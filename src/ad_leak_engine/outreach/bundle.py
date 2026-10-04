"""Outreach package assembly [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..shared.schemas import Page, Leak, Fix, OutreachPack
from ..shared.interfaces import AbstractOutreachBuilder
from .message_gen import MessageGenerator
from .compliance import ComplianceChecker

TEMPLATE_DIR = Path(__file__).parent / "templates"


class OutreachBuilder(AbstractOutreachBuilder):
    """Assembles the complete client-facing teardown package."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.message_gen = MessageGenerator()
        self.compliance = ComplianceChecker()
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build(self, page: Page, leaks: list[Leak], fixes: list[Fix], financial_data: dict | None = None) -> OutreachPack:
        """Assemble teardown, message, and evidence into an OutreachPack."""
        # Rank leaks by severity (highest first)
        leaks = sorted(leaks, key=lambda l: l.severity, reverse=True)

        # Calculate recovery BEFORE generating teardown so it can be passed in
        estimated_recovery = self._estimate_recovery(page, leaks)
        teardown_md = self._generate_teardown(page, leaks, fixes, estimated_recovery, financial_data=financial_data)
        exec_summary = self.message_gen.generate_executive_summary(page, leaks)
        message_text = self.message_gen.generate_message(page, leaks, fixes)

        self.compliance.validate(message_text)

        page_dir = self.output_dir / page.id
        page_dir.mkdir(parents=True, exist_ok=True)

        teardown_path = page_dir / "teardown.md"
        teardown_path.write_text(teardown_md, encoding="utf-8")

        message_path = page_dir / "message.txt"
        message_path.write_text(message_text, encoding="utf-8")

        evidence_paths = [str(teardown_path), str(message_path)]

        return OutreachPack(
            page_id=page.id,
            page_name=page.name,
            prospect_url=page.url,
            teardown_markdown=teardown_md,
            executive_summary=exec_summary,
            leaks_found=leaks,
            fixes=fixes,
            evidence_paths=evidence_paths,
            message_text=message_text,
            estimated_recovery=estimated_recovery,
        )

    def _generate_teardown(self, page: Page, leaks: list[Leak], fixes: list[Fix], estimated_recovery: str, financial_data: dict | None = None) -> str:
        # [SEED: 2399] EVIDENCE SANITIZATION (Strip raw logs for C-Level readability)
        for leak in leaks:
            if hasattr(leak, 'evidence') and isinstance(leak.evidence, dict) and 'network_requests' in leak.evidence:
                reqs = leak.evidence['network_requests']
                if isinstance(reqs, list):
                    pixel_detected = any('facebook' in r.get('url','') or 'fbq' in r.get('url','') or 'fbevents' in r.get('url','') for r in reqs if isinstance(r, dict))
                    waf_detected = any('cloudflare' in r.get('url','') or 'challenge' in r.get('url','') for r in reqs if isinstance(r, dict))
                    summary = f"Analyzed {len(reqs)} network requests. "
                    if waf_detected: summary += "WAF/Bot Protection detected. "
                    summary += f"Meta Pixel: {'Detected' if pixel_detected else 'MISSING'}."
                    leak.evidence['network_requests'] = summary
        
        template = self.env.get_template("teardown.md.j2")
        return template.render(page=page, leaks=leaks, fixes=fixes, estimated_recovery=estimated_recovery)

    def _estimate_recovery(self, page: Page, leaks: list[Leak], financial_data: dict | None = None) -> str:
        # [SEED: 2399] HARD FINANCIAL DATA (Graph API Insights)
        if financial_data and financial_data.get("actual_spend"):
            spend = financial_data["actual_spend"]
            roas = financial_data.get("actual_roas", 0)
            cpa = financial_data.get("actual_cpa")
            # Conservative recovery: 15-25% efficiency gain (industry standard)
            recovery_low = round(spend * 0.15, 0)
            recovery_high = round(spend * 0.25, 0)
            return f"${recovery_low:,.0f}-${recovery_high:,.0f}/mo recovery (based on actual ${spend:,.0f} spend, {roas}x ROAS)"
        # Fallback: enhanced heuristic estimation
        # 1. HOLY GRAIL: If OAuth granted actual spend, use it for lethal precision
        if page.actual_monthly_spend and page.actual_monthly_spend > 0:
            high_sev_count = sum(1 for l in leaks if l.severity >= 0.8)
            med_sev_count = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
            
            # Industry standard: broken tracking inflates CPA by 15-30%
            inflation_rate = (high_sev_count * 0.20) + (med_sev_count * 0.10)
            inflation_rate = min(inflation_rate, 0.50)  # Cap at 50%
            
            recovery = page.actual_monthly_spend * inflation_rate
            return f"${recovery:,.0f}/month potential recovery (Based on verified ${page.actual_monthly_spend:,.0f}/mo actual spend)"
        
        # 2. FALLBACK: Meta Ad Library estimated spend range
        spend_range = page.total_estimated_spend
        if not spend_range or spend_range == (0, 0):
            high_sev = sum(1 for l in leaks if l.severity >= 0.8)
            med_sev = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
            recovery = (high_sev * 1000) + (med_sev * 300)
            return f"${recovery:,}/month potential recovery"
        
        spend_midpoint = (spend_range[0] + spend_range[1]) / 2
        high_sev_count = sum(1 for l in leaks if l.severity >= 0.8)
        med_sev_count = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
        
        inflation_rate = (high_sev_count * 0.20) + (med_sev_count * 0.10)
        inflation_rate = min(inflation_rate, 0.50)
        
        recovery = spend_midpoint * inflation_rate
        return f"${recovery:,.0f}/month potential recovery (based on ${spend_range[0]:,.0f}-${spend_range[1]:,.0f} Meta spend)"
