"""Structured JSON logging for Ad-Leak-Engine [SEED: 2399]."""
import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": 2399,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "stage": getattr(record, "stage", "unknown"),
            "action": getattr(record, "action", "unknown"),
            "error": str(record.exc_info[1]) if record.exc_info else None
        }
        return json.dumps(log_entry)

def get_logger(name: str = "ad_leak_engine") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console handler (clean output for CLI)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("[SEED:2399] %(message)s"))
        logger.addHandler(ch)
        
        # File handler (structured JSON for production monitoring)
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "engine.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)
        
    return logger
