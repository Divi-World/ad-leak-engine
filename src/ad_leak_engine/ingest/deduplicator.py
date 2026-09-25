"""In-memory ad deduplication."""
from ..shared.schemas import RawAd

class Deduplicator:
    def __init__(self):
        self.seen_ids = set()

    def filter_new(self, ads: list[RawAd]) -> list[RawAd]:
        new_ads = []
        for ad in ads:
            if ad.id not in self.seen_ids:
                self.seen_ids.add(ad.id)
                new_ads.append(ad)
        return new_ads
