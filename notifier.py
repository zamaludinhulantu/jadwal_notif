import logging
from datetime import datetime
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

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


def _format_month_totals(month_totals: Mapping[str, int] | None) -> list[str]:
    if not month_totals:
        return []

    lines = ["Total jadwal bulan terpantau:"]
    for month_label, total in month_totals.items():
        lines.append(f"- {month_label}: {total}")
    return lines


def format_schedule_message(
    schedule: dict,
    month_label: str,
    is_personal: bool,
    month_totals: Mapping[str, int] | None = None,
) -> str:
    title = (
        "\u2705\u2705\u2705\u2705\u2705 \U0001F6A8 PENTING: Jadwal Ujian Kamu Terdeteksi"
        if is_personal
        else "\u2705\u2705\u2705\u2705\u2705 \U0001F4E2 Jadwal Ujian SISKP Baru"
    )
    link_label = "Segera cek SISKP:" if is_personal else "Link:"
    totals_lines = _format_month_totals(month_totals)

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
            *totals_lines,
            *([""] if totals_lines else []),
            link_label,
            schedule.get("source_url", "-"),
        ]
    )
    return _truncate(message)


def format_heartbeat_message(
    timezone_name: str,
    month_totals: Mapping[str, int] | None = None,
) -> str:
    now = datetime.now(ZoneInfo(timezone_name))
    month_names = {
        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember",
    }
    time_label = (
        f"{now.day:02d} {month_names[now.month]} {now.year} "
        f"{now.strftime('%H:%M')} {now.tzname() or timezone_name}"
    )
    totals_lines = _format_month_totals(month_totals)
    message = "\n".join(
        [
            "\u2139\ufe0f Bot SISKP aktif",
            "",
            "\u274c\u274c\u274c Belum ada jadwal ujian baru.",
            *totals_lines,
            *([""] if totals_lines else []),
            f"Cek terakhir: {time_label}",
            "Sumber: SISKP Jadwal Ujian",
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
