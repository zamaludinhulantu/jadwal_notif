import logging
from typing import Iterable

import requests


logger = logging.getLogger(__name__)
TELEGRAM_LIMIT = 4000


class NotificationError(RuntimeError):
    pass


def _truncate(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _join_people(items: Iterable[str]) -> str:
    values = [value for value in items if value and value != "-"]
    return ", ".join(values) if values else "-"


def format_schedule_message(schedule: dict, month_label: str, is_personal: bool) -> str:
    title = (
        "\U0001F6A8 PENTING: Jadwal Ujian Kamu Terdeteksi"
        if is_personal
        else "\U0001F4E2 Jadwal Ujian SISKP Baru"
    )
    link_label = "Segera cek SISKP:" if is_personal else "Link:"

    message = "\n".join(
        [
            title,
            "",
            *(["Bulan: " + month_label] if not is_personal else []),
            f"Nama: {schedule.get('nama') or '-'}",
            f"NIM: {schedule.get('nim') or '-'}",
            f"Jenis Ujian: {schedule.get('jenis_ujian') or '-'}",
            f"Tanggal: {schedule.get('tanggal_ujian') or '-'}",
            f"Jam: {schedule.get('jam_ujian') or '-'}",
            f"Tempat: {schedule.get('tempat_ruangan') or '-'}",
            f"Judul: {schedule.get('judul') or '-'}",
            f"Penguji: {_join_people(schedule.get('penguji_pembimbing', []))}",
            "",
            link_label,
            schedule.get("source_url", "-"),
        ]
    )
    return _truncate(message)


def send_telegram_message(text: str, bot_token: str, chat_id: str) -> None:
    if not bot_token:
        raise NotificationError("TELEGRAM_BOT_TOKEN belum diisi.")
    if not chat_id:
        raise NotificationError("TELEGRAM_CHAT_ID belum diisi.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _truncate(text),
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()
    except requests.RequestException as exc:
        logger.error("Gagal mengirim pesan Telegram: %s", exc)
        raise NotificationError("Gagal mengirim pesan Telegram.") from exc
    except ValueError as exc:
        logger.error("Response Telegram bukan JSON valid: %s", exc)
        raise NotificationError("Response Telegram tidak valid.") from exc

    if not response_data.get("ok"):
        description = response_data.get("description", "Telegram API menolak request.")
        raise NotificationError(description)
