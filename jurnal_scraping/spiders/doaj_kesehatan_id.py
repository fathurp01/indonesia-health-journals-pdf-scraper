from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

import scrapy

from jurnal_scraping.items import JournalArticleItem


class DoajKesehatanIndonesiaSpider(scrapy.Spider):
    name = "doaj_kesehatan_id"
    allowed_domains = ["doaj.org"]

    custom_settings = {
        "DOWNLOAD_FAIL_ON_DATALOSS": False,
    }

    page_size = 100

    health_keywords = (
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

    keyword_queries = (
        "kesehatan",
        "kedokteran",
        "keperawatan",
        "farmasi",
        "gizi",
        "klinis",
        "medis",
        '"kesehatan masyarakat"',
        '"rumah sakit"',
    )

    def start_requests(self):
        for query in self.keyword_queries:
            yield self._make_search_request(query=query, page=1)

    def _make_search_request(self, query: str, page: int) -> scrapy.Request:
        url = (
            "https://doaj.org/api/v2/search/articles/"
            + quote_plus(query)
            + f"?page={page}&pageSize={self.page_size}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_search,
            errback=self.errback_log,
            meta={
                "query": query,
                "page": page,
                # Let callback see non-200 so we can log status/body.
                "handle_httpstatus_list": [400, 401, 403, 404, 429, 500, 502, 503, 504],
            },
        )

    def parse_search(self, response: scrapy.http.Response):
        if response.status != 200:
            body_prefix = response.text[:250].replace("\n", " ").replace("\r", " ")
            self.logger.warning(
                "Non-200 from DOAJ (status=%s, query=%r, page=%s): %s | body=%r",
                response.status,
                response.meta.get("query"),
                response.meta.get("page"),
                response.url,
                body_prefix,
            )
            return

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning("JSON decode failed for %s", response.url)
            return

        results = payload.get("results") or []
        if not results:
            return

        query = response.meta.get("query")
        page = int(response.meta.get("page") or 1)
        if query:
            yield self._make_search_request(query=query, page=page + 1)

        for record in results:
            item = self._record_to_item(record)
            if not item:
                continue

            pdf_url = (item.get("pdf_url") or "").strip()
            if pdf_url and pdf_url.lower().endswith(".pdf"):
                item["pdf_url"] = pdf_url
                item["file_urls"] = [pdf_url]
                yield item
                continue

            landing_url = (item.get("landing_url") or "").strip()
            if landing_url:
                yield scrapy.Request(
                    landing_url,
                    callback=self.parse_landing,
                    errback=self.errback_log,
                    meta={
                        "item": item,
                        "handle_httpstatus_list": [400, 401, 403, 404, 429, 500, 502, 503, 504],
                    },
                )

    def _record_to_item(self, record: dict[str, Any]) -> JournalArticleItem | None:
        bib = record.get("bibjson") or {}

        title = self._pick_first_string(bib.get("title"))
        abstract = self._pick_first_string(bib.get("abstract"))

        if not title or not abstract:
            return None

        # lightweight pre-filter to reduce downstream work
        haystack = f"{title} {abstract}".lower()
        if not any(k in haystack for k in self.health_keywords):
            return None

        journal = bib.get("journal") or {}
        journal_title = self._pick_first_string(journal.get("title"))

        authors_list = bib.get("author") or []
        authors = []
        affiliations = []
        for a in authors_list:
            name = self._pick_first_string(a.get("name"))
            if name:
                authors.append(name)
            aff = self._pick_first_string(a.get("affiliation"))
            if aff:
                affiliations.append(aff)

        links = bib.get("link") or []
        pdf_url = self._extract_pdf_url(links)
        landing_url = self._extract_fulltext_url(links)
        source_url = self._extract_source_url(record, links)

        item = JournalArticleItem(
            journal_title=(journal_title or ""),
            title=title,
            authors=", ".join(self._dedup_keep_order(authors)),
            affiliation="; ".join(self._dedup_keep_order(affiliations)) or "",
            abstract=abstract,
            pdf_url=pdf_url or "",
            landing_url=landing_url or "",
            file_urls=[pdf_url] if (pdf_url or "").lower().endswith(".pdf") else [],
            source_url=source_url or "",
        )
        return item

    def parse_landing(self, response: scrapy.http.Response):
        item: JournalArticleItem = response.meta["item"]
        if response.status != 200:
            return

        ctype = (response.headers.get(b"Content-Type") or b"").decode("utf-8", errors="ignore")
        if "pdf" in ctype.lower() or response.url.lower().endswith(".pdf"):
            item["pdf_url"] = response.url
            item["file_urls"] = [response.url]
            yield item
            return

        pdf_url = self._find_pdf_url_in_landing(response)
        if pdf_url:
            item["pdf_url"] = pdf_url
            item["file_urls"] = [pdf_url]
        else:
            item["pdf_url"] = ""
            item["file_urls"] = []

        yield item

    def errback_log(self, failure):
        response = getattr(failure.value, "response", None)
        if response is not None:
            self.logger.warning(
                "Request failed (status=%s, url=%s): %s",
                response.status,
                response.url,
                failure,
            )
        else:
            self.logger.warning("Request failed (no response): %s", failure)

    @staticmethod
    def _pick_first_string(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        if isinstance(value, list):
            for v in value:
                if isinstance(v, str) and v.strip():
                    return re.sub(r"\s+", " ", v).strip()
        return ""

    @staticmethod
    def _extract_pdf_url(links: list[dict[str, Any]]) -> str:
        for link in links:
            url = (link.get("url") or "").strip()
            if not url:
                continue
            ltype = (link.get("type") or "").lower()
            if "fulltext" in ltype and url.lower().endswith(".pdf"):
                return url
        for link in links:
            url = (link.get("url") or "").strip()
            if url and url.lower().endswith(".pdf"):
                return url
        return ""

    @staticmethod
    def _extract_fulltext_url(links: list[dict[str, Any]]) -> str:
        for link in links:
            url = (link.get("url") or "").strip()
            if not url:
                continue
            ltype = (link.get("type") or "").lower()
            if "fulltext" in ltype:
                return url
        # Fallback: any link
        for link in links:
            url = (link.get("url") or "").strip()
            if url:
                return url
        return ""

    @staticmethod
    def _find_pdf_url_in_landing(response: scrapy.http.Response) -> str:
        meta_pdf = response.css('meta[name="citation_pdf_url"]::attr(content)').get()
        if meta_pdf and meta_pdf.strip():
            return response.urljoin(meta_pdf.strip())

        hrefs = response.css("a::attr(href)").getall()
        hrefs = [h.strip() for h in hrefs if h and h.strip() and not h.strip().lower().startswith("javascript:")]

        for h in hrefs:
            if ".pdf" in h.lower():
                return response.urljoin(h)

        for h in hrefs:
            hl = h.lower()
            if "pdf" in hl or "download" in hl:
                return response.urljoin(h)

        return ""

    @staticmethod
    def _extract_source_url(record: dict[str, Any], links: list[dict[str, Any]]) -> str:
        # Prefer DOAJ record url if present, else fallback to first link
        for key in ("id",):
            if record.get(key):
                # DOAJ UI URL (public page)
                return f"https://doaj.org/article/{record.get(key)}"
        for link in links:
            url = (link.get("url") or "").strip()
            if url:
                return url
        return ""

    @staticmethod
    def _dedup_keep_order(values: list[str]) -> list[str]:
        seen = set()
        out = []
        for v in values:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out
