from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path

from langdetect import DetectorFactory, LangDetectException, detect
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.files import FileException
from scrapy import Request
from scrapy.exceptions import DropItem


DetectorFactory.seed = 42


_HEALTH_KEYWORDS: tuple[str, ...] = (
    "kesehatan",
    "medis",
    "kedokteran",
    "keperawatan",
    "farmasi",
    "kesehatan masyarakat",
    "gizi",
    "klinis",
    "rumah sakit",
)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _slugify_filename(value: str, *, maxlen: int = 120) -> str:
    text = (value or "").strip().lower()
    # Keep ASCII letters/digits; replace anything else with hyphen.
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return ""
    text = text[: max(1, int(maxlen))].rstrip("- ")
    # Windows-safe: avoid trailing dots/spaces.
    return text.strip(". ")


def _looks_health_related(title: str, abstract: str) -> bool:
    text = f"{title} {abstract}".lower()
    return any(k in text for k in _HEALTH_KEYWORDS)


class ValidateDedupLimitPipeline:
    """Validate required fields, filter health+Indonesian, deduplicate.

    For the "PDF-only" use case, we also require a PDF URL so the downloader
    pipeline can fetch full documents.
    """

    def __init__(self):
        self.seen: set[str] = set()
        self.existing_ok = 0
        self._files_store: str | None = None
        self._csv_path: str | None = None

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline._files_store = crawler.settings.get("FILES_STORE")
        pipeline._csv_path = crawler.settings.get("CSV_OUTPUT", "jurnal_kesehatan_indonesia.csv")
        return pipeline

    def open_spider(self, spider):
        csv_path = self._csv_path or "jurnal_kesehatan_indonesia.csv"
        if not os.path.exists(csv_path):
            spider.jurnal_existing_ok = 0
            spider.jurnal_seen = set()
            return

        files_store = self._files_store or "downloaded_pdfs"
        store_root = Path(files_store)

        seen: set[str] = set()
        existing_ok = 0
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pdf_url = _normalize_spaces(row.get("pdf_url", ""))
                    source_url = _normalize_spaces(row.get("source_url", ""))
                    title = _normalize_spaces(row.get("title", ""))
                    pdf_local_path = _normalize_spaces(row.get("pdf_local_path", ""))

                    if pdf_url or source_url or title:
                        dedup_key = (pdf_url or source_url or "") + "|" + (title.lower() if title else "")
                        seen.add(dedup_key)

                    if pdf_local_path:
                        candidate = store_root / pdf_local_path
                        if candidate.exists():
                            existing_ok += 1
        except Exception as e:
            spider.logger.warning("Failed loading existing CSV state (%s): %s", csv_path, e)

        self.seen |= seen
        self.existing_ok = existing_ok
        spider.jurnal_existing_ok = existing_ok
        spider.jurnal_seen = set(self.seen)

    def process_item(self, item, spider):
        title = _normalize_spaces(item.get("title", ""))
        abstract = _normalize_spaces(item.get("abstract", ""))
        source_url = _normalize_spaces(item.get("source_url", ""))
        pdf_url = _normalize_spaces(item.get("pdf_url", ""))

        if not title or not abstract:
            raise DropItem("missing_title_or_abstract")

        # User requirement: keep only items that have a PDF link (full document).
        if not pdf_url:
            raise DropItem("missing_pdf_url")

        if not _looks_health_related(title, abstract):
            raise DropItem("non_health_article")

        try:
            lang = detect(abstract)
        except LangDetectException:
            raise DropItem("langdetect_failed")

        if lang != "id":
            raise DropItem(f"non_indonesian_lang:{lang}")

        # Prefer PDF URL for deduplication when available.
        dedup_key = (pdf_url or source_url or "") + "|" + title.lower()
        if dedup_key in self.seen:
            raise DropItem("duplicate")
        self.seen.add(dedup_key)

        item["title"] = title
        item["abstract"] = abstract
        item["source_url"] = source_url
        item["pdf_url"] = pdf_url

        return item


class PdfDownloadPipeline(FilesPipeline):
    """Download PDFs and stop after EXACTLY MAX_PDFS successful downloads."""

    def __init__(self, store_uri, settings=None, *, crawler=None):
        super().__init__(store_uri, settings=settings, crawler=crawler)
        self.max_pdfs = 400
        self.downloaded_ok = 0
        self.in_progress: set[str] = set()
        self._spider = None
        self.pdf_filename_by_title = False
        self.pdf_filename_hash_len = 10
        self.pdf_filename_slug_maxlen = 120

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = super().from_crawler(crawler)
        pipeline.max_pdfs = crawler.settings.getint(
            "MAX_PDFS", crawler.settings.getint("MAX_ITEMS", 400)
        )
        pipeline.pdf_filename_by_title = crawler.settings.getbool(
            "PDF_FILENAME_BY_TITLE", False
        )
        pipeline.pdf_filename_hash_len = crawler.settings.getint(
            "PDF_FILENAME_HASH_LEN", 10
        )
        pipeline.pdf_filename_slug_maxlen = crawler.settings.getint(
            "PDF_FILENAME_SLUG_MAXLEN", 120
        )
        pipeline.downloaded_ok = 0
        pipeline.in_progress = set()
        return pipeline

    def open_spider(self, spider):
        super().open_spider(spider)
        self._spider = spider

        # Resume support: count PDFs already present from existing CSV rows.
        existing_ok = int(getattr(spider, "jurnal_existing_ok", 0) or 0)
        self.downloaded_ok = existing_ok
        if self.downloaded_ok >= self.max_pdfs and self._spider is not None:
            self._spider.crawler.engine.close_spider(
                self._spider, reason=f"already_reached_{self.max_pdfs}_pdfs"
            )

    def close_spider(self, spider):
        super().close_spider(spider)

    def get_media_requests(self, item, info):
        pdf_url = (item.get("pdf_url") or "").strip()
        if not pdf_url:
            raise DropItem("missing_pdf_url")

        if self.downloaded_ok + len(self.in_progress) >= self.max_pdfs:
            raise DropItem("pdf_limit_reached")

        self.in_progress.add(pdf_url)
        # Use GET (not HEAD) because we want the file.
        yield Request(
            pdf_url,
            dont_filter=True,
            headers={"Accept": "application/pdf,*/*;q=0.9"},
        )

    def file_path(self, request, response=None, info=None, *, item=None):
        url = request.url
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()

        if self.pdf_filename_by_title and item is not None:
            title = _normalize_spaces(item.get("title", ""))
            slug = _slugify_filename(title, maxlen=self.pdf_filename_slug_maxlen)
            if slug:
                short_hash = digest[: max(6, min(int(self.pdf_filename_hash_len), 40))]
                return f"pdfs/{slug}-{short_hash}.pdf"

        return f"pdfs/{digest}.pdf"

    def media_downloaded(self, response, request, info, *, item=None):
        ctype = (response.headers.get(b"Content-Type") or b"").decode(
            "utf-8", errors="ignore"
        )
        if "pdf" not in ctype.lower() and not request.url.lower().endswith(".pdf"):
            raise FileException(f"not_a_pdf_content_type:{ctype}")
        return super().media_downloaded(response, request, info, item=item)

    def item_completed(self, results, item, info):
        pdf_url = (item.get("pdf_url") or "").strip()
        if pdf_url in self.in_progress:
            self.in_progress.discard(pdf_url)

        ok_files = [x for ok, x in results if ok]
        if not ok_files:
            raise DropItem("pdf_download_failed")

        # Use first downloaded file.
        item["pdf_local_path"] = ok_files[0].get("path", "")
        item["files"] = ok_files
        item["file_urls"] = [pdf_url]

        self.downloaded_ok += 1
        if self.downloaded_ok == self.max_pdfs:
            if self._spider is not None:
                self._spider.crawler.engine.close_spider(
                    self._spider, reason=f"reached_{self.max_pdfs}_pdfs"
                )
        if self.downloaded_ok > self.max_pdfs:
            raise DropItem("over_pdf_limit")

        return item


class CsvAppendPipeline:
    """Append a stable CSV index after a PDF download succeeds."""

    fieldnames = [
        "journal_title",
        "title",
        "authors",
        "affiliation",
        "abstract",
        "pdf_url",
        "pdf_local_path",
        "source_url",
    ]

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._file = None
        self._writer: csv.DictWriter | None = None

    @classmethod
    def from_crawler(cls, crawler):
        csv_path = crawler.settings.get("CSV_OUTPUT", "jurnal_kesehatan_indonesia.csv")
        return cls(csv_path=csv_path)

    def open_spider(self, spider):
        file_exists = os.path.exists(self.csv_path)
        self._file = open(self.csv_path, "a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)

        # Write header only if the file is new/empty.
        if (not file_exists) or os.path.getsize(self.csv_path) == 0:
            self._writer.writeheader()

    def close_spider(self, spider):
        if self._file is not None:
            self._file.close()
        self._file = None
        self._writer = None

    def process_item(self, item, spider):
        if not self._writer:
            return item

        row = {k: (item.get(k, "") or "") for k in self.fieldnames}
        self._writer.writerow(row)
        return item
