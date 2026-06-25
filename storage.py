import json
from pathlib import Path
from typing import Dict, Iterable


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

    def save_many_seen(self, schedules: Iterable[dict]) -> tuple[int, int]:
        added_count = 0
        existing_count = 0

        for schedule in schedules:
            schedule_hash = schedule["schedule_hash"]
            if self.is_new(schedule_hash):
                self.remember(schedule_hash, schedule)
                added_count += 1
            else:
                existing_count += 1

        self.flush()
        return added_count, existing_count
