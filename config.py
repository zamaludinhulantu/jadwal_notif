import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    pass


@dataclass(slots=True)
class AppConfig:
    siskp_base_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    my_name: str
    my_nim: str
    check_next_month: bool
    storage_path: Path
    timezone: str


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> AppConfig:
    load_dotenv()

    siskp_base_url = os.getenv(
        "SISKP_BASE_URL", "https://siskp.informatika.ft.ung.ac.id/masuk/jadwal"
    ).rstrip("/")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    my_name = os.getenv("MY_NAME", "").strip()
    my_nim = os.getenv("MY_NIM", "").strip()
    check_next_month = _parse_bool(os.getenv("CHECK_NEXT_MONTH"), default=True)
    storage_path = Path(os.getenv("STORAGE_PATH", "data/sent_schedules.json"))
    timezone = os.getenv("TIMEZONE", "Asia/Makassar").strip() or "Asia/Makassar"

    if not telegram_bot_token:
        raise ConfigurationError("TELEGRAM_BOT_TOKEN belum diisi.")
    if not telegram_chat_id:
        raise ConfigurationError("TELEGRAM_CHAT_ID belum diisi.")

    return AppConfig(
        siskp_base_url=siskp_base_url,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        my_name=my_name,
        my_nim=my_nim,
        check_next_month=check_next_month,
        storage_path=storage_path,
        timezone=timezone,
    )
