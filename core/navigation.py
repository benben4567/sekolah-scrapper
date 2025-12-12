"""DOM selectors and parsing helpers for the DIKMEN pages."""

from __future__ import annotations

from typing import Any

TimeoutException = None  # type: ignore
By = None  # type: ignore
EC = None  # type: ignore
WebDriverWait = None  # type: ignore

PROVINCE_TABLE_SELECTOR = "table.table-striped tbody tr"
CITY_TABLE_SELECTOR = "table.table-striped tbody tr"
DISTRICT_TABLE_SELECTOR = "table.table-striped tbody tr"
SCHOOL_TABLE_SELECTOR = "table.table-striped tbody tr"
PAGINATION_NEXT_SELECTOR = "a.paginate_button.next"
DETAIL_ROWS_SELECTOR = "div.tabby-tab:first-of-type div.tabby-content table tbody tr"
DEFAULT_TIMEOUT = 20

LABEL_MAP = {
    "nama": "nama",
    "npsn": "npsn",
    "alamat": "alamat",
    "desa/kelurahan": "desa_kel",
    "desa kelurahan": "desa_kel",
    "desa": "desa_kel",
    "kelurahan": "desa_kel",
    "kecamatan": "kecamatan",
    "kecamatan/kota (ln)": "kecamatan",
    "kabupaten": "kota_kab",
    "kab/kota": "kota_kab",
    "kab.-kota": "kota_kab",
    "kab.-kota/negara (ln)": "kota_kab",
    "kota": "kota_kab",
    "provinsi": "provinsi",
    "propinsi": "provinsi",
    "propinsi/luar negeri (ln)": "provinsi",
    "status sekolah": "status",
    "status": "status",
    "bentuk pendidikan": "bentuk",
    "bentuk": "bentuk",
}

def _require_selenium() -> None:
    global TimeoutException, By, EC, WebDriverWait
    if By is not None and WebDriverWait is not None and EC is not None:
        return

    try:
        from selenium.common.exceptions import TimeoutException as _Timeout  # type: ignore[import]
        from selenium.webdriver.common.by import By as _By  # type: ignore[import]
        from selenium.webdriver.support import expected_conditions as _EC  # type: ignore[import]
        from selenium.webdriver.support.ui import WebDriverWait as _Wait  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - triggered when selenium missing
        raise RuntimeError("Selenium must be installed to run the scraper.") from exc

    TimeoutException = _Timeout
    By = _By
    EC = _EC
    WebDriverWait = _Wait


def collect_table_rows(driver: Any, selector: str, timeout: int = DEFAULT_TIMEOUT) -> list[Any]:
    """Return all row WebElements for the supplied CSS selector."""

    _require_selenium()
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    except TimeoutException:
        return []
    return driver.find_elements(By.CSS_SELECTOR, selector)


def extract_cells(row_element: Any) -> list[Any]:
    """Return all cell elements within a table row element."""

    _require_selenium()
    cells = row_element.find_elements(By.TAG_NAME, "td")
    if cells:
        return cells
    return row_element.find_elements(By.TAG_NAME, "th")


def find_next_page(driver: Any) -> Any | None:
    """Return the clickable element for the next pagination page, if available."""

    _require_selenium()
    elements = driver.find_elements(By.CSS_SELECTOR, PAGINATION_NEXT_SELECTOR)
    for element in elements:
        classes = (element.get_attribute("class") or "").lower()
        aria_disabled = (element.get_attribute("aria-disabled") or "").lower()
        if "disabled" in classes or aria_disabled == "true":
            continue
        return element
    return None


def parse_detail_block(driver: Any, timeout: int = DEFAULT_TIMEOUT) -> dict[str, str]:
    """Parse the school detail page into a normalized dictionary."""

    _require_selenium()
    details: dict[str, str] = {}
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, DETAIL_ROWS_SELECTOR))
        )
    except TimeoutException:
        return details

    rows = driver.find_elements(By.CSS_SELECTOR, DETAIL_ROWS_SELECTOR)
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            continue
        label = cells[1].text.strip().rstrip(":").lower()
        value = cells[3].text.strip()
        key = LABEL_MAP.get(label)
        if key and value:
            details[key] = value
    return details
