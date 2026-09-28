"""Outreach dispatcher for Ad-Leak-Engine [SEED: 2399]."""
import os
import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_test_key")
FROM_EMAIL = os.getenv("FROM_EMAIL", "Ad-Leak-Engine <audit@adleakengine.com>")

async def send_outreach_email(to_email: str, subject: str, message_text: str) -> dict:
    """Send an outreach email via Resend API."""
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": message_text,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        
    if response.status_code == 200:
        return {"status": "success", "email_id": response.json().get("id")}
    else:
        return {"status": "error", "detail": response.text}
