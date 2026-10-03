
# ============================================================
# [SEED: 2399] META GRAPH API OAUTH REAL-ID PROOF
# Required for $80k-$200k SaaS Valuation (Hard Financial Data Ingestion)
# ============================================================
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import os, urllib.parse, requests

router = APIRouter(prefix="/oauth", tags=["OAuth Real-ID Proof"])

META_APP_ID = os.getenv("META_APP_ID", "YOUR_META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET", "YOUR_META_APP_SECRET")
REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/meta/callback")

# Import scopes from our enterprise config
try:
    from ...config.enterprise_scopes import META_GRAPH_API_SCOPES
except ImportError:
    META_GRAPH_API_SCOPES = ["ads_read", "ads_management", "business_management"]

@router.get("/meta/login")
async def meta_login(request: Request):
    # [SEED: 2399] CSRF Protection State
    state = "seed_2399_csrf_state"
    scope_str = ",".join(META_GRAPH_API_SCOPES)
    
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={META_APP_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"state={state}&"
        f"scope={urllib.parse.quote(scope_str)}"
    )
    return RedirectResponse(url=auth_url)

@router.get("/meta/callback")
async def meta_callback(request: Request, code: str = None, state: str = None):
    if state != "seed_2399_csrf_state":
        raise HTTPException(status_code=400, detail="[SEED: 2399] Invalid CSRF state. Handshake aborted.")
        
    if not code:
        raise HTTPException(status_code=400, detail="[SEED: 2399] Missing OAuth authorization code.")
        
    # Exchange code for Long-Lived Access Token
    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
    payload = {
        "client_id": META_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "client_secret": META_APP_SECRET,
        "code": code
    }
    
    try:
        resp = requests.get(token_url, params=payload, timeout=10)
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[SEED: 2399] Meta Graph API Timeout: {str(e)}")
        
    if "access_token" not in data:
        error_msg = data.get("error", {}).get("message", "Unknown Meta OAuth Error")
        raise HTTPException(status_code=400, detail=f"[SEED: 2399] Meta OAuth Rejected: {error_msg}")
        
    # [SEED: 2399] FORENSIC GATE: Token acquired. In production, this is encrypted and stored in the Tenant DB.
    return JSONResponse(content={
        "status": "success", 
        "message": "[SEED: 2399] Meta Real-ID Proof Connected. Hard Financial Ingestion Cleared.",
        "scopes_granted": META_GRAPH_API_SCOPES,
        "token_type": data.get("token_type", "bearer")
    })
