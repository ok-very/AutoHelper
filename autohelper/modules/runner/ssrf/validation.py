"""
SSRF URL validation functions.

Provides DNS resolution and IP range checking for safe URL access.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from .constants import BLOCKED_HOSTNAMES, DNS_TIMEOUT_SECONDS, PRIVATE_IP_RANGES

# Blocked hostname suffixes for subdomain matching
BLOCKED_HOSTNAME_SUFFIXES = {
    ".localhost",
    ".internal",
    ".metadata.google.internal",
}


class DNSResolutionError(Exception):
    """Raised when DNS resolution fails for a hostname."""

    pass


def _resolve_all_ips(hostname: str) -> list[str]:
    """
    Resolve hostname to all IP addresses (both IPv4 and IPv6).

    Returns:
        List of IP address strings

    Raises:
        DNSResolutionError: If hostname cannot be resolved (DNS failure, timeout, etc.)
    """
    ips: list[str] = []
    try:
        # Use getaddrinfo to get both IPv4 and IPv6 addresses
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for result in results:
            ip_str = str(result[4][0])  # Ensure string type for IP address
            if ip_str not in ips:
                ips.append(ip_str)
    except (TimeoutError, socket.gaierror, socket.herror, OSError) as e:
        # DNS/network resolution errors should be treated as unsafe
        # - gaierror: address-related errors
        # - herror: legacy host errors
        # - timeout: DNS resolution timeout
        # - OSError: other system-level network errors
        raise DNSResolutionError(f"Failed to resolve hostname '{hostname}': {e}") from e
    return ips


def _check_ips_against_private_ranges(ips: list[str]) -> tuple[bool, str]:
    """
    Check if any of the IPs are in private/internal ranges.

    Returns:
        Tuple of (is_private, error_message)
    """
    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in PRIVATE_IP_RANGES:
                if ip in network:
                    return True, f"URL resolves to private/internal IP: {ip_str}"
        except ValueError:
            # Invalid IP address format, skip
            continue
    return False, ""


async def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.

    Checks:
    - Only http/https schemes allowed
    - Hostname not in blocklist
    - Resolved IPs not in private ranges

    Args:
        url: The URL to validate

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)
    except ValueError as e:
        # urlparse can raise ValueError for malformed URLs
        return False, f"Invalid URL format: {e}"

    # Only allow http/https
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme: {parsed.scheme}"

    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid URL: no hostname"

    # Normalize hostname: lowercase, strip trailing dot, handle IDNA
    hostname_lower = hostname.lower().rstrip(".")

    # Strip IPv6 zone ID if present (e.g., "fe80::1%eth0" -> "fe80::1")
    if "%" in hostname_lower:
        hostname_lower = hostname_lower.split("%")[0]

    # Handle IDNA/punycode encoding for Unicode hostnames
    try:
        # Encode to ASCII (punycode) then decode back to normalized form
        hostname_normalized = hostname_lower.encode("idna").decode("ascii").lower()
    except (UnicodeError, UnicodeDecodeError):
        # If IDNA encoding fails, use the original (will likely fail DNS anyway)
        hostname_normalized = hostname_lower

    # Check blocked hostnames (exact match)
    if hostname_normalized in BLOCKED_HOSTNAMES:
        return False, f"Blocked hostname: {hostname}"

    # Check blocked hostname suffixes (subdomain matching)
    for suffix in BLOCKED_HOSTNAME_SUFFIXES:
        if hostname_normalized.endswith(suffix) or hostname_normalized == suffix.lstrip("."):
            return False, f"Blocked hostname: {hostname}"

    # Check if hostname is an IP literal (skip DNS resolution)
    try:
        ip = ipaddress.ip_address(hostname_normalized)
        is_private, error_msg = _check_ips_against_private_ranges([str(ip)])
        if is_private:
            return False, error_msg
        return True, ""
    except ValueError:
        # Not an IP literal, proceed with DNS resolution
        pass

    # Try to resolve hostname and check if IP is private
    # Use asyncio.to_thread to avoid blocking the event loop
    # Resolve all IPs (both IPv4 and IPv6)
    # Add timeout to prevent unbounded blocking on slow/stuck DNS resolution
    try:
        ips = await asyncio.wait_for(
            asyncio.to_thread(_resolve_all_ips, hostname_normalized),
            timeout=DNS_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        # Sanitized error: don't expose timeout duration or internal details
        return False, "DNS resolution timed out"
    except DNSResolutionError:
        # Sanitized error: don't expose internal DNS error details
        return False, "DNS resolution failed for hostname"

    if not ips:
        # No IPs resolved (shouldn't happen if no exception, but be defensive)
        return False, f"No IP addresses resolved for hostname: {hostname}"

    is_private, error_msg = _check_ips_against_private_ranges(ips)
    if is_private:
        return False, error_msg

    return True, ""
