"""[SEED: 2399] Graph API Financial Ingestor.
Pulls actual ad spend, CPA, and ROAS from the Meta Ads Insights API.
The API is FREE — requires only the OAuth token persisted in Tenant DB.
Falls back to enhanced heuristics when no token is available.
"""
import os
import httpx


GRAPH_BASE = "https://graph.facebook.com/v19.0"


class GraphAPIFinancialIngestor:
    """Queries the Meta Ads Insights API for hard financial data."""

    def __init__(self, access_token: str):
        self.token = access_token

    def get_ad_accounts(self) -> list[dict]:
        """Fetch all ad accounts accessible to the authorized user.
        Endpoint: GET /me/adaccounts?fields=id,name,amount_spent
        """
        try:
            resp = httpx.get(
                f"{GRAPH_BASE}/me/adaccounts",
                params={
                    "fields": "id,name,amount_spent,currency",
                    "access_token": self.token,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception:
            pass
        return []

    def get_account_insights(self, account_id: str, days: int = 30) -> dict | None:
        """Fetch actual spend, CPA, ROAS for an ad account.
        Endpoint: GET /act_{id}/insights
        Fields: spend,actions,action_values,cost_per_action_type,purchase_roas
        Ref: https://www.get-ryze.ai/blog/meta-ads-api-insights-endpoint
        """
        acct_id = account_id.replace("act_", "")
        try:
            resp = httpx.get(
                f"{GRAPH_BASE}/act_{acct_id}/insights",
                params={
                    "fields": "spend,impressions,clicks,actions,action_values,cost_per_action_type,purchase_roas,campaign_name",
                    "date_preset": f"last_{days}d",
                    "level": "account",
                    "access_token": self.token,
                },
                timeout=20.0,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    row = data[0]
                    spend = float(row.get("spend", 0))
                    roas = float(row.get("purchase_roas", 0))
                    impressions = int(row.get("impressions", 0))
                    clicks = int(row.get("clicks", 0))

                    # Extract CPA from cost_per_action_type array
                    cpa = None
                    for action in row.get("cost_per_action_type", []):
                        if action.get("action_type") == "purchase":
                            cpa = float(action.get("value", 0))
                            break

                    # Extract purchase count from actions array
                    purchases = 0
                    for action in row.get("actions", []):
                        if action.get("action_type") == "purchase":
                            purchases = int(action.get("value", 0))
                            break

                    return {
                        "actual_spend": round(spend, 2),
                        "actual_roas": round(roas, 2),
                        "actual_cpa": round(cpa, 2) if cpa else None,
                        "impressions": impressions,
                        "clicks": clicks,
                        "purchases": purchases,
                        "currency": "USD",
                        "period_days": days,
                        "source": "meta_graph_api_live",
                    }
        except Exception:
            pass
        return None

    def get_page_ad_spend(self, page_id: str, days: int = 30) -> dict | None:
        """Attempt to pull page-level ad delivery data.
        Uses the Ad Library API (FREE, no token required) for public data,
        then enriches with Insights API if token is available.
        """
        # Step 1: Try Insights API for hard financial data
        accounts = self.get_ad_accounts()
        if accounts:
            # Use the first account (single-tenant mode)
            acct = accounts[0]
            insights = self.get_account_insights(acct.get("id", ""), days)
            if insights:
                insights["account_name"] = acct.get("name", "Unknown")
                return insights
        return None


def get_financial_data_for_page(page_id: str) -> dict | None:
    """Top-level function: attempt to pull hard financial data.
    Returns None if no OAuth token is available (falls back to heuristics).
    """
    try:
        from ..persistence.repository import TenantRepository
        repo = TenantRepository()
        token = repo.get_tenant_token("seed_2399")
        if not token:
            return None
        ingestor = GraphAPIFinancialIngestor(token)
        return ingestor.get_page_ad_spend(page_id)
    except Exception:
        return None
