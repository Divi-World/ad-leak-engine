"""Header Randomization [SEED: 2399].
Rotates sec-ch-ua, sec-fetch-mode, accept-language per request.
"""
import random

def get_random_headers() -> dict:
    """Generates randomized browser-like headers for DataDome/Akamai neutralization."""
    chrome_versions = ["120.0.6099.109", "121.0.6167.85", "122.0.6261.94"]
    ver = random.choice(chrome_versions)
    major = ver.split(".")[0]
    
    return {
        "sec-ch-ua": f'"Not A(Brand";v="99", "Google Chrome";v="{major}", "Chromium";v="{major}"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": random.choice(["cors", "same-origin", "navigate"]),
        "sec-fetch-site": random.choice(["same-origin", "cross-site", "none"]),
        "accept-language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en;q=0.8"]),
        "priority": random.choice(["u=1, i", "u=0, i", "u=1"]),
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"
    }
