"""
SSRF protection submodule.

Provides URL validation and HTTP client wrapper to prevent Server-Side Request Forgery attacks.
"""

from .client import SSRFProtectedClient
from .constants import BLOCKED_HOSTNAMES, DNS_TIMEOUT_SECONDS, PRIVATE_IP_RANGES
from .validation import DNSResolutionError, is_safe_url

__all__ = [
    "SSRFProtectedClient",
    "is_safe_url",
    "DNSResolutionError",
    "BLOCKED_HOSTNAMES",
    "PRIVATE_IP_RANGES",
    "DNS_TIMEOUT_SECONDS",
]
