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
        # [SEED: 2399] SEMANTIC QUERY EXPANSION ENGINE
        EXPANSION_MAP = {
            "skincare": ["beauty", "cosmetics", "dermatology", "anti-aging", "skin care", "esthetics", "aesthetics", "glow", "serum", "moisturizer"],
            "health": ["wellness", "supplements", "fitness", "nutrition", "medical", "holistic", "alternative medicine", "vitamins", "protein", "keto"],
            "fitness": ["gym", "workout", "health", "training", "weight loss", "crossfit", "yoga", "pilates", "personal trainer", "bodybuilding"],
            "marketing": ["seo", "agency", "digital marketing", "consulting", "b2b", "lead generation", "smm", "ppc", "growth hacking", "branding"],
            "ecommerce": ["shopify", "dropshipping", "boutique", "retail", "store", "d2c", "direct to consumer", "wholesale", "ecom", "online store"],
            "fashion": ["apparel", "clothing", "boutique", "streetwear", "accessories", "jewelry", "sneakers", "footwear", "menswear", "womenswear"],
            "tech": ["saas", "software", "startup", "ai", "artificial intelligence", "cloud", "cybersecurity", "fintech", "web3", "crypto"],
            "real estate": ["realtor", "mortgage", "property management", "homes for sale", "rentals", "airbnb", "vrbo", "real estate investing", "flip"],
            "food": ["restaurant", "cafe", "bakery", "catering", "meal prep", "food delivery", "snacks", "beverage", "brewery", "winery"],
            "home": ["interior design", "landscaping", "plumbing", "hvac", "roofing", "contractor", "remodeling", "decor", "furniture", "cleaning"],
            "auto": ["car dealership", "auto repair", "detailing", "tires", "motorcycle", "rv", "boat", "marine", "powersports", "car wash"],
            "education": ["tutoring", "online course", "coaching", "bootcamp", "language learning", "test prep", "certification", "edtech", "homeschool"],
            "finance": ["accounting", "bookkeeping", "tax prep", "financial advisor", "wealth management", "insurance", "loans", "credit repair", "forex"],
            "pet": ["dog grooming", "vet", "pet sitting", "dog walking", "pet food", "pet supplies", "kennel", "cattery", "animal rescue", "pet trainer"],
            "beauty": ["salon", "spa", "nail salon", "hair extensions", "lashes", "microblading", "botox", "fillers", "medspa", "tanning"]
        }
        
        queries_to_run = [query]
        q_lower = query.lower().strip()
        if q_lower in EXPANSION_MAP:
            queries_to_run.extend(EXPANSION_MAP[q_lower])
            
        seen_ids = set()
        total_yielded = 0
        hb = HumanBrowser(headless=self.headless)

        for q in queries_to_run:
            if total_yielded >= max_results:
                break
                
            url = AD_LIBRARY_URL.format(country=country, query=q.replace(" ", "%20"))
            html = ""
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
                pass

            if not html:
                continue

            extracted = self.extractor.extract_ads(html, country)
            for ad in extracted:
                if ad.id not in seen_ids:
                    seen_ids.add(ad.id)
                    yield ad
                    total_yielded += 1
                    if total_yielded >= max_results:
                        break


    def health_check(self) -> bool:
        return True
