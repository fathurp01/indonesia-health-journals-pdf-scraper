import scrapy


class JournalArticleItem(scrapy.Item):
    journal_title = scrapy.Field()
    title = scrapy.Field()
    authors = scrapy.Field()  # comma-separated
    affiliation = scrapy.Field()  # semicolon-separated (best effort)
    abstract = scrapy.Field()
    pdf_url = scrapy.Field()
    pdf_local_path = scrapy.Field()  # where the downloaded PDF is stored
    landing_url = scrapy.Field()
    file_urls = scrapy.Field()
    files = scrapy.Field()
    source_url = scrapy.Field()

    # Used by Scrapy FilesPipeline
    file_urls = scrapy.Field()
    files = scrapy.Field()
