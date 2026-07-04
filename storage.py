import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)


class ScheduleStore:
    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = self.load_seen()

    def load_seen(self) -> Dict[str, dict]:
        if not self.storage_path.exists():
            return {}

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def is_new(self, schedule_hash: str) -> bool:
        return schedule_hash not in self._seen

    def remember(self, schedule_hash: str, schedule_data: dict) -> None:
        self._seen[schedule_hash] = schedule_data

    def flush(self) -> None:
        with self.storage_path.open("w", encoding="utf-8") as handle:
            json.dump(self._seen, handle, ensure_ascii=False, indent=2)

    def save_seen(self, schedule_hash: str, schedule_data: dict) -> None:
        self.remember(schedule_hash, schedule_data)
        self.flush()

    def _resolve_item_hash(self, item: dict) -> str:
        item_hash = item.get("schedule_hash") or item.get("entry_hash")
        if not item_hash:
            raise KeyError("Item harus memiliki schedule_hash atau entry_hash.")
        return str(item_hash)

    def save_many_seen(self, schedules: Iterable[dict]) -> tuple[int, int]:
        added_count = 0
        existing_count = 0

        for schedule in schedules:
            schedule_hash = self._resolve_item_hash(schedule)
            if self.is_new(schedule_hash):
                self.remember(schedule_hash, schedule)
                added_count += 1
            else:
                existing_count += 1

        self.flush()
        return added_count, existing_count


def load_heartbeat_state(path: Path) -> dict:
    heartbeat_path = Path(path)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)

    if not heartbeat_path.exists():
        heartbeat_path.write_text("{}", encoding="utf-8")
        return {}

    try:
        with heartbeat_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.warning("State heartbeat tidak valid, dianggap belum pernah heartbeat.")
        return {}

    return data if isinstance(data, dict) else {}


def save_heartbeat_state(path: Path, data: dict) -> None:
    heartbeat_path = Path(path)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    with heartbeat_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def should_send_heartbeat(
    last_sent_at: str | None, interval_minutes: int, timezone: str
) -> bool:
    now = datetime.now(ZoneInfo(timezone))

    if interval_minutes == 60:
        if now.minute != 0:
            return False

        if not last_sent_at:
            return True

        try:
            last_sent = datetime.fromisoformat(last_sent_at)
        except ValueError:
            logger.warning("Format last_sent_at heartbeat tidak valid, kirim heartbeat baru.")
            return True

        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=ZoneInfo(timezone))

        return last_sent.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%dT%H") != now.strftime(
            "%Y-%m-%dT%H"
        )

    if not last_sent_at:
        return True

    try:
        last_sent = datetime.fromisoformat(last_sent_at)
    except ValueError:
        logger.warning("Format last_sent_at heartbeat tidak valid, kirim heartbeat baru.")
        return True

    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=ZoneInfo(timezone))

    return now - last_sent >= timedelta(minutes=interval_minutes)
