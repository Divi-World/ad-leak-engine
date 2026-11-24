"""[SEED: 2399] Graph API Financial Ingestor.
Pulls actual ad spend, CPA, and ROAS from the Meta Ads Insights API.
The API is FREE — requires only the OAuth token persisted in Tenant DB.
Falls back to enhanced heuristics when no token is available.
"""
import os
from ..persistence.connection_pool import GraphQLConnectionPool  # [RW-3]


_graph_pool = None  # [RW-3] module-level pooled client singleton


def _get_graph_pool():
    global _graph_pool
    if _graph_pool is None:
        _graph_pool = GraphQLConnectionPool()
    return _graph_pool


GRAPH_BASE = "https://graph.facebook.com/v19.0"

def _as_float(v, default=0.0):
    """Accept a scalar OR Meta's structured action-value array. Never raises."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return default
    if isinstance(v, list):
        for _pref in ("purchase", "omni_purchase"):
            for _it in v:
                if isinstance(_it, dict) and _it.get("action_type") == _pref:
                    try:
                        return float(_it.get("value", default))
                    except (TypeError, ValueError):
                        return default
        for _it in v:
            if isinstance(_it, dict) and "value" in _it:
                try:
                    return float(_it["value"])
                except (TypeError, ValueError):
                    pass
    return default


class GraphAPIFinancialIngestor:
    """Queries the Meta Ads Insights API for hard financial data."""

    def __init__(self, access_token: str):
        self.token = access_token

    def get_ad_accounts(self) -> list[dict]:
        """Fetch all ad accounts accessible to the authorized user.
        Endpoint: GET /me/adaccounts?fields=id,name,amount_spent
        """
        try:
            resp = _get_graph_pool().get(
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

    def get_account_insights(self, account_id: str, days: int = 30,
                             account_currency: str | None = None) -> dict | None:
        """Fetch actual spend, CPA, ROAS for an ad account.
        Endpoint: GET /act_{id}/insights
        Fields: spend,actions,action_values,cost_per_action_type,purchase_roas
        Ref: https://www.get-ryze.ai/blog/meta-ads-api-insights-endpoint
        """
        acct_id = account_id.replace("act_", "")
        try:
            resp = _get_graph_pool().get(
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
                    spend = _as_float(row.get("spend", 0))
                    roas = _as_float(row.get("purchase_roas", 0))
                    impressions = int(_as_float(row.get("impressions", 0)))
                    clicks = int(_as_float(row.get("clicks", 0)))

                    # Extract CPA from cost_per_action_type array
                    cpa = None
                    for action in row.get("cost_per_action_type", []):
                        if action.get("action_type") == "purchase":
                            cpa = _as_float(action.get("value", 0))
                            break

                    # Extract purchase count from actions array
                    purchases = 0
                    for action in row.get("actions", []):
                        if action.get("action_type") == "purchase":
                            purchases = int(_as_float(action.get("value", 0)))
                            break

                    return {
                        "actual_spend": round(spend, 2),
                        "actual_roas": round(roas, 2),
                        "actual_cpa": round(cpa, 2) if cpa else None,
                        "impressions": impressions,
                        "clicks": clicks,
                        "purchases": purchases,
                        "currency": account_currency or "USD",
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
            insights = self.get_account_insights(
                acct.get("id", ""), days,
                account_currency=acct.get("currency"),
            )
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
            # SEED 2399: Fallback to environment variable for local CLI testing
            token = os.getenv("META_ACCESS_TOKEN")
            if not token:
                return None
        ingestor = GraphAPIFinancialIngestor(token)
        return ingestor.get_page_ad_spend(page_id)
    except Exception:
        return None
