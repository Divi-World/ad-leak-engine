"""Stage interface contracts for Ad-Leak-Engine [SEED: 2399]."""
from abc import ABC, abstractmethod
from typing import Iterator

from .schemas import Fix, Leak, OutreachPack, Page, RawAd


class AbstractAdSource(ABC):
    """Ingest stage: collects ads from Meta Ad Library."""

    @abstractmethod
    def search(self, query: str, country: str, max_results: int = 100) -> Iterator[RawAd]:
        """Search Ad Library and yield normalized ads."""

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the source is operational."""


class AbstractLeakScanner(ABC):
    """Leak Scan stage: detects revenue leaks at a given tier."""

    @abstractmethod
    def scan(self, page: Page) -> list[Leak]:
        """Analyze a page and return all detected leaks."""

    @abstractmethod
    def tier(self) -> str:
        """Return which tier this scanner handles (L1/L2/L3)."""


class AbstractPlatformDetector(ABC):
    """Fingerprint stage: identifies the e-commerce platform."""

    @abstractmethod
    def detect(self, url: str, html: str | None = None, headers: dict | None = None) -> tuple[str, float]:
        """Return (platform_name, confidence_score)."""


class AbstractFixGenerator(ABC):
    """Fix Forge stage: generates platform-specific solutions."""

    @abstractmethod
    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        """Generate an executable fix for a detected leak."""

    @abstractmethod
    def supported_platforms(self) -> list[str]:
        """Return the list of platforms this generator handles."""


class AbstractOutreachBuilder(ABC):
    """Outreach stage: assembles client-facing packages."""

    @abstractmethod
    def build(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> OutreachPack:
        """Assemble a complete outreach bundle."""
