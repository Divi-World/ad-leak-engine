"""Fix Forge orchestrator [SEED: 2399]. Routes leaks to platform generators."""
from ..shared.schemas import Leak, Fix
from ..shared.exceptions import PlatformAmbiguousError
from .platforms.shopify import ShopifyFixGenerator
from .platforms.woocommerce import WooCommerceFixGenerator
from .platforms.bigcommerce import BigCommerceFixGenerator
from .platforms.custom import CustomFixGenerator
from .platforms.nextjs_headless import NextJsHeadlessFixGenerator

class VerticalStrategyResolver:
    """Maps keywords to canonical business verticals using Expansion Map logic."""
    
    VERTICAL_KEYWORDS = {
        # --- Healthcare & Medical ---
        "healthcare_clinic": [
            "clinic", "dental", "doctor", "medical", "hospital", "physiotherapy", 
            "chiropractic", "dermatology", "fertility", "veterinary", "med spa", 
            "urgent care", "specialty clinic", "telehealth", "wellness", "supplement", 
            "nutrition", "vitamin", "organic", "holistic"
        ],
        
        # --- Real Estate & Property ---
        "real_estate": [
            "realty", "property", "homes", "mortgage", "realtor", "housing", "mls", 
            "listing", "zillow", "rental", "lease", "appraisal"
        ],
        
        # --- Education (K12 & Higher Ed) ---
        "education_school": [
            "school", "academy", "tutoring", "admissions", "enrollment", "k12", 
            "charter", "private school", "after school", "summer camp", "language school",
            "test prep", "homeschool"
        ],
        "education_higher_ed": [
            "university", "college", "degree", "campus", "student recruitment", 
            "graduate program", "continuing education", "online degree"
        ],
        
        # --- Finance & Legal ---
        "finance_services": [
            "bank", "insurance", "loan", "fintech", "accounting", "tax", "wealth", 
            "lending", "credit", "investment", "financial planning"
        ],
        "legal_professional": [
            "lawyer", "attorney", "legal", "litigation", "immigration", "estate planning", 
            "personal injury", "family law", "paralegal"
        ],
        
        # --- Home Services & Trades ---
        "home_improvement": [
            "plumbing", "roofing", "hvac", "landscaping", "cleaning", "pest control", 
            "contractor", "electrician", "handyman", "renovation", "construction"
        ],
        
        # --- Beauty, Fitness & Lifestyle ---
        "beauty_health": [
            "skincare", "beauty", "cosmetic", "serum", "spa", "salon", "makeup", 
            "facial", "cleanser", "moisturizer", "hair", "nails"
        ],
        "fitness_gym": [
            "gym", "workout", "crossfit", "yoga", "pilates", "training", "weight loss", 
            "exercise", "fitness coach", "personal trainer"
        ],
        
        # --- E-commerce & Retail ---
        "ecommerce_retail": [
            "shop", "store", "boutique", "fashion", "apparel", "dropshipping", 
            "retail", "buy", "cart", "checkout", "clothing", "shoes", "jewelry"
        ],
        
        # --- Agencies & B2B Services ---
        "agency_marketing": [
            "seo", "ppc", "digital marketing", "branding", "consulting", "lead generation", 
            "b2b", "agency", "freelancer", "creative studio", "photography", "design"
        ],
        
        # --- Automotive & Travel ---
        "automotive": [
            "car dealership", "auto repair", "car rental", "ev charging", "auto insurance", 
            "mechanic", "tire", "service center"
        ],
        "travel_hospitality": [
            "hotel", "resort", "airline", "travel agency", "vacation rental", "tour operator", 
            "cruise", "booking", "lodging"
        ],
        
        # --- Food & Beverage ---
        "food_beverage": [
            "restaurant", "cafe", "catering", "food delivery", "bakery", "bar", 
            "coffee shop", "pizza", "burger", "fine dining"
        ],
        
        # --- Government & Public Sector ---
        "public_sector": [
            "government", "municipal", "public transit", "social services", "civic engagement", 
            "procurement", "public health campaign"
        ],
        
        # --- Recruitment & HR ---
        "hr_staffing": [
            "recruitment", "employer branding", "job advertising", "talent acquisition", 
            "staffing agency", "hiring", "jobs"
        ]
    }

    def resolve(self, keywords: list[str]) -> str | None:
        if not keywords: 
            return None
        
        # Filter out empty strings and whitespace-only entries
        normalized = [k.lower().strip() for k in keywords if k.strip()]
        
        if not normalized:
            return None

        best_vertical = None
        max_score = 0
        
        # Define weights: Exact match > Substring match
        for vertical, terms in self.VERTICAL_KEYWORDS.items():
            score = 0
            for term in terms:
                for kw in normalized:
                    if kw == term:
                        score += 10  # Strong signal
                    elif term in kw or kw in term:
                        score += 2   # Weak signal
                    
            if score > max_score:
                max_score = score
                best_vertical = vertical
        
        # THRESHOLD GUARD: Only return a vertical if we have strong evidence
        # If score is too low (e.g., just one weak substring match), return None
        # This prevents mislabeling a supplement store as "Public Sector"
        if max_score < 5: 
            return None
            
        return best_vertical

class FixForge:
    def __init__(self):
        self.generators = {
            "shopify": ShopifyFixGenerator(),
            "woocommerce": WooCommerceFixGenerator(),
            "bigcommerce": BigCommerceFixGenerator(),
            "custom": CustomFixGenerator(),
            "nextjs": NextJsHeadlessFixGenerator(),
        }
        self.resolver = VerticalStrategyResolver()

    def generate(self, leak: Leak, platform: str, confidence: float, context_keywords: list[str] | None = None) -> Fix:
        # Platform-specific code injection requires confidence >= 0.5.
        if platform != "custom" and confidence < 0.5:
            raise PlatformAmbiguousError(
                f"Platform confidence {confidence} too low for {platform} codegen"
            )
        
        generator = self.generators.get(platform, self.generators["custom"])
        
        # Resolve Vertical for L1 Creative Leaks
        vertical = None
        if leak.tier == "L1" and context_keywords:
            vertical = self.resolver.resolve(context_keywords)
            
        # Pass vertical to generator
        return generator.generate(leak, platform, confidence, vertical=vertical)