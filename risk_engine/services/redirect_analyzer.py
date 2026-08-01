"""Phase D: flags redirect hops that leave HTTPS or the official domain
whitelist before the user reaches the final target URL - the "detect
unexpected redirects" / "detect suspicious navigation" requirements.
"""

from .domain_verifier import is_domain_allowed, is_https


def analyze_redirect_chain(redirect_chain: list[str], allowed_domains: list[str]) -> list[str]:
    """Returns one human-readable finding per unsafe hop in `redirect_chain`
    (oldest hop first). An empty return value means every hop supplied was
    HTTPS and on the whitelist; it does NOT mean no redirect happened, only
    that whatever was reported checked out.
    """

    findings: list[str] = []
    for index, url in enumerate(redirect_chain, start=1):
        if not is_https(url):
            findings.append(f"Redirect hop {index} ({url}) is not served over HTTPS.")
        if not is_domain_allowed(url, allowed_domains):
            findings.append(f"Redirect hop {index} ({url}) is outside the official domain whitelist.")
    return findings
