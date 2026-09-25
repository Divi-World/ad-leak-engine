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

    def build(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> OutreachPack:
        """Assemble teardown, message, and evidence into an OutreachPack."""
        # Rank leaks by severity (highest first)
        leaks = sorted(leaks, key=lambda l: l.severity, reverse=True)

        teardown_md = self._generate_teardown(page, leaks, fixes)
        exec_summary = self.message_gen.generate_executive_summary(page, leaks)
        message_text = self.message_gen.generate_message(page, leaks, fixes)

        self.compliance.validate(message_text)
        estimated_recovery = self._estimate_recovery(leaks)

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

    def _generate_teardown(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> str:
        template = self.env.get_template("teardown.md.j2")
        return template.render(page=page, leaks=leaks, fixes=fixes)

    def _estimate_recovery(self, leaks: list[Leak]) -> str:
        high_sev = sum(1 for l in leaks if l.severity >= 0.8)
        med_sev = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
        recovery = (high_sev * 1000) + (med_sev * 300)
        return f"${recovery:,}/month potential recovery"
