import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    pass


@dataclass(slots=True)
class AppConfig:
    siskp_base_url: str
    siskp_public_base_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    my_name: str
    my_nim: str
    check_next_month: bool
    storage_path: Path
    exam_registration_storage_path: Path
    thesis_history_storage_path: Path
    public_list_max_pages: int
    timezone: str
    send_no_update_notification: bool
    no_update_notification_every_run: bool
    heartbeat_interval_minutes: int
    heartbeat_state_path: Path


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> AppConfig:
    load_dotenv()

    siskp_base_url = os.getenv(
        "SISKP_BASE_URL", "https://siskp.informatika.ft.ung.ac.id/masuk/jadwal"
    ).rstrip("/")
    siskp_public_base_url = os.getenv(
        "SISKP_PUBLIC_BASE_URL", "https://siskp.informatika.ft.ung.ac.id/masuk"
    ).rstrip("/")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    my_name = os.getenv("MY_NAME", "").strip()
    my_nim = os.getenv("MY_NIM", "").strip()
    check_next_month = _parse_bool(os.getenv("CHECK_NEXT_MONTH"), default=True)
    storage_path = Path(os.getenv("STORAGE_PATH", "data/sent_schedules.json"))
    exam_registration_storage_path = Path(
        os.getenv("EXAM_REGISTRATION_STORAGE_PATH", "data/sent_exam_registrations.json")
    )
    thesis_history_storage_path = Path(
        os.getenv("THESIS_HISTORY_STORAGE_PATH", "data/sent_thesis_history.json")
    )
    try:
        public_list_max_pages = int(os.getenv("PUBLIC_LIST_MAX_PAGES", "3"))
    except ValueError as exc:
        raise ConfigurationError("PUBLIC_LIST_MAX_PAGES harus berupa angka.") from exc
    timezone = os.getenv("TIMEZONE", "Asia/Makassar").strip() or "Asia/Makassar"
    send_no_update_notification = _parse_bool(
        os.getenv("SEND_NO_UPDATE_NOTIFICATION"), default=False
    )
    no_update_notification_every_run = _parse_bool(
        os.getenv("NO_UPDATE_NOTIFICATION_EVERY_RUN"), default=False
    )
    try:
        heartbeat_interval_minutes = int(
            os.getenv("HEARTBEAT_INTERVAL_MINUTES", "60")
        )
    except ValueError as exc:
        raise ConfigurationError("HEARTBEAT_INTERVAL_MINUTES harus berupa angka.") from exc
    heartbeat_state_path = Path(
        os.getenv("HEARTBEAT_STATE_PATH", "data/heartbeat_state.json")
    )

    if not telegram_bot_token:
        raise ConfigurationError("TELEGRAM_BOT_TOKEN belum diisi.")
    if not telegram_chat_id:
        raise ConfigurationError("TELEGRAM_CHAT_ID belum diisi.")
    if heartbeat_interval_minutes < 0:
        raise ConfigurationError("HEARTBEAT_INTERVAL_MINUTES tidak boleh negatif.")
    if public_list_max_pages < 1:
        raise ConfigurationError("PUBLIC_LIST_MAX_PAGES minimal 1.")

    return AppConfig(
        siskp_base_url=siskp_base_url,
        siskp_public_base_url=siskp_public_base_url,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        my_name=my_name,
        my_nim=my_nim,
        check_next_month=check_next_month,
        storage_path=storage_path,
        exam_registration_storage_path=exam_registration_storage_path,
        thesis_history_storage_path=thesis_history_storage_path,
        public_list_max_pages=public_list_max_pages,
        timezone=timezone,
        send_no_update_notification=send_no_update_notification,
        no_update_notification_every_run=no_update_notification_every_run,
        heartbeat_interval_minutes=heartbeat_interval_minutes,
        heartbeat_state_path=heartbeat_state_path,
    )
