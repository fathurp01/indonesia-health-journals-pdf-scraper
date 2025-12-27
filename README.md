## Journal Scraping (Indonesia - Health/Medical)

Scrapy project to collect **exactly 400** Indonesian-language **health/medical** journal records and automatically download the **PDF fulltext** (when available).

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

### How “exactly 400 PDFs” is enforced
- Records must pass:
	- Indonesian language detection (`langdetect`) on abstract
	- Health/medical keyword filter on title+abstract
	- Must have a resolvable PDF URL
- PDFs are downloaded via Scrapy `FilesPipeline`.
- Crawl stops automatically after **400 successful PDF downloads**.

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