"""CLI entry point for the DIKMEN Selenium scraper."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from argparse import ArgumentDefaultsHelpFormatter
from pathlib import Path

from selenium import webdriver  # type: ignore[import]

from core.csv_store import FailedWriter, SchoolsWriter
from core.logger import EmojiLogger
from core.scraper import DikmenScraper
from core.state import ScrapeState


DEFAULT_DELAY = 2.0


def build_parser() -> ArgumentParser:
    """Create the top-level argument parser for the scraper CLI."""

    parser = ArgumentParser(
        description=(
            "Scrape jenjang DIKMEN (SMA/SMK/MA) dari referensi.kemdikdasmen.go.id\n"
            "Flow baru: kumpulkan semua link provinsi → kota/kabupaten → kecamatan → sekolah,"
            "\nkemudian jalankan detail scraping berdasarkan antrean link tersebut."
        ),
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "resume", "province", "provinces-only"],
        default="full",
        help=(
            "full: scrape seluruh provinsi; resume: ulangi tapi skip NPSN yang sudah lengkap;"
            " province: fokus ke satu provinsi (butuh --province-id);"
            " provinces-only: hanya perbarui provinces.csv tanpa menyentuh sekolah."
        ),
    )
    parser.add_argument(
        "--province-id",
        type=int,
        help="ID provinsi (berdasarkan provinces.csv) ketika mode=province",
    )
    parser.add_argument(
        "--start-province-id",
        type=int,
        help="Start scraping from a specific province ID (inclusive)",
    )
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="Base delay (seconds) between page interactions",
    )
    parser.add_argument(
        "--recheck-incomplete",
        action="store_true",
        help=(
            "Hapus baris sekolah yang kolom wajibnya kosong, lalu scrape ulang detail"
            " untuk NPSN tersebut (berguna memperbaiki data tidak lengkap)."
        ),
    )
    return parser


def parse_args() -> Namespace:
    """Parse CLI arguments and apply basic validation."""

    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "province" and args.province_id is None:
        parser.error("--province-id is required when --mode=province")

    return args


def build_driver(headless: bool) -> webdriver.Chrome:
    """Instantiate a Chrome webdriver with optional headless mode."""

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,720")
    return webdriver.Chrome(options=options)


def main() -> None:
    """Bootstrap dependencies and dispatch the requested scraping mode."""

    args = parse_args()
    logger = EmojiLogger()
    logger.start(
        f"Mulai scraping DIKMEN mode={args.mode} headless={args.headless} delay={args.delay}"
    )

    base_dir = Path(__file__).parent
    provinces_csv = base_dir / "provinces.csv"
    schools_csv = base_dir / "schools.csv"
    failed_csv = base_dir / "failed_npsn.csv"

    exit_code = 0
    driver = None
    try:
        driver = build_driver(args.headless)
        state = ScrapeState(recheck_incomplete=args.recheck_incomplete)
        removed_incomplete = state.load_existing_schools(schools_csv)
        if removed_incomplete:
            logger.warn(
                "warn",
                f"Hapus {removed_incomplete} baris sekolah tidak lengkap; akan di-scrape ulang",
            )
        schools_writer = SchoolsWriter(schools_csv, state)
        failed_writer = FailedWriter(failed_csv)
        scraper = DikmenScraper(driver, logger, state, schools_writer, failed_writer, args.delay)

        if args.mode == "provinces-only":
            provinces = scraper.scrape_provinces_if_needed(str(provinces_csv))
            logger.start(
                f"Berhasil memperbarui {len(provinces)} provinsi ke {provinces_csv.name}"
            )
            return

        state.ensure_provinces(scraper, provinces_csv)
        scraper.scrape_all_provinces(
            mode=args.mode,
            start_id=args.start_province_id,
            single_province_id=args.province_id,
        )

        summary = scraper.summarize()
        logger.start("Ringkasan scraping:")
        for key, value in summary.items():
            logger.info("info", f"{key}: {value}")

    except KeyboardInterrupt:
        exit_code = 130
        logger.warn("warn", "Scraper dihentikan pengguna. Buffer akan disimpan.")
    except Exception as exc:  # pragma: no cover - CLI safeguard
        exit_code = 1
        logger.failure(f"Scraper gagal: {exc}")
    finally:
        if driver is not None:
            try:
                flushed = schools_writer.flush_all() if 'schools_writer' in locals() else 0
                if flushed:
                    logger.save(
                        f"Flush {flushed} record ke schools.csv (total: {schools_writer.total_written})"
                    )
            finally:
                driver.quit()

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
