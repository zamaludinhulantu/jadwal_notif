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


def _build_generic_hash(parts: List[str]) -> str:
    material = "||".join(str(part) for part in parts)
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


def limit_pagination_urls(page_urls: List[str], max_pages: int) -> List[str]:
    return page_urls[:max_pages]


def _normalize_multiline_text(text: str) -> str:
    value = text.replace("\r", "\n")
    value = re.sub(r"\n\s*\n+", "\n", value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def _extract_card_list(soup: BeautifulSoup) -> List:
    for card in soup.select(".card"):
        items = [
            child
            for child in card.find_all("div", class_="card-body", recursive=False)
            if "border-bottom" in (child.get("class") or [])
        ]
        if items:
            return items
    return []


def parse_exam_registrations(
    html: str, source_url: str, canonical_source_url: str | None = None
) -> List[dict]:
    if not html.strip():
        logger.warning("HTML kosong untuk %s", source_url)
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = _extract_card_list(soup)
    registrations: List[dict] = []

    for item in items:
        title_node = item.select_one(".card-title")
        detail_link = item.select_one("a[href*='/masuk/ujian/']")
        if title_node is None or detail_link is None:
            continue

        title_text = _normalize_space(title_node.get_text(" ", strip=True))
        match = re.match(r"\d+\)\.\s*(.*?)\s*\((\d+)\)$", title_text)
        if not match:
            continue

        status_node = item.select_one(".text-dark")
        timestamp_node = item.select_one(".small em")
        raw_lines = [
            line.strip()
            for line in item.get_text("\n", strip=True).splitlines()
            if line.strip() and line.strip().casefold() != "detail"
        ]

        exam_type = raw_lines[1].rstrip(".") if len(raw_lines) > 1 else ""
        title = ""
        for line in raw_lines:
            if line.startswith("Judul:"):
                title = line.replace("Judul:", "", 1).strip()
                break

        registration = {
            "name": match.group(1).strip(),
            "nim": match.group(2).strip(),
            "exam_type": exam_type,
            "title": title,
            "status": _normalize_space(status_node.get_text(" ", strip=True)) if status_node else "",
            "registered_at": _normalize_space(timestamp_node.get_text(" ", strip=True))
            if timestamp_node
            else "",
            "detail_url": urljoin(source_url, detail_link["href"]),
            "source_url": source_url,
            "canonical_source_url": canonical_source_url or source_url,
            "raw_text": _normalize_multiline_text(item.get_text("\n", strip=True)),
        }
        registration["entry_hash"] = _build_generic_hash(
            [
                "exam_registration",
                registration["nim"],
                registration["detail_url"],
                registration["registered_at"],
                registration["status"],
            ]
        )
        registrations.append(registration)

    return registrations


def parse_thesis_history(
    html: str, source_url: str, canonical_source_url: str | None = None
) -> List[dict]:
    if not html.strip():
        logger.warning("HTML kosong untuk %s", source_url)
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = _extract_card_list(soup)
    histories: List[dict] = []

    for item in items:
        title_node = item.select_one(".card-title")
        detail_link = item.select_one("a[href*='/masuk/riwayat-skripsi/']")
        if title_node is None or detail_link is None:
            continue

        title_text = _normalize_space(title_node.get_text(" ", strip=True))
        match = re.match(r"\d+\)\.\s*(.*?)\s*\((\d+)\)$", title_text)
        if not match:
            continue

        status_node = item.select_one(".text-dark")
        raw_lines = [
            line.strip()
            for line in item.get_text("\n", strip=True).splitlines()
            if line.strip() and line.strip().casefold() != "detail"
        ]
        thesis_title = raw_lines[1] if len(raw_lines) > 1 else ""

        history = {
            "name": match.group(1).strip(),
            "nim": match.group(2).strip(),
            "title": thesis_title,
            "stage": _normalize_space(status_node.get_text(" ", strip=True)) if status_node else "",
            "detail_url": urljoin(source_url, detail_link["href"]),
            "source_url": source_url,
            "canonical_source_url": canonical_source_url or source_url,
            "raw_text": _normalize_multiline_text(item.get_text("\n", strip=True)),
        }
        history["entry_hash"] = _build_generic_hash(
            [
                "thesis_history",
                history["nim"],
                history["detail_url"],
                history["stage"],
            ]
        )
        histories.append(history)

    return histories


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


def scrape_exam_registrations(public_base_url: str, max_pages: int = 3) -> List[dict]:
    url = f"{public_base_url.rstrip('/')}/ujian"
    first_html = fetch_html(url)
    if not first_html:
        return []

    page_urls = limit_pagination_urls(extract_pagination_urls(first_html, url), max_pages)
    registrations_by_hash: dict[str, dict] = {}

    for page_url in page_urls:
        html = first_html if page_url == url else fetch_html(page_url)
        if not html:
            continue
        for registration in parse_exam_registrations(html, page_url, canonical_source_url=url):
            registrations_by_hash.setdefault(registration["entry_hash"], registration)

    return list(registrations_by_hash.values())


def scrape_thesis_history(public_base_url: str, max_pages: int = 3) -> List[dict]:
    url = f"{public_base_url.rstrip('/')}/riwayat-skripsi"
    first_html = fetch_html(url)
    if not first_html:
        return []

    page_urls = limit_pagination_urls(extract_pagination_urls(first_html, url), max_pages)
    histories_by_hash: dict[str, dict] = {}

    for page_url in page_urls:
        html = first_html if page_url == url else fetch_html(page_url)
        if not html:
            continue
        for history in parse_thesis_history(html, page_url, canonical_source_url=url):
            histories_by_hash.setdefault(history["entry_hash"], history)

    return list(histories_by_hash.values())
