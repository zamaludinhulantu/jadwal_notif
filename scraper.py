import hashlib
import logging
import re
from datetime import datetime
from typing import List
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


def build_schedule_url(base_url: str, year_month: str) -> str:
    return f"{base_url.rstrip('/')}/{year_month}"


def get_target_months(check_next_month: bool, timezone_name: str) -> List[str]:
    now = datetime.now(ZoneInfo(timezone_name))
    months = [now.strftime("%Y-%m")]

    if check_next_month:
        year = now.year + (1 if now.month == 12 else 0)
        month = 1 if now.month == 12 else now.month + 1
        months.append(f"{year:04d}-{month:02d}")

    return months


def extract_year_month(text: str) -> str | None:
    match = re.search(r"\b(\d{4}-\d{2})\b", text)
    return match.group(1) if match else None


def fetch_html(url: str, timeout: int = 30) -> str:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Gagal mengambil halaman %s: %s", url, exc)
        return ""

    return response.text


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _cell_text_parts(cell) -> List[str]:
    parts = [piece.strip() for piece in cell.stripped_strings if piece.strip()]
    return parts


def _sanitize_key(header_text: str, fallback_index: int) -> str:
    normalized = _normalize_space(header_text).casefold()
    replacements = {
        "&": "dan",
        "/": " ",
        "-": " ",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized or f"column_{fallback_index}"


def _extract_fields(record: dict) -> dict:
    nama_nim = record.get("nama_dan_nim", "")
    nama_parts = [part.strip() for part in nama_nim.split("\n") if part.strip()]
    nama = nama_parts[0] if nama_parts else ""
    nim = ""
    for part in nama_parts[1:]:
        digits = re.sub(r"\D", "", part)
        if digits:
            nim = digits
            break

    tempat_waktu = record.get("tempat_dan_waktu", "")
    tempat_parts = [part.strip() for part in tempat_waktu.split("\n") if part.strip()]
    tempat = tempat_parts[0] if tempat_parts else ""
    tanggal = ""
    jam = ""
    for part in tempat_parts[1:]:
        lower_part = part.casefold()
        if "hari " in lower_part:
            tanggal = part
        if "pukul" in lower_part:
            jam = part.replace("Pukul", "").replace("pukul", "").strip(" :")

    penguji = record.get("dosen_penguji", "")
    penguji_list = [part.strip() for part in penguji.split("\n") if part.strip()]

    extracted = {
        "nama": nama,
        "nim": nim,
        "jenis_ujian": record.get("ujian", ""),
        "judul": record.get("judul", ""),
        "tanggal_ujian": tanggal,
        "jam_ujian": jam,
        "tempat_ruangan": tempat,
        "penguji_pembimbing": penguji_list,
    }
    return extracted


def _build_schedule_hash(schedule: dict) -> str:
    material = "||".join(
        [
            str(schedule.get("nama", "")),
            str(schedule.get("nim", "")),
            str(schedule.get("jenis_ujian", "")),
            str(schedule.get("tanggal_ujian", "")),
            str(schedule.get("jam_ujian", "")),
            str(schedule.get("tempat_ruangan", "")),
            str(schedule.get("judul", "")),
            str(schedule.get("canonical_source_url", "")),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _record_from_row(headers: List[str], cells: List) -> dict:
    record: dict = {}
    for index, cell in enumerate(cells):
        key = headers[index] if index < len(headers) else f"column_{index}"
        record[key] = "\n".join(_cell_text_parts(cell))
    record["raw_text"] = " | ".join(_normalize_space(cell.get_text(" ", strip=True)) for cell in cells)
    return record


def _fallback_records(soup: BeautifulSoup, source_url: str) -> List[dict]:
    text = _normalize_space(soup.get_text(" ", strip=True))
    if not text:
        logger.warning("Halaman kosong: %s", source_url)
        return []

    schedule = {
        "raw_text": text[:4000],
        "source_url": source_url,
        "nama": "",
        "nim": "",
        "jenis_ujian": "",
        "judul": "",
        "tanggal_ujian": "",
        "jam_ujian": "",
        "tempat_ruangan": "",
        "penguji_pembimbing": [],
    }
    schedule["schedule_hash"] = _build_schedule_hash(schedule)
    return [schedule]


def parse_schedules(
    html: str, source_url: str, canonical_source_url: str | None = None
) -> List[dict]:
    if not html.strip():
        logger.warning("HTML kosong untuk %s", source_url)
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        logger.warning("Tidak ada tabel ditemukan di %s", source_url)
        return _fallback_records(soup, source_url)

    schedules: List[dict] = []
    for table_index, table in enumerate(tables):
        header_cells = table.find_all("th")
        headers = [
            _sanitize_key(cell.get_text(" ", strip=True), index)
            for index, cell in enumerate(header_cells)
        ]

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            record = _record_from_row(headers, cells)
            extracted = _extract_fields(record)
            schedule = {
                "table_index": table_index,
                "source_url": source_url,
                "canonical_source_url": canonical_source_url or source_url,
                **record,
                **extracted,
            }
            schedule["schedule_hash"] = _build_schedule_hash(schedule)
            schedules.append(schedule)

    if not schedules:
        logger.warning("Tabel ditemukan tetapi tidak ada baris data di %s", source_url)
        return _fallback_records(soup, source_url)

    return schedules


def extract_pagination_urls(html: str, source_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = {source_url}

    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, link["href"])
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        if "page" not in query:
            continue
        if source_url.rstrip("/") not in href:
            continue
        urls.add(href)

    return sorted(
        urls,
        key=lambda value: int(parse_qs(urlparse(value).query).get("page", ["1"])[0]),
    )


def scrape_month(base_url: str, year_month: str) -> List[dict]:
    url = build_schedule_url(base_url, year_month)
    first_html = fetch_html(url)
    if not first_html:
        return []

    page_urls = extract_pagination_urls(first_html, url)
    schedules_by_hash: dict[str, dict] = {}

    for page_url in page_urls:
        html = first_html if page_url == url else fetch_html(page_url)
        if not html:
            continue
        for schedule in parse_schedules(html, page_url, canonical_source_url=url):
            schedules_by_hash.setdefault(schedule["schedule_hash"], schedule)

    return list(schedules_by_hash.values())
