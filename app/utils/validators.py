"""URL validation and SSRF protection (T04).

Every URL is checked before any network call, and again on every redirect hop,
so internal or reserved addresses can never be fetched.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")


class URLValidationError(ValueError):
    """Base class for all validation failures."""

    code = "invalid_url"


class InvalidURLError(URLValidationError):
    code = "invalid_url"


class DisallowedSchemeError(URLValidationError):
    code = "disallowed_scheme"


class BlockedAddressError(URLValidationError):
    code = "blocked_address"


def _format_host(host: str) -> str:
    """Add brackets around IPv6 literals when rebuilding a URL."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    return f"[{host}]" if address.version == 6 else host


def _is_blocked_address(address: ipaddress._BaseAddress) -> bool:
    """True for any address that must never be reached from this service."""
    # Handle IPv4-mapped IPv6 addresses such as ::ffff:127.0.0.1
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _resolve_host(host: str) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to IP addresses without performing any HTTP request."""
    cleaned = host.strip("[]")
    try:
        return [ipaddress.ip_address(cleaned)]
    except ValueError:
        pass

    try:
        ascii_host = cleaned.encode("idna").decode("ascii")
    except UnicodeError:
        ascii_host = cleaned

    try:
        infos = socket.getaddrinfo(ascii_host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InvalidURLError(f"Could not resolve hostname '{host}': {exc}") from exc

    addresses: list[ipaddress._BaseAddress] = []
    for info in infos:
        try:
            candidate = ipaddress.ip_address(info[4][0])
        except (ValueError, IndexError):
            continue
        if candidate not in addresses:
            addresses.append(candidate)

    if not addresses:
        raise InvalidURLError(f"Hostname '{host}' resolved to no usable address")
    return addresses


def validate_url(raw: str, max_length: int = 2048) -> str:
    """Validate syntax and return a normalised http(s) URL string."""
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidURLError("URL must be a non-empty string")

    value = raw.strip()
    if len(value) > max_length:
        raise InvalidURLError(f"URL exceeds the maximum length of {max_length} characters")
    if any(character.isspace() for character in value):
        raise InvalidURLError("URL must not contain whitespace")

    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise DisallowedSchemeError(
            "Only http and https URLs are supported; received "
            f"'{parts.scheme or 'no scheme'}'"
        )
    if parts.username or parts.password:
        raise InvalidURLError("URL must not contain embedded credentials")

    host = parts.hostname
    if not host:
        raise InvalidURLError("URL must include a hostname")

    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidURLError("URL contains an invalid port") from exc
    if port is not None and port not in ALLOWED_PORTS:
        raise InvalidURLError(
            f"Port {port} is not allowed; only standard HTTP(S) ports 80 and 443 are accepted"
        )

    lower_host = host.rstrip(".").lower()
    if lower_host == "localhost" or lower_host.endswith(INTERNAL_SUFFIXES):
        raise BlockedAddressError(f"Internal hostname '{host}' is not allowed")

    try:
        literal = ipaddress.ip_address(lower_host)
    except ValueError:
        pass
    else:
        if _is_blocked_address(literal):
            raise BlockedAddressError(f"Private or reserved address '{host}' is not allowed")

    netloc = _format_host(lower_host)
    if port is not None:
        netloc += f":{port}"

    normalised = urlunsplit(
        (scheme, netloc, parts.path or "/", parts.query, "")
    )
    return normalised


def assert_public_address(url: str) -> None:
    """Resolve the URL host and reject private/reserved addresses."""
    host = urlsplit(url).hostname
    if not host:
        raise InvalidURLError("URL must include a hostname")
    for address in _resolve_host(host):
        if _is_blocked_address(address):
            raise BlockedAddressError(
                f"Host resolves to blocked address '{address}'; access denied"
            )


def ensure_public_url(raw: str, max_length: int = 2048) -> str:
    """Validate syntax and resolve the host before any request is made."""
    url = validate_url(raw, max_length=max_length)
    assert_public_address(url)
    return url
