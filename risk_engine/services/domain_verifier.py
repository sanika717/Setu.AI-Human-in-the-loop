"""Phase D (Security Shield) checks: HTTPS enforcement and official-domain
whitelist verification. Pure functions, no I/O - the live whitelist itself
comes from the Official Service Registry via registry_client.py.
"""

from urllib.parse import urlparse


def is_https(url: str) -> bool:
    """True only for an https:// URL with a non-empty host."""

    parsed = urlparse(url)
    return parsed.scheme.lower() == "https" and bool(parsed.hostname)


def hostname_of(url: str) -> str | None:
    return urlparse(url).hostname


def _host_matches(host: str, allowed_domain: str) -> bool:
    host = host.lower().rstrip(".")
    allowed_domain = allowed_domain.lower().lstrip(".").rstrip(".")
    return host == allowed_domain or host.endswith("." + allowed_domain)


def is_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    """True if `url`'s host is exactly one of `allowed_domains`, or a
    subdomain of one of them. An empty/unparsable host, or an empty
    whitelist, is always treated as NOT allowed - the Security Shield fails
    closed, never open.
    """

    host = hostname_of(url)
    if not host or not allowed_domains:
        return False
    return any(_host_matches(host, domain) for domain in allowed_domains)
