"""Meta OAuth routes for the Holy Grail Deep Dive [SEED: 2399]."""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()

# These will be populated from environment variables in production
META_CLIENT_ID = "YOUR_META_APP_ID"
REDIRECT_URI = "https://api.adleakengine.com/api/v1/auth/meta/callback"

@router.get("/meta/login")
def meta_login() -> RedirectResponse:
    """
    Redirects the prospect to Meta's official OAuth consent screen.
    Scopes: ads_read, business_management (Read-only access).
    """
    auth_url = (
        "https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={META_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=ads_read,business_management"
        "&response_type=code"
    )
    return RedirectResponse(url=auth_url)

@router.get("/meta/callback")
def meta_callback(request: Request) -> dict:
    """
    Meta redirects here after the prospect grants consent.
    Phase 29 will implement the token exchange and actual_spend fetching here.
    """
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        return {"status": "error", "message": f"OAuth denied: {error}"}
    
    if not code:
        return {"status": "error", "message": "No authorization code provided."}
    
    # TODO Phase 29: Exchange 'code' for access_token via Meta Graph API
    # TODO Phase 29: Fetch actual_monthly_spend and update the Page schema
    
    return {
        "status": "success",
        "message": "OAuth successful. Deep dive data processing initiated.",
        "code_received": True
    }
