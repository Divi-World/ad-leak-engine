"""Filesystem evidence storage [SEED: 2399]."""
from pathlib import Path
class EvidenceStorage:
    def __init__(self, base_dir="output"):
        self.base_dir = Path(base_dir)
    def save_screenshot(self, page_id: str, data: bytes):
        p = self.base_dir / str(page_id) / "evidence" / "screenshot.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
