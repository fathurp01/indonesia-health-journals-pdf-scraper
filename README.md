## Journal Scraping (Indonesia - Health/Medical)

Scrapy project to collect Indonesian-language **health/medical** article records from DOAJ and automatically download the **PDF fulltext** (when available).

### What you get
- CSV index: `jurnal_kesehatan_indonesia.csv` (UTF-8)
- PDFs downloaded to: `downloaded_pdfs/pdfs/`

### Install
```bash
python -m pip install -r requirements.txt
```

### Run
```bash
scrapy crawl doaj_kesehatan_id
```

Set jumlah total PDF (override default) dan lanjut tanpa duplikasi:
```bash
scrapy crawl doaj_kesehatan_id -s MAX_PDFS=800
```

Toggle penamaan file PDF:
- Default (judul artikel + suffix hash pendek):
	```bash
	scrapy crawl doaj_kesehatan_id -s PDF_FILENAME_BY_TITLE=True
	```
- Kembali ke nama hash penuh (stabil dari URL):
	```bash
	scrapy crawl doaj_kesehatan_id -s PDF_FILENAME_BY_TITLE=False
	```

Optional (more logs):
```bash
scrapy crawl doaj_kesehatan_id -s LOG_LEVEL=INFO
```

### Output fields (CSV)
- `journal_title`
- `title`
- `authors`
- `affiliation`
- `abstract`
- `pdf_url`
- `pdf_local_path`
- `source_url`

### How “exactly N PDFs” is enforced
- Records must pass:
	- Indonesian language detection (`langdetect`) on abstract
	- Health/medical keyword filter on title+abstract
	- Must have a resolvable PDF URL
- PDFs are downloaded via Scrapy `FilesPipeline`.
- Crawl stops automatically after **N successful PDF downloads** (`MAX_PDFS`).

### Resume / anti-duplikasi lintas-run
- `jurnal_kesehatan_indonesia.csv` dipakai sebagai **index/progress**: saat start, spider membaca CSV ini untuk
	menghindari duplikasi dan menghitung berapa PDF yang sudah ada di disk.
- Scheduler state juga disimpan di `jobstate/` (Scrapy `JOBDIR`) agar bisa resume jika proses terhenti.
- Kalau kamu sudah punya target sebelumnya lalu ingin menaikkan target (mis. 450 → 800), cukup jalankan ulang dengan `-s MAX_PDFS=800`.

### Default target
- Default target saat ini: **450 PDF** (lihat `MAX_PDFS` di `jurnal_scraping/settings.py`).

### Stability & ethics
- Obeys `robots.txt`
- Random User-Agent rotation
- AutoThrottle enabled
- Retries + timeouts enabled
- No captcha bypass, no login brute-force, no JS automation

### Rerun cleanly
Delete these if you want a fresh run:
- `downloaded_pdfs/`
- `jurnal_kesehatan_indonesia.csv`
- `jobstate/`