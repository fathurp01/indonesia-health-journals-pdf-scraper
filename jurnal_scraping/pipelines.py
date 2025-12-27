from __future__ import annotations

import hashlib
import re

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

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

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

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = super().from_crawler(crawler)
        pipeline.max_pdfs = crawler.settings.getint(
            "MAX_PDFS", crawler.settings.getint("MAX_ITEMS", 400)
        )
        pipeline.downloaded_ok = 0
        pipeline.in_progress = set()
        return pipeline

    def open_spider(self, spider):
        super().open_spider(spider)
        self._spider = spider

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
