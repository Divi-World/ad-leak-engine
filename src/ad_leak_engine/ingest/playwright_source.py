"""HUMAN-GRADE Meta Ad Library scraper using camoufox + Regex Extractor [SEED: 2399]."""
from typing import Iterator
from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .html_extractor import HtmlAdExtractor

# --- CRITICAL FIX: Add Missing Imports ---
import time
import logging
logger = logging.getLogger(__name__)
# ----------------------------------------

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

class PlaywrightSource(AbstractAdSource):
    # ... rest of the class remains unchanged ...
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.extractor = HtmlAdExtractor()

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        # [SEED: 2399] SEMANTIC QUERY EXPANSION ENGINE
        EXPANSION_MAP = {
            # =========================================================
            # --- Existing Consumer / Commercial ---
            # =========================================================
            "skincare": [
                "skin", "skin care", "beauty", "dermatology", "serum", "moisturizer",
                "facial", "cleanser", "cosmetic", "cosmetics", "anti-aging", "esthetics",
                "aesthetics", "glow", "acne", "sunscreen", "retinol", "spf"
            ],
            "health": [
                "wellness", "supplement", "supplements", "fitness", "nutrition", "medical",
                "holistic", "vitamin", "vitamins", "organic", "alternative medicine",
                "protein", "keto", "weight loss", "mental health", "telehealth", "dental"
            ],
            "fitness": [
                "gym", "workout", "training", "weight loss", "crossfit", "yoga", "pilates",
                "exercise", "personal trainer", "bodybuilding", "health", "nutrition",
                "home gym", "running", "cycling", "martial arts"
            ],
            "marketing": [
                "seo", "agency", "digital marketing", "consulting", "b2b", "lead generation",
                "ppc", "branding", "smm", "growth hacking", "social media", "content marketing",
                "email marketing", "copywriting", "advertising", "pr", "public relations",
                "affiliate marketing", "influencer marketing", "analytics"
            ],
            "ecommerce": [
                "shop", "store", "buy", "boutique", "retail", "fashion", "apparel",
                "dropshipping", "shopify", "d2c", "direct to consumer", "wholesale",
                "ecom", "online store", "marketplace", "subscription box", "print on demand"
            ],
            "real estate": [
                "realty", "property", "mls", "mortgage", "homes", "realtor", "housing",
                "property management", "homes for sale", "rentals", "airbnb", "vrbo",
                "real estate investing", "flip", "commercial real estate", "land", "condo"
            ],
            "woodworking": [
                "carpentry", "timber", "lumber", "craftsman", "custom furniture", "woodcraft",
                "joinery", "cabinet making", "woodturning", "furniture making"
            ],
            "studio": [
                "photography", "portrait", "creative", "design", "agency", "videography",
                "recording studio", "dance studio", "art studio", "production studio"
            ],

            # =========================================================
            # --- Consumer Verticals (expanded from Map 2) ---
            # =========================================================
            "home": [
                "home decor", "home improvement", "furniture", "interior design", "homeware",
                "home goods", "furnishings", "home accessories", "kitchenware", "bedding",
                "landscaping", "plumbing", "hvac", "roofing", "contractor", "remodeling",
                "decor", "cleaning", "pest control", "electrical", "painting", "flooring",
                "windows", "garage door", "solar", "pool"
            ],
            "fashion": [
                "clothing", "apparel", "boutique", "streetwear", "luxury fashion", "accessories",
                "shoes", "handbags", "jewelry", "watches", "sunglasses", "sneakers", "footwear",
                "menswear", "womenswear", "kids fashion", "swimwear", "activewear", "denim"
            ],
            "beauty": [
                "makeup", "cosmetics", "lipstick", "foundation", "beauty salon", "nail salon",
                "hair salon", "beauty supply", "fragrance", "perfume", "salon", "spa",
                "hair extensions", "lashes", "microblading", "botox", "fillers", "medspa",
                "tanning", "barber", "waxing", "eyebrows"
            ],
            "pets": [
                "pet supplies", "pet food", "dog training", "veterinary", "pet grooming",
                "pet insurance", "cat litter", "dog toys", "pet adoption", "vet", "pet sitting",
                "dog walking", "kennel", "cattery", "animal rescue", "pet trainer",
                "aquarium", "reptile", "pet pharmacy"
            ],
            "gaming": [
                "video games", "esports", "gaming pc", "console", "game server", "mobile game",
                "gaming chair", "streaming", "gaming mouse", "gaming keyboard", "vr", "metaverse",
                "game development", "twitch", "gaming monitor", "gaming headset"
            ],
            "crypto": [
                "bitcoin", "ethereum", "blockchain", "web3", "crypto exchange", "nft", "defi",
                "wallet", "altcoin", "mining", "staking", "smart contract", "token", "dao",
                "crypto trading", "cold storage"
            ],
            "gambling": [
                "casino", "sportsbook", "betting", "poker", "lottery", "online casino", "slots",
                "blackjack", "roulette", "fantasy sports", "horse racing", "bingo"
            ],
            "dating": [
                "dating app", "singles", "matchmaking", "hookup", "relationship", "dating site",
                "speed dating", "dating coach", "over 50 dating", "christian dating"
            ],
            "wedding": [
                "wedding planning", "bridal", "wedding dress", "wedding venue",
                "wedding photographer", "engagement ring", "wedding invitation",
                "wedding catering", "wedding dj", "honeymoon", "wedding cake", "wedding florist"
            ],
            "baby": [
                "baby products", "stroller", "diapers", "maternity", "parenting", "toddler",
                "nursery", "baby food", "baby monitor", "baby formula", "baby clothes",
                "car seat", "breastfeeding", "baby shower"
            ],
            "sports": [
                "sports equipment", "athletic wear", "team sports", "sports betting",
                "sports nutrition", "sports memorabilia", "sports apparel", "golf", "tennis",
                "soccer", "basketball", "baseball", "football", "hockey", "surfing", "skiing"
            ],
            "food": [
                "food delivery", "meal kit", "grocery", "snack", "snacks", "coffee", "tea",
                "supplement drink", "wine", "spirits", "bakery", "restaurant", "cafe",
                "catering", "meal prep", "beverage", "brewery", "winery", "vegan", "organic food",
                "pizza", "sushi", "bbq", "dessert"
            ],
            "electronics": [
                "smartphone", "laptop", "headphones", "smartwatch", "tv", "camera",
                "drone", "gadget", "tablet", "speaker", "earbuds", "monitor", "printer",
                "router", "charger", "smart home", "wearable"
            ],
            "nonprofit": [
                "charity", "donation", "fundraising", "ngo", "foundation", "volunteer",
                "social cause", "crowdfunding", "philanthropy", "grant writing", "nonprofit marketing"
            ],

            # =========================================================
            # --- Institutional & High-Value Verticals ---
            # =========================================================
            "hospital": [
                "hospital marketing", "patient acquisition", "health system advertising", "telehealth",
                "urgent care", "specialty clinic", "medical group", "hospital recruitment",
                "healthcare marketing", "patient experience", "hospital it"
            ],
            "clinic": [
                "dental clinic", "dermatology clinic", "fertility clinic", "physical therapy",
                "chiropractic", "veterinary clinic", "med spa", "urgent care clinic",
                "behavioral health", "pain management", "orthopedic clinic", "eye clinic"
            ],
            "school": [
                "school enrollment", "charter school marketing", "private school admissions",
                "K12 recruitment", "after school program", "school choice", "tutoring",
                "school marketing", "school software", "school safety", "edtech k12"
            ],
            "university": [
                "university admissions", "higher ed marketing", "online degree", "college enrollment",
                "graduate program", "continuing education", "student recruitment", "campus tour",
                "study abroad", "mba", "phd", "community college"
            ],
            "government": [
                "public health campaign", "government recruitment", "municipal services",
                "public transit", "social services", "civic engagement", "government procurement",
                "govtech", "public safety", "defense", "e-government"
            ],
            "recruitment": [
                "employer branding", "job advertising", "talent acquisition", "staffing agency",
                "healthcare recruiting", "education recruiting", "recruiting software", "ats",
                "executive search", "temp agency", "hr tech"
            ],

            # =========================================================
            # --- Other High-Spend Verticals ---
            # =========================================================
            "finance": [
                "bank", "insurance", "fintech", "accounting", "tax prep", "wealth management",
                "lending", "bookkeeping", "financial advisor", "loans", "credit repair", "forex",
                "investing", "stocks", "trading", "retirement", "cpa", "payroll", "crypto finance"
            ],
            "legal": [
                "law firm", "attorney", "personal injury", "immigration lawyer", "family law",
                "estate planning", "criminal defense", "divorce lawyer", "bankruptcy",
                "business law", "dui", "workers compensation", "patent", "legal software"
            ],
            "automotive": [
                "car dealership", "auto repair", "car rental", "ev charging", "auto insurance",
                "car", "detailing", "tires", "motorcycle", "rv", "boat", "marine", "powersports",
                "car wash", "auto parts", "used cars", "leasing", "trucking"
            ],
            "travel": [
                "hotel", "resort", "airline", "travel agency", "vacation rental", "tour operator",
                "cruise", "booking", "flights", "car rental travel", "travel insurance",
                "destination wedding", "safari", "backpacking", "all inclusive"
            ],
            "restaurant": [
                "restaurant", "cafe", "catering", "food delivery", "bakery", "bar",
                "bistro", "fast food", "fine dining", "food truck", "pub", "coffee shop",
                "restaurant pos", "restaurant marketing"
            ],
            "home_services": [
                "plumbing", "roofing", "hvac", "landscaping", "cleaning service", "pest control",
                "electrician", "handyman", "garage door", "flooring", "painting service",
                "window replacement", "gutter", "chimney", "locksmith", "mold removal"
            ],
            "education_k12": [
                "tutoring", "test prep", "homeschool", "summer camp", "language school",
                "sat prep", "act prep", "private tutor", "stem education", "coding for kids",
                "montessori", "special education"
            ],

            # =========================================================
            # --- NEW: Technology / B2B SaaS (from Map 2 + expanded) ---
            # =========================================================
            "tech": [
                "saas", "software", "startup", "ai", "artificial intelligence", "cloud",
                "cybersecurity", "fintech", "web3", "crypto", "machine learning", "data analytics",
                "devops", "api", "automation", "no code", "low code", "it services", "managed it",
                "erp", "crm", "hr software", "martech", "adtech", "biotech", "quantum"
            ],

            # =========================================================
            # --- NEW: Auto (alias merged above; kept for backward compat)
            # =========================================================
            "auto": [
                "car dealership", "auto repair", "detailing", "tires", "motorcycle", "rv",
                "boat", "marine", "powersports", "car wash", "used cars", "auto parts",
                "ev charging", "auto insurance"
            ],

            # =========================================================
            # --- NEW: Education (generic; K12/university split above) ---
            # =========================================================
            "education": [
                "tutoring", "online course", "coaching", "bootcamp", "language learning",
                "test prep", "certification", "edtech", "homeschool", "online degree",
                "mooc", "learning management system", "lms", "study abroad", "upskilling"
            ],

            # =========================================================
            # --- NEW: Pet (singular alias; merged with "pets" above) ---
            # =========================================================
            "pet": [
                "dog grooming", "vet", "pet sitting", "dog walking", "pet food", "pet supplies",
                "kennel", "cattery", "animal rescue", "pet trainer", "pet insurance",
                "pet adoption", "veterinary"
            ],

            # =========================================================
            # --- NEW: Personal Care (merged from duplicate personal/personal care)
            # =========================================================
            "personal care": [
                "skincare", "beauty", "cosmetics", "hair care", "body care", "oral care",
                "wellness", "organic", "natural", "bath", "grooming", "hygiene", "moisturizer",
                "shampoo", "soap", "lotion", "cream", "serum", "facial", "cleanser",
                "deodorant", "toothpaste", "razor", "sunscreen", "conditioner", "body wash"
            ],

            # =========================================================
            # --- NEW: Media / Entertainment / Publishing (gap fill) ---
            # =========================================================
            "media": [
                "entertainment", "streaming", "film", "music", "podcast", "publishing",
                "news", "magazine", "radio", "television", "production", "content creator",
                "youtube", "tiktok", "advertising media", "ott", "cinema"
            ],

            # =========================================================
            # --- NEW: Energy / Utilities (gap fill) ---
            # =========================================================
            "energy": [
                "solar", "renewable energy", "electricity", "oil and gas", "wind energy",
                "battery", "ev charging", "utility", "power plant", "energy efficiency",
                "nuclear", "hydrogen", "grid"
            ],

            # =========================================================
            # --- NEW: Logistics / Supply Chain (gap fill) ---
            # =========================================================
            "logistics": [
                "shipping", "freight", "warehousing", "supply chain", "trucking",
                "last mile delivery", "fulfillment", "3pl", "courier", "cargo",
                "fleet management", "customs", "cold chain"
            ],

            # =========================================================
            # --- NEW: Manufacturing / Industrial (gap fill) ---
            # =========================================================
            "manufacturing": [
                "industrial", "factory", "machinery", "cnc", "3d printing", "robotics",
                "automation industrial", "metal fabrication", "plastics", "packaging",
                "quality control", "lean manufacturing", "oem", "supplier"
            ],

            # =========================================================
            # --- NEW: Agriculture (gap fill) ---
            # =========================================================
            "agriculture": [
                "farming", "agtech", "crops", "livestock", "dairy", "agriculture equipment",
                "irrigation", "fertilizer", "seeds", "greenhouse", "organic farming",
                "precision agriculture", "harvest"
            ],

            # =========================================================
            # --- NEW: Insurance (standalone high-spend vertical) ---
            # =========================================================
            "insurance": [
                "auto insurance", "home insurance", "life insurance", "health insurance",
                "renters insurance", "pet insurance", "business insurance", "travel insurance",
                "disability insurance", "umbrella policy", "insurance broker", "claims"
            ],

            # =========================================================
            # --- NEW: Construction / Trades (gap fill) ---
            # =========================================================
            "construction": [
                "general contractor", "construction company", "building", "renovation",
                "commercial construction", "residential construction", "civil engineering",
                "architecture", "surveying", "concrete", "steel", "heavy equipment"
            ],

            # =========================================================
            # --- NEW: Professional Services (gap fill) ---
            # =========================================================
            "professional services": [
                "consulting", "accounting firm", "law firm", "it consulting", "management consulting",
                "hr consulting", "marketing agency", "design agency", "engineering services",
                "architecture firm", "bookkeeping", "business coaching"
            ],

            # =========================================================
            # --- NEW: Retail (general, distinct from ecommerce) ---
            # =========================================================
            "retail": [
                "retail store", "shopping mall", "department store", "supermarket",
                "convenience store", "specialty retail", "retail pos", "inventory",
                "point of sale", "brick and mortar", "franchise"
            ],

            # =========================================================
            # --- NEW: Environment / Sustainability (gap fill) ---
            # =========================================================
            "environment": [
                "sustainability", "recycling", "waste management", "water treatment",
                "clean energy", "climate", "carbon offset", "esg", "environmental services",
                "conservation"
            ],

            # =========================================================
            # --- NEW: Telecom (gap fill) ---
            # =========================================================
            "telecom": [
                "mobile carrier", "internet provider", "isp", "broadband", "5g", "voip",
                "phone plans", "fiber", "satellite internet", "telecom equipment"
            ]
        }
        queries_to_run = [query]
        q_lower = query.lower().strip()
        if q_lower in EXPANSION_MAP:
            queries_to_run.extend(EXPANSION_MAP[q_lower])
        else:
            # [SEED: 2399] UNIVERSAL TRANSACTIONAL FALLBACK
            # For arbitrary niches (e.g., "woodworking", "real estate", "studio"), append commercial modifiers
            # to guarantee the Meta Ad Library returns DTC/Service leads, not blogs or apps.
            queries_to_run.extend([
                f"{query} store", f"{query} shop", f"{query} services", 
                f"{query} buy", f"{query} agency"
            ])
            
        seen_ids = set()
        total_yielded = 0
        hb = HumanBrowser(headless=self.headless)

        for q in queries_to_run:
            if total_yielded >= max_results:
                break
                
# Inside PlaywrightSource.search(), replace the try block:

            url = AD_LIBRARY_URL.format(country=country, query=q.replace(" ", "%20"))
            html = ""
            try:
                with hb.session() as page:
                    # [FIX] Removed non-existent prime_facebook_session call.
                    # Instead, navigate directly and handle potential blocks interactively.
                    
                    logger.info(f"[SOURCE] Navigating to {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    
                    # [FIX] Simulate human-like initial load behavior
                    hb.human_pause(2.0, 4.0)
                    
                    # [FIX] Check for Cloudflare/Turnstile challenges on FB itself
                    # FB Ad Library sometimes triggers simple bot checks
                    if "challenges.cloudflare.com" in page.content():
                        logger.warning("[SOURCE] Detected CF Challenge on FB. Attempting solve...")
                        hb.solve_cloudflare_turnstile(page)
                        time.sleep(3) # Wait for reload
                    
                    # Scroll to trigger lazy loading of ad cards
                    for _ in range(3):
                        hb.human_scroll(page, distance=800, steps=10)
                        hb.human_pause(1.5, 3.0)
                        
                    html = page.content()
                    logger.info(f"[SOURCE] Extracted HTML length: {len(html)} bytes")
                    
            except Exception as e:
                # [FIX] Log the specific error instead of swallowing it blindly
                logger.error(f"[SOURCE] Query '{q}' failed: {type(e).__name__}: {e}")
                continue # Move to next query expansion

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
