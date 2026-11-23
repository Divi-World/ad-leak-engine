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
        # [SEED: 2399] QUALITY GATE: Validate all fix code blocks before assembly
        # Prevents malformed Liquid/JS/PHP snippets reaching client-facing teardowns
        from ..fix_forge.validation import validate_fix
        valid_fixes = []
        for fix in fixes:
            if validate_fix(fix):
                valid_fixes.append(fix)
            else:
                logger.warning(f"[OUTREACH] Fix rejected by validation: {getattr(fix, 'template_name', 'unknown')}")
        fixes = valid_fixes

        # Rank leaks by severity (highest first)
        # [SEED:2399] Learned-weight prioritisation. Additive: severity/confidence
        # values are never altered; the score is exposed in evidence for auditability.
        # Any degraded weights state falls back to neutral 1.0 — a scan never breaks.
        from ..leak_scan.scoring import calculate_priority_score
        try:
            from ..self_improve.weights import load_weights
            _w = load_weights()
            _w = _w if isinstance(_w, dict) else {}
        except Exception:
            _w = {}

        def _weight_for(_l):
            _t = _w.get(getattr(_l, "tier", "")) or {}
            _v = _t.get(getattr(_l, "signal", ""), 1.0)
            try:
                _v = float(_v)
            except (TypeError, ValueError):
                _v = 1.0
            return _v if _v > 0 else 1.0

        for _l in leaks:
            _wv = _weight_for(_l)
            _sc = calculate_priority_score(_l, _wv)
            _ev = getattr(_l, "evidence", None)
            if isinstance(_ev, dict):
                _ev["priority_score"] = round(_sc, 4)
                _ev["applied_weight"] = _wv

        leaks = sorted(
            leaks,
            key=lambda l: (calculate_priority_score(l, _weight_for(l)), l.severity),
            reverse=True,
        )

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
        
        # [SEED:2399] Harvest the measured audit context from the leaks themselves.
        # No signature change: every detector leak already carries this evidence.
        _audit = {}
        # [SEED:2399] Authoritative source: the probe output already on page.raw.
        _raw = getattr(page, "raw", None)
        _nl = {}
        if isinstance(_raw, dict):
            if isinstance(_raw.get("network_log"), dict):
                _nl = _raw["network_log"]
            elif _raw.get("detected_pixel_id") or _raw.get("pixel_fired"):
                _nl = _raw
        _INTERNAL = {"_meta_prev", "requests", "request_attempts", "fbq_raw_calls",
                     "session_fingerprint", "step_budget_exhausted",
                     "meta_observations_by_step", "tracking_diagnostics",
                     "basket_state", "fulfilment_steps", "funnel_steps",
                     "checkout_snapshot", "auth_page_evidence",
                     "consent_events", "consent_result"}
        for _k, _v in (_nl or {}).items():
            if _k in _INTERNAL or _k.startswith("_"):
                continue
            if _v not in (None, [], {}, ""):
                _audit[_k] = _v

        _keys = ("pixel_census", "per_pixel_verdicts", "per_pixel", "gtag_ids",
                 "guest_recon", "payment_stage", "checkout_blockers",
                 "frame_harvest", "worker_harvest", "consent_at_gate",
                 "pixel_evidence_grade", "items_added_verified",
                 "fulfilment_result", "detected_pixel_ids")
        for _lk in leaks:
            _ev = getattr(_lk, "evidence", None)
            if not isinstance(_ev, dict):
                continue
            for _k in _keys:
                if _k in _ev and _k not in _audit and _ev[_k] not in (None, [], {}, ""):
                    _audit[_k] = _ev[_k]
        # Client-facing readability: replace heavy structures with a summary line.
        _heavy = {"pixel_census": "pixels", "per_pixel_verdicts": None,
                  "per_pixel": None, "frame_harvest": None, "worker_harvest": None,
                  "checkout_blockers": None, "detected_pixel_ids": None}
        for _lk in leaks:
            _ev = getattr(_lk, "evidence", None)
            if not isinstance(_ev, dict):
                continue
            for _k in list(_ev.keys()):
                if _k not in _heavy:
                    continue
                _v = _ev[_k]
                if _k == "pixel_census" and isinstance(_v, dict):
                    _ev[_k] = (f"{_v.get('total_ids', 0)} pixel ID(s) found; "
                               f"{_v.get('confirmed_real', 0)} confirmed live; "
                               f"{_v.get('transmitting', 0)} transmitting; "
                               f"{_v.get('static_only', 0)} dormant. See census below.")
                elif isinstance(_v, (list, dict)):
                    _ev[_k] = f"{len(_v)} item(s) — see detailed section below."
        template = self.env.get_template("teardown.md.j2")
        return template.render(page=page, leaks=leaks, fixes=fixes,
                               estimated_recovery=estimated_recovery,
                               audit=_audit, financial_data=financial_data)

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
