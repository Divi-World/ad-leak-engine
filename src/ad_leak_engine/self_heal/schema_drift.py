"""Schema drift detection via response key hashing."""
import hashlib
import json

class SchemaDriftDetector:
    def __init__(self):
        self.expected_hash: str | None = None

    def set_baseline(self, sample_data: dict):
        self.expected_hash = self._hash_keys(sample_data)

    def check_drift(self, data: dict) -> bool:
        current_hash = self._hash_keys(data)
        if self.expected_hash is None:
            self.expected_hash = current_hash
            return False
        return current_hash != self.expected_hash

    def _hash_keys(self, data: dict) -> str:
        keys = sorted(list(data.keys()))
        return hashlib.md5(json.dumps(keys).encode()).hexdigest()
