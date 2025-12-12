# Sekolah Scraper (DIKMEN)

Scraper berbasis Python + Selenium untuk mengambil data sekolah jenjang DIKMEN (SMA/SMK/MA/MAK) dari laman referensi resmi Kemendikbud `https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen`.

## Fitur Utama

- Navigasi bertahap (provinsi → kab/kota → kecamatan → sekolah) dengan antrean link sehingga mudah dipantau dan diulang.
- Penulisan data ke `provinces.csv` dan `schools.csv` dengan buffer dan auto-increment ID.
- Mode `resume` + deduplikasi NPSN agar aman dijalankan berkali-kali.
- Mode `--recheck-incomplete` otomatis menghapus baris sekolah yang kolom wajibnya kosong lalu scrape ulang detailnya.
- Logging beremoji untuk setiap tahapan (provinsi, kota, kecamatan, sekolah, flush buffer, dll.).

## Persiapan Lingkungan

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Pastikan sudah memasang Chrome/Chromium dan driver yang kompatibel.

## Cara Menjalankan

```bash
python scraper.py --mode full --headless
```

## System Requirements

| Komponen | Windows | macOS | Linux |
| --- | --- | --- | --- |
| OS | Windows 10/11 64-bit | macOS 12+ (Intel/Apple Silicon) | Distribusi modern (Ubuntu 20.04+, Debian 11+, Fedora 38+, dll.) |
| Python | Python 3.9+ (disarankan 3.11) | Python 3.9+ (via Xcode CLT/Homebrew) | Python 3.9+ (paket distro/pyenv) |
| Browser | Chrome/Chromium terbaru | Chrome/Chromium terbaru | Chrome/Chromium terbaru |
| Driver | ChromeDriver kompatibel (biasanya otomatis dari selenium>=4) | ChromeDriver kompatibel | ChromeDriver kompatibel |
| Dependensi | `pip install -r requirements.txt` | sama | sama |
| Lainnya | PowerShell/CMD untuk CLI | Terminal (zsh/bash) | Terminal (bash/zsh) |

Catatan: Selenium 4.39+ otomatis mengelola driver Chrome selama browser yang terpasang sesuai versi. Jika memakai driver manual, pastikan executable dapat diakses (misal `chromedriver.exe` di PATH Windows, atau `/usr/local/bin/chromedriver` di macOS/Linux).

### Opsi CLI

| Argumen | Deskripsi |
| --- | --- |
| `--mode {full,resume,province}` | `full`: semua provinsi; `resume`: ulangi tapi skip NPSN yang sudah lengkap; `province`: hanya satu provinsi (butuh `--province-id`). |
| `--province-id <int>` | ID provinsi sesuai `provinces.csv` saat `--mode province`. |
| `--start-province-id <int>` | Mulai scraping dari provinsi tertentu (berguna untuk melanjutkan manual). |
| `--headless` | Menjalankan Chrome dalam mode headless. |
| `--delay <float>` | Delay dasar antar navigasi (default 2 detik, ada jitter ±50%). |
| `--recheck-incomplete` | Hapus baris sekolah yang kolom wajibnya kosong dari `schools.csv`, lalu scrape ulang detail untuk NPSN tersebut. |

Contoh lain:

```bash
python scraper.py --mode resume --headless
python scraper.py --mode province --province-id 11 --headless
python scraper.py --mode full --headless --recheck-incomplete
```

## Struktur Folder

```
scraper.py              # Entry point CLI
core/
  ├── logger.py         # Emoji logger & helper
  ├── state.py          # State + dedupe NPSN + recheck-incomplete
  ├── csv_store.py      # Utilities tulis/baca CSV & buffered writer
  ├── navigation.py     # Selector & parsing helper (Selenium)
  └── scraper.py        # Orkestrasi Selenium + antrean link
requirements.txt        # Dependency (Selenium)
.gitignore
README.md
```

## Output CSV

- `provinces.csv`: kolom `id`, `nama`.
- `schools.csv`: `id`, `province_id`, `nama`, `npsn`, `alamat`, `desa_kel`, `kecamatan`, `kota_kab`, `provinsi`, `status`, `bentuk`.
- `failed_npsn.csv`: catatan NPSN yang gagal (timestamp, npsn, reason).

## Catatan Tambahan

- Jangan menjalankan beberapa instance scraper secara paralel terhadap CSV yang sama.
- Jika scraping dihentikan paksa (Ctrl+C), buffer akan di-flush sebelum browser ditutup.
- Gunakan `--recheck-incomplete` saat menemukan baris awal `schools.csv` yang belum lengkap.
- Penggunaan Selenium harus sopan: delay default + jitter sudah disiapkan, jangan menurunkan delay drastis.
