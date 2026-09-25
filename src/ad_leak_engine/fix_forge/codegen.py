"""Template rendering engine for Fix Forge [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

TEMPLATE_DIR = Path(__file__).parent / "templates"


class CodeGenerator:
    """Renders Jinja2 templates into executable code blocks."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,  # Code output, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(self, platform: str, template_name: str, context: dict | None = None) -> str:
        """Render a platform template with the given context."""
        context = context or {}
        template_path = f"{platform}/{template_name}"
        try:
            template = self.env.get_template(template_path)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template.render(**context)

    def template_exists(self, platform: str, template_name: str) -> bool:
        """Check whether a template exists."""
        try:
            self.env.get_template(f"{platform}/{template_name}")
            return True
        except TemplateNotFound:
            return False
