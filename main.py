import argparse
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Iterable, List
from zoneinfo import ZoneInfo

from config import AppConfig, ConfigurationError, load_config
from notifier import (
    NotificationError,
    format_heartbeat_message,
    format_schedule_message,
    send_telegram_message,
)
from scraper import extract_year_month, get_target_months, scrape_month
from storage import (
    ScheduleStore,
    load_heartbeat_state,
    save_heartbeat_state,
    should_send_heartbeat,
)


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor jadwal ujian SISKP dan kirim notifikasi Telegram."
    )
    parser.add_argument(
        "--month",
        dest="months",
        action="append",
        help="Cek bulan tertentu dalam format YYYY-MM. Bisa dipakai lebih dari sekali.",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Kirim pesan test ke Telegram tanpa scraping atau menyentuh storage.",
    )
    parser.add_argument(
        "--seed-existing",
        action="store_true",
        help="Tandai semua jadwal yang saat ini ada sebagai sudah dilihat tanpa kirim notifikasi.",
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def resolve_target_months(config: AppConfig, cli_months: Iterable[str] | None) -> List[str]:
    if cli_months:
        return list(dict.fromkeys(cli_months))
    return get_target_months(config.check_next_month, config.timezone)


def schedule_is_personal(schedule: dict, config: AppConfig) -> bool:
    my_name = config.my_name.casefold()
    my_nim = config.my_nim.casefold()
    haystacks = [
        str(schedule.get("nama", "")).casefold(),
        str(schedule.get("nim", "")).casefold(),
        str(schedule.get("raw_text", "")).casefold(),
    ]

    name_match = bool(my_name) and any(my_name in value for value in haystacks)
    nim_match = bool(my_nim) and any(my_nim in value for value in haystacks)
    return name_match or nim_match


def build_month_totals(schedules: List[dict]) -> OrderedDict[str, int]:
    month_totals: OrderedDict[str, int] = OrderedDict()
    for schedule in schedules:
        month_label = extract_year_month(schedule.get("canonical_source_url", "")) or extract_year_month(
            schedule.get("source_url", "")
        )
        if not month_label:
            continue
        month_totals[month_label] = month_totals.get(month_label, 0) + 1
    return month_totals


def notify_new_schedules(
    schedules: List[dict], store: ScheduleStore, config: AppConfig
) -> int:
    sent_count = 0
    month_totals = build_month_totals(schedules)

    for schedule in schedules:
        schedule_hash = schedule["schedule_hash"]
        if not store.is_new(schedule_hash):
            continue

        is_personal = schedule_is_personal(schedule, config)
        month_label = extract_year_month(schedule.get("source_url", "")) or "-"
        message = format_schedule_message(
            schedule,
            month_label,
            is_personal,
            month_totals=month_totals,
        )

        try:
            send_telegram_message(
                message,
                bot_token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
            )
        except NotificationError as exc:
            logger.error("Gagal mengirim notifikasi untuk hash %s: %s", schedule_hash, exc)
            continue
        store.save_seen(schedule_hash, schedule)
        sent_count += 1
        logger.info("Notifikasi terkirim untuk hash %s", schedule_hash)

    return sent_count


def seed_existing_schedules(schedules: List[dict], store: ScheduleStore) -> tuple[int, int, int]:
    added_count, existing_count = store.save_many_seen(schedules)
    total_count = len(schedules)
    return total_count, added_count, existing_count


def maybe_send_heartbeat(config: AppConfig) -> None:
    if not config.send_no_update_notification:
        return

    if config.no_update_notification_every_run:
        message = format_heartbeat_message(config.timezone)
        send_telegram_message(
            message,
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
        )
        logger.info("Heartbeat terkirim untuk run tanpa update.")
        return

    state = load_heartbeat_state(config.heartbeat_state_path)
    last_sent_at = state.get("last_sent_at")
    if not should_send_heartbeat(
        last_sent_at,
        config.heartbeat_interval_minutes,
        config.timezone,
    ):
        logger.info("Heartbeat belum dikirim karena interval belum terlewati.")
        return

    message = format_heartbeat_message(config.timezone)
    send_telegram_message(
        message,
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    now = datetime.now(ZoneInfo(config.timezone)).isoformat()
    save_heartbeat_state(config.heartbeat_state_path, {"last_sent_at": now})
    logger.info("Heartbeat terkirim dan state heartbeat diperbarui.")


def main() -> int:
    setup_logging()
    args = parse_args()

    try:
        config = load_config()
    except ConfigurationError as exc:
        logger.error("Konfigurasi tidak valid: %s", exc)
        return 1

    if args.test_telegram:
        try:
            send_telegram_message(
                "\u2705 Bot SISKP Jadwal Notifier aktif.",
                bot_token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
            )
        except NotificationError as exc:
            logger.error("Test Telegram gagal: %s", exc)
            return 1

        logger.info("Test Telegram berhasil dikirim.")
        return 0

    target_months = resolve_target_months(config, args.months)
    logger.info("Target bulan: %s", ", ".join(target_months))

    all_schedules: List[dict] = []
    for year_month in target_months:
        schedules = scrape_month(config.siskp_base_url, year_month)
        logger.info("Bulan %s menghasilkan %s jadwal", year_month, len(schedules))
        all_schedules.extend(schedules)

    if not all_schedules:
        logger.warning("Tidak ada jadwal yang berhasil dibaca.")
        return 0

    store = ScheduleStore(config.storage_path)

    if args.seed_existing:
        total_count, added_count, existing_count = seed_existing_schedules(
            all_schedules, store
        )
        logger.info("Seed selesai. Total jadwal ditemukan: %s", total_count)
        logger.info(
            "Seed selesai. Jadwal baru yang ditandai sebagai sudah dilihat: %s",
            added_count,
        )
        logger.info(
            "Seed selesai. Jadwal yang sebelumnya sudah ada di state: %s",
            existing_count,
        )
        return 0

    has_unseen_schedules = any(
        store.is_new(schedule["schedule_hash"]) for schedule in all_schedules
    )
    new_count = notify_new_schedules(all_schedules, store, config)

    if has_unseen_schedules:
        logger.info("Total notifikasi baru: %s", new_count)
        return 0

    if new_count == 0:
        logger.info("Tidak ada jadwal baru.")
        try:
            maybe_send_heartbeat(config)
        except NotificationError as exc:
            logger.error("Gagal mengirim heartbeat: %s", exc)
            return 1
    else:
        logger.info("Total notifikasi baru: %s", new_count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
