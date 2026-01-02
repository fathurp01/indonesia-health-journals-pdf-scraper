BOT_NAME = "jurnal_scraping"

SPIDER_MODULES = ["jurnal_scraping.spiders"]
NEWSPIDER_MODULE = "jurnal_scraping.spiders"
ROBOTSTXT_OBEY = True
OFFSITE_ENABLED = False

CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True

DOWNLOAD_TIMEOUT = 25
RETRY_ENABLED = True
RETRY_TIMES = 6
RETRY_HTTP_CODES = [403, 408, 429, 500, 502, 503, 504, 522, 524]

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.75
AUTOTHROTTLE_MAX_DELAY = 15.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

COOKIES_ENABLED = False
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id,en;q=0.8",
}

USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

DOWNLOADER_MIDDLEWARES = {
    "jurnal_scraping.middlewares.RandomUserAgentMiddleware": 400,
    "scrapy.downloadermiddlewares.offsite.OffsiteMiddleware": None,
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
}

MAX_ITEMS = 450
MAX_PDFS = 450
ITEM_PIPELINES = {
    "jurnal_scraping.pipelines.ValidateDedupLimitPipeline": 200,
    "jurnal_scraping.pipelines.PdfDownloadPipeline": 300,
    "jurnal_scraping.pipelines.CsvAppendPipeline": 400,
}
FILES_STORE = "downloaded_pdfs"
MEDIA_ALLOW_REDIRECTS = True

# PDF filename strategy
# - False (default): pdfs/<sha1(pdf_url)>.pdf
# - True          : pdfs/<slug(title)>-<short_hash>.pdf
PDF_FILENAME_BY_TITLE = True
PDF_FILENAME_HASH_LEN = 10
PDF_FILENAME_SLUG_MAXLEN = 120

# Persist scheduler/dupefilter state for resume.
JOBDIR = "jobstate"

# Where the index CSV is written/appended.
CSV_OUTPUT = "jurnal_kesehatan_indonesia.csv"

LOG_LEVEL = "INFO"
