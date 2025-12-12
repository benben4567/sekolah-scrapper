"""State management helpers for DIKMEN scraping sessions."""

from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_SCHOOL_FIELDS = [
    "province_id",
    "nama",
    "npsn",
    "alamat",
    "desa_kel",
    "kecamatan",
    "kota_kab",
    "provinsi",
    "status",
    "bentuk",
]


class ScrapeState:
    """Track provinces, existing NPSN entries, and auto-increment IDs."""

    def __init__(self, recheck_incomplete: bool = False) -> None:
        self.provinces: list[dict[str, str]] = []
        self.existing_npsn: set[str] = set()
        self.incomplete_npsn: set[str] = set()
        self._next_school_id: int = 1
        self.recheck_incomplete = recheck_incomplete

    def load_existing_schools(self, schools_csv: Path) -> int:
        """Load schools.csv to seed next ID and populate the NPSN set."""

        if not schools_csv.exists():
            return 0

        with schools_csv.open(newline="", encoding="utf-8") as handle:
            reader = list(csv.DictReader(handle))

        removed = 0
        rows = reader
        if self.recheck_incomplete and rows:
            rows, removed = self._prune_incomplete_rows(rows, schools_csv)

        max_id = 0
        for row in rows:
            npsn = (row.get("npsn") or "").strip()
            if npsn:
                self.existing_npsn.add(npsn)
            try:
                row_id = int((row.get("id") or "0"))
            except ValueError:
                row_id = 0
            if row_id > max_id:
                max_id = row_id
        self._next_school_id = max_id + 1 if max_id else 1
        return removed

    def load_provinces(self, provinces_csv: Path) -> None:
        """Load provinces.csv to fill the in-memory list."""

        from . import csv_store

        self.provinces = csv_store.load_provinces(provinces_csv)

    def ensure_provinces(self, scraper: "DikmenScraper", provinces_csv: Path) -> None:  # type: ignore[name-defined]
        """Ensure provinces list is available, triggering scraping if missing."""

        if self.provinces:
            return

        provinces = scraper.scrape_provinces_if_needed(str(provinces_csv))
        if provinces:
            self.provinces = provinces
            return

        if provinces_csv.exists():
            self.load_provinces(provinces_csv)
            if self.provinces:
                return

        raise RuntimeError("Gagal memuat daftar provinsi dari sumber mana pun.")

    def should_skip(self, npsn: str) -> bool:
        """Return True if the NPSN has already been scraped."""

        if npsn in self.incomplete_npsn:
            return False
        return npsn in self.existing_npsn

    def register_school(self, npsn: str) -> None:
        """Track the NPSN as processed to avoid duplicates in the same run."""

        if npsn:
            if npsn in self.incomplete_npsn:
                self.incomplete_npsn.remove(npsn)
            self.existing_npsn.add(npsn)

    def get_next_school_id(self) -> int:
        """Provide the next global school ID and increment the counter."""

        next_id = self._next_school_id
        self._next_school_id += 1
        return next_id

    def _prune_incomplete_rows(
        self, rows: list[dict[str, str]], schools_csv: Path
    ) -> tuple[list[dict[str, str]], int]:
        from .csv_store import SCHOOL_FIELDNAMES

        filtered: list[dict[str, str]] = []
        removed = 0
        for row in rows:
            npsn = (row.get("npsn") or "").strip()
            if not npsn:
                removed += 1
                continue
            if self._is_row_complete(row):
                filtered.append(row)
            else:
                self.incomplete_npsn.add(npsn)
                removed += 1

        if removed:
            schools_csv.parent.mkdir(parents=True, exist_ok=True)
            with schools_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=SCHOOL_FIELDNAMES)
                writer.writeheader()
                writer.writerows(filtered)

        return filtered, removed

    def _is_row_complete(self, row: dict[str, str]) -> bool:
        for field in REQUIRED_SCHOOL_FIELDS:
            if not (row.get(field) or "").strip():
                return False
        return True
