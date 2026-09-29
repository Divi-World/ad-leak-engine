"""Meta OAuth routes for the Holy Grail Deep Dive [SEED: 2399]."""
import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse

router = APIRouter()

META_CLIENT_ID = os.getenv("META_CLIENT_ID", "YOUR_META_APP_ID")
META_CLIENT_SECRET = os.getenv("META_CLIENT_SECRET", "YOUR_META_APP_SECRET")
REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:8000/api/v1/auth/meta/callback")

@router.get("/meta/login")
def meta_login():
    """Redirects the prospect to Meta's official OAuth consent screen."""
    if META_CLIENT_ID == "YOUR_META_APP_ID":
        return JSONResponse(
            status_code=503,
            content={"status": "not_configured", "message": "Meta OAuth not configured. Engine operates in unlimited public mode."}
        )
    auth_url = (
        "https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={META_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=ads_read,business_management"
        "&response_type=code"
    )
    return RedirectResponse(url=auth_url)

@router.get("/meta/callback")
async def meta_callback(request: Request):
    """Meta redirects here after the prospect grants consent."""
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(f"<h2>Access Denied</h2><p>{error}</p><script>setTimeout(()=>window.close(),3000)</script>")
    if not code:
        return HTMLResponse("<h2>Error</h2><p>No authorization code.</p><script>setTimeout(()=>window.close(),3000)</script>")

    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "client_id": META_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "client_secret": META_CLIENT_SECRET,
        "code": code,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(token_url, params=params)
            data = resp.json()
            if "access_token" in data:
                return HTMLResponse(
                    "<h2 style='color:green; font-family:sans-serif;'>Access Granted</h2>"
                    "<p style='font-family:sans-serif;'>Deep spend analysis enabled. This window will close.</p>"
                    "<script>setTimeout(()=>{if(window.opener){window.opener.postMessage({ale_oauth:'success'},'*');}window.close();},2000)</script>"
                )
            return HTMLResponse(f"<h2>Token Exchange Failed</h2><pre>{data}</pre>")
    except Exception as e:
        return HTMLResponse(f"<h2>Network Error</h2><pre>{e}</pre>")
