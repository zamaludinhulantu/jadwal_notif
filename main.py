import argparse
import logging
from typing import Iterable, List

from config import AppConfig, ConfigurationError, load_config
from notifier import NotificationError, format_schedule_message, send_telegram_message
from scraper import extract_year_month, get_target_months, scrape_month
from storage import ScheduleStore


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


def notify_new_schedules(
    schedules: List[dict], store: ScheduleStore, config: AppConfig
) -> int:
    sent_count = 0

    for schedule in schedules:
        schedule_hash = schedule["schedule_hash"]
        if not store.is_new(schedule_hash):
            continue

        is_personal = schedule_is_personal(schedule, config)
        month_label = extract_year_month(schedule.get("source_url", "")) or "-"
        message = format_schedule_message(schedule, month_label, is_personal)

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

    new_count = notify_new_schedules(all_schedules, store, config)

    if new_count == 0:
        logger.info("Tidak ada jadwal baru.")
    else:
        logger.info("Total notifikasi baru: %s", new_count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
