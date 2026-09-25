"""Export FastAPI OpenAPI/Swagger JSON [SEED: 2399]."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.orchestrator.app import app

def main():
    docs = app.openapi()
    Path("output/api_docs.json").write_text(json.dumps(docs, indent=2))
    print("[SEED:2399] API Documentation exported to output/api_docs.json")

if __name__ == "__main__":
    main()
