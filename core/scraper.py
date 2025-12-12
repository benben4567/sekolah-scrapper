"""High-level Selenium orchestration for scraping the DIKMEN site."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Tuple
from urllib.parse import urljoin

from core import navigation
from core.csv_store import FailedWriter, SchoolsWriter, write_provinces
from core.logger import EmojiLogger
from core.state import ScrapeState

BASE_URL = "https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen"
MAX_DETAIL_RETRY = 3


@dataclass
class ProvinceContext:
    """Container for province attributes passed across methods."""

    id: int
    name: str
    url: str


@dataclass
class CityContext:
    """Represents a kabupaten/kota page belonging to a province."""

    province: ProvinceContext
    name: str
    url: str


@dataclass
class DistrictContext:
    """Represents a kecamatan page belonging to a city/kabupaten."""

    province: ProvinceContext
    city_name: str
    name: str
    url: str


@dataclass
class SchoolListing:
    """Represents a school listing row waiting for detail scraping."""

    province: ProvinceContext
    city_name: str
    district_name: str
    npsn: str
    name: str
    detail_url: str


class DikmenScraper:
    """Encapsulates Selenium navigation across provinces, cities, and schools."""

    def __init__(
        self,
        driver: Any,
        logger: EmojiLogger,
        state: ScrapeState,
        schools_writer: SchoolsWriter,
        failed_writer: FailedWriter,
        base_delay: float,
    ) -> None:
        self.driver = driver
        self.logger = logger
        self.state = state
        self.schools_writer = schools_writer
        self.failed_writer = failed_writer
        self.base_delay = max(0.5, base_delay)
        self.counters = {
            "province": 0,
            "school_new": 0,
            "school_skip": 0,
            "school_fail": 0,
        }
        self.city_queue: list[CityContext] = []
        self.district_queue: list[DistrictContext] = []
        self.school_queue: list[SchoolListing] = []

    def scrape_provinces_if_needed(self, provinces_csv_path: str) -> list[dict[str, str]]:
        """Scrape the province table and persist it when not already cached."""

        self.driver.get(BASE_URL)
        self.sleep_with_jitter()
        rows = navigation.collect_table_rows(self.driver, navigation.PROVINCE_TABLE_SELECTOR)
        provinces: list[dict[str, str]] = []
        for idx, row in enumerate(rows, start=1):
            name, href = self._extract_link(row)
            if not name:
                continue
            provinces.append({"id": str(idx), "nama": name, "url": href or BASE_URL})

        if not provinces:
            raise RuntimeError("Tidak menemukan tabel provinsi pada halaman utama.")

        csv_path = Path(provinces_csv_path)
        if not csv_path.exists():
            write_provinces(csv_path, provinces)
            self.logger.save(f"Tulis {len(provinces)} provinsi ke {csv_path.name}")

        self.state.provinces = provinces
        return provinces

    def scrape_all_provinces(
        self,
        mode: str,
        start_id: int | None = None,
        single_province_id: int | None = None,
    ) -> None:
        """Drive the scraping process across all relevant provinces."""

        if not self.state.provinces:
            raise RuntimeError("Daftar provinsi belum dimuat ke dalam state.")

        self.city_queue.clear()
        self.district_queue.clear()
        self.school_queue.clear()

        self.logger.start(
            f"Mulai scraping mode={mode} start_id={start_id} single_province={single_province_id}"
        )
        province_contexts = [
            ProvinceContext(
                id=int(province.get("id", 0)),
                name=province.get("nama", ""),
                url=province.get("url") or self._build_province_url(int(province.get("id", 0))),
            )
            for province in self.state.provinces
        ]

        for context in province_contexts:
            if start_id and context.id < start_id:
                continue
            if mode == "province" and single_province_id and context.id != single_province_id:
                continue
            try:
                self.collect_cities(context)
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.failure(f"Provinsi {context.name} gagal (kota): {exc}")

        for city in self.city_queue:
            try:
                self.collect_districts(city)
            except Exception as exc:
                self.logger.warn("warn", f"Gagal memuat kecamatan di {city.name}: {exc}")

        for district in self.district_queue:
            try:
                self.collect_schools(district)
            except Exception as exc:
                self.logger.warn("warn", f"Gagal memuat sekolah di {district.name}: {exc}")

        for listing in self.school_queue:
            self.process_school_listing(listing)

    def collect_cities(self, province: ProvinceContext) -> None:
        """Collect kab/kota links for a province without descending further yet."""

        self.logger.province(f"Provinsi {province.id} - {province.name}")
        self.counters["province"] += 1
        self.driver.get(province.url)
        self.sleep_with_jitter()
        rows = navigation.collect_table_rows(self.driver, navigation.CITY_TABLE_SELECTOR)
        links = self._extract_links(rows)
        entries = [CityContext(province=province, name=name, url=url) for name, url in links]
        self.city_queue.extend(entries)
        self.logger.city(
            f"Kumpulkan {len(entries)} kab/kota untuk {province.name} (total queue: {len(self.city_queue)})"
        )

    def collect_districts(self, city: CityContext) -> None:
        """Collect kecamatan links for a city and queue them for later processing."""

        self.logger.city(f"Kab/Kota: {city.name} ({city.province.name})")
        self.driver.get(city.url)
        self.sleep_with_jitter()
        rows = navigation.collect_table_rows(self.driver, navigation.DISTRICT_TABLE_SELECTOR)
        links = self._extract_links(rows)
        entries = [
            DistrictContext(province=city.province, city_name=city.name, name=name, url=url)
            for name, url in links
        ]
        self.district_queue.extend(entries)
        self.logger.district(
            f"Tambah {len(entries)} kecamatan dari {city.name} (total queue: {len(self.district_queue)})"
        )

    def collect_schools(self, district: DistrictContext) -> None:
        """Collect school listings for a district and enqueue them for detail scraping."""

        if not district.url:
            return
        self.logger.district(f"Kecamatan: {district.name} ({district.city_name})")
        self.driver.get(district.url)
        self.sleep_with_jitter()

        while True:
            rows = navigation.collect_table_rows(self.driver, navigation.SCHOOL_TABLE_SELECTOR)
            added = 0
            for row in rows:
                cells = navigation.extract_cells(row)
                if len(cells) < 3:
                    continue
                npsn = cells[1].text.strip()
                link_name, detail_url = self._extract_link(row)
                listing_name = cells[2].text.strip() or link_name
                if not npsn or not detail_url:
                    continue
                if self.state.should_skip(npsn):
                    self.counters["school_skip"] += 1
                    self.logger.skip(f"NPSN {npsn} sudah ada, skip")
                    continue
                listing = SchoolListing(
                    province=district.province,
                    city_name=district.city_name,
                    district_name=district.name,
                    npsn=npsn,
                    name=listing_name or npsn,
                    detail_url=urljoin(BASE_URL, detail_url),
                )
                self.school_queue.append(listing)
                added += 1
            if added:
                self.logger.school(
                    f"Queue {added} sekolah dari {district.name} (total queue: {len(self.school_queue)})"
                )

            next_button = navigation.find_next_page(self.driver)
            if not next_button:
                break
            self.logger.wait(f"Pagination berikutnya untuk {district.name}")
            next_button.click()
            self.sleep_with_jitter()

    def process_school_listing(self, listing: SchoolListing) -> None:
        """Fetch school details for a queued listing and write to CSV."""

        if self.state.should_skip(listing.npsn):
            self.counters["school_skip"] += 1
            return
        self.logger.school(f"{listing.npsn} - {listing.name}")
        last_error: str | None = None
        for attempt in range(1, MAX_DETAIL_RETRY + 1):
            try:
                self.driver.get(listing.detail_url)
                self.sleep_with_jitter()
                details = navigation.parse_detail_block(self.driver)
                record = {
                    "province_id": str(listing.province.id),
                    "nama": details.get("nama") or listing.name,
                    "npsn": details.get("npsn") or listing.npsn,
                    "alamat": details.get("alamat", ""),
                    "desa_kel": details.get("desa_kel", ""),
                    "kecamatan": details.get("kecamatan", listing.district_name),
                    "kota_kab": details.get("kota_kab", listing.city_name),
                    "provinsi": details.get("provinsi", listing.province.name),
                    "status": details.get("status", ""),
                    "bentuk": details.get("bentuk", ""),
                }
                self.schools_writer.append_school(record)
                flushed = self.schools_writer.flush_if_needed()
                if flushed:
                    total = self.schools_writer.total_written
                    self.logger.save(
                        f"Flush {flushed} record ke schools.csv (total: {total})"
                    )
                self.state.register_school(record["npsn"])
                self.counters["school_new"] += 1
                return
            except Exception as exc:  # pragma: no cover - network/driver issues
                last_error = str(exc)
                self.logger.warn(
                    "warn", f"Retry {attempt} untuk NPSN {listing.npsn}: {exc}"
                )
                time.sleep(2)

        self.counters["school_fail"] += 1
        self.failed_writer.record(listing.npsn, last_error or "Detail tidak tersedia")
        self.logger.failure(
            f"Gagal memproses NPSN {listing.npsn} setelah {MAX_DETAIL_RETRY} percobaan"
        )

    def sleep_with_jitter(self) -> None:
        """Pause execution politely between navigation hops."""

        wait_time = random.uniform(self.base_delay * 0.5, self.base_delay * 1.5)
        self.logger.wait(f"Delay {wait_time:.2f}s")
        time.sleep(wait_time)

    def _build_province_url(self, province_id: int) -> str:
        return f"{BASE_URL}?kode={province_id}"

    def _extract_links(self, rows: Iterable[Any]) -> List[Tuple[str, str]]:
        links: List[Tuple[str, str]] = []
        for row in rows:
            name, href = self._extract_link(row)
            if name and href:
                links.append((name, urljoin(BASE_URL, href)))
        return links

    @staticmethod
    def _extract_link(row: Any) -> tuple[str, str]:
        link_cells = row.find_elements("css selector", "td.link1 a")
        links = link_cells or row.find_elements("tag name", "a")
        if not links:
            return "", ""
        link = links[0]
        return link.text.strip(), link.get_attribute("href") or ""

    def summarize(self) -> dict[str, int]:
        """Return summary counters for logging at the CLI level."""

        return {
            "provinsi": self.counters["province"],
            "sekolah_baru": self.counters["school_new"],
            "sekolah_skip": self.counters["school_skip"],
            "sekolah_gagal": self.counters["school_fail"],
        }
