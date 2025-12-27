import random


class RandomUserAgentMiddleware:
    """Assigns a random User-Agent per request.

    Keeps scraping ethical: no fingerprinting/captcha bypass, just basic UA rotation.
    """

    def __init__(self, user_agents):
        self.user_agents = [ua for ua in (user_agents or []) if ua]

    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.getlist("USER_AGENT_LIST")
        return cls(user_agents)

    def process_request(self, request, spider):
        if not self.user_agents:
            return None
        if b"User-Agent" in request.headers:
            return None
        request.headers[b"User-Agent"] = random.choice(self.user_agents).encode("utf-8")
        return None
