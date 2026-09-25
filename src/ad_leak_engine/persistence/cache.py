"""DiskCache wrapper with TTL [SEED: 2399]."""
import diskcache
from pathlib import Path
class CacheManager:
    def __init__(self, directory="data/cache"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.cache = diskcache.Cache(directory)
    def get(self, key, default=None): return self.cache.get(key, default)
    def set(self, key, value, ttl=86400): self.cache.set(key, value, expire=ttl)
