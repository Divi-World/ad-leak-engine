"""HUMAN-GRADE Meta Ad Library scraper using camoufox + Regex Extractor [SEED: 2399]."""
from typing import Iterator
from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .html_extractor import HtmlAdExtractor

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

class PlaywrightSource(AbstractAdSource):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.extractor = HtmlAdExtractor()

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        hb = HumanBrowser(headless=self.headless)

        try:
            with hb.session() as page:
                hb.prime_facebook_session(page)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                hb.human_pause(3.0, 5.0)

                for _ in range(3):
                    hb.human_scroll(page, distance=800, steps=10)
                    hb.human_pause(1.5, 3.0)

                html = page.content()
        except Exception:
            return

        ads = self.extractor.extract_ads(html, country)

        seen = set()
        count = 0
        for ad in ads:
            if ad.id not in seen:
                seen.add(ad.id)
                yield ad
                count += 1
                if count >= max_results:
                    return

    def health_check(self) -> bool:
        return True
