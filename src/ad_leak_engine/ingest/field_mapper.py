"""Adaptive field mapper for Meta Ad Library GraphQL responses [SEED: 2399].

Uses multiple extraction strategies so it survives Meta schema variation:
  Strategy 1: GraphQL Relay `nodes[]` arrays
  Strategy 2: any list of ad-like dicts
"""
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad


class AdLibraryFieldMapper:
    AD_ID_KEYS = ["ad_archive_id", "id", "ad_id", "archive_id"]
    AD_HINT_KEYS = ["snapshot", "collation_count", "ad_delivery_start_time", "page"]

    def extract_ads(self, payload, country: str) -> list[RawAd]:
        ads = []
        seen = set()
        for node in self._iter_ad_nodes(payload):
            ad = self._node_to_ad(node, country)
            if ad and ad.id != "unknown" and ad.id not in seen:
                seen.add(ad.id)
                ads.append(ad)
        return ads

    def _iter_ad_nodes(self, payload):
        # Strategy 1: Relay nodes[] arrays
        for nodes_list in self._find_key_lists(payload, "nodes"):
            for node in nodes_list:
                if self._looks_like_ad(node):
                    yield node
        # Strategy 2: any list of ad-like dicts
        for lst in self._find_all_lists(payload):
            for item in lst:
                if self._looks_like_ad(item):
                    yield item

    def _looks_like_ad(self, node) -> bool:
        if not isinstance(node, dict):
            return False
        has_id = any(k in node for k in self.AD_ID_KEYS)
        has_hint = any(k in node for k in self.AD_HINT_KEYS)
        return has_id and has_hint

    def _find_key_lists(self, node, key):
        if isinstance(node, dict):
            if key in node and isinstance(node[key], list):
                yield node[key]
            for v in node.values():
                yield from self._find_key_lists(v, key)
        elif isinstance(node, list):
            for item in node:
                yield from self._find_key_lists(item, key)

    def _find_all_lists(self, node):
        if isinstance(node, dict):
            for v in node.values():
                yield from self._find_all_lists(v)
        elif isinstance(node, list):
            yield node
            for item in node:
                yield from self._find_all_lists(item)

    def _node_to_ad(self, node, country):
        try:
            return normalize_meta_ad(node, country)
        except Exception:
            return None
