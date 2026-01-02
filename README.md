## Journal Scraping (Indonesia - Health/Medical)

Scrapy project to collect Indonesian-language **health/medical** article records from DOAJ and automatically download the **PDF full text** (when available).

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

Set the total PDF target (override default) and continue without duplicates:
```bash
scrapy crawl doaj_kesehatan_id -s MAX_PDFS=800
```

Toggle PDF filename strategy:
- Use article title (slug) + short hash suffix:
	```bash
	scrapy crawl doaj_kesehatan_id -s PDF_FILENAME_BY_TITLE=True
	```
- Use full hash filename (stable from URL):
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

### Resume / cross-run de-duplication
- `jurnal_kesehatan_indonesia.csv` is used as an **index/progress file**: on startup, the crawler reads this CSV to
	avoid duplicates and count how many PDFs already exist on disk.
- Scheduler state is also stored in `jobstate/` (Scrapy `JOBDIR`) to support resuming after an interruption.
- If you already reached a previous target and want to extend it (e.g. 450 → 800), rerun with `-s MAX_PDFS=800`.

### Default target
- Current default target: **450 PDFs** (see `MAX_PDFS` in `jurnal_scraping/settings.py`).

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