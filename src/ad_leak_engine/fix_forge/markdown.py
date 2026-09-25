"""Step-by-step guide generation for Fix Forge [SEED: 2399]."""
from .codegen import CodeGenerator


class MarkdownGenerator:
    """Generates human-readable implementation guides."""

    def __init__(self):
        self.codegen = CodeGenerator()

    def generate(self, platform: str, context: dict) -> str:
        """Render the platform-specific guide template."""
        return self.codegen.render(platform, "guide.md.j2", context)
