"""Error taxonomy for Ad-Leak-Engine [SEED: 2399]."""


class AdLeakEngineError(Exception):
    """Base exception for all engine errors."""


class SchemaDriftError(AdLeakEngineError):
    """GraphQL response keys changed unexpectedly."""


class RateLimitError(AdLeakEngineError):
    """HTTP 429 - too many requests."""


class BlockedError(AdLeakEngineError):
    """HTTP 403 after session handshake - access blocked."""


class ProxyDeadError(AdLeakEngineError):
    """Proxy failed repeated health checks."""


class PlatformAmbiguousError(AdLeakEngineError):
    """Fingerprint confidence too low for deterministic codegen."""


class CrawlerTimeoutError(AdLeakEngineError):
    """Page load exceeded the time budget."""


class CAPTCHAError(AdLeakEngineError):
    """CAPTCHA challenge detected in response."""


class EmptyResponseError(AdLeakEngineError):
    """Valid HTTP response but no usable ad data."""
