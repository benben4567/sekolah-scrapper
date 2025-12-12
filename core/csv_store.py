"""CSV helpers for provinces, schools, and failure reporting."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROVINCE_FIELDNAMES = ["id", "nama"]
SCHOOL_FIELDNAMES = [
    "id",
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


def load_provinces(csv_path: Path) -> list[dict[str, str]]:
    """Return a list of provinces loaded from provinces.csv."""

    if not csv_path.exists():
        return []

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if row.get("id") and row.get("nama")]


def write_provinces(csv_path: Path, provinces: Iterable[dict[str, str]]) -> None:
    """Persist the provinces list to provinces.csv with a header."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROVINCE_FIELDNAMES)
        writer.writeheader()
        for row in provinces:
            writer.writerow({"id": row.get("id"), "nama": row.get("nama")})


class SchoolsWriter:
    """Buffered writer that appends school rows to schools.csv."""

    def __init__(self, csv_path: Path, state: "ScrapeState", buffer_size: int = 50):  # type: ignore[name-defined]
        self.csv_path = csv_path
        self.state = state
        self.buffer_size = buffer_size
        self.buffer: list[dict[str, str]] = []
        self.total_written = 0
        self._ensure_header()

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCHOOL_FIELDNAMES)
            writer.writeheader()

    def append_school(self, record: dict[str, str]) -> None:
        """Queue a school record for persistence, auto-assigning the ID."""

        row = {field: record.get(field, "") for field in SCHOOL_FIELDNAMES}
        row["id"] = str(self.state.get_next_school_id())
        self.buffer.append(row)

    def flush_if_needed(self) -> int:
        """Flush the buffer when it reaches the configured capacity."""

        if len(self.buffer) >= self.buffer_size:
            return self._flush_buffer()
        return 0

    def flush_all(self) -> int:
        """Force a flush of any remaining buffered records."""

        if self.buffer:
            return self._flush_buffer()
        return 0

    def _flush_buffer(self) -> int:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        count = len(self.buffer)
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCHOOL_FIELDNAMES)
            writer.writerows(self.buffer)
        self.buffer.clear()
        self.total_written += count
        return count


class FailedWriter:
    """Simple writer that captures NPSN values that failed to scrape."""

    FIELDNAMES = ["timestamp", "npsn", "reason"]

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self._ensure_header()

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
            writer.writeheader()

    def record(self, npsn: str, reason: str) -> None:
        """Append a failure row with the NPSN and explanation."""

        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
            writer.writerow(
                {
                    "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
                    "npsn": npsn,
                    "reason": reason,
                }
            )
