import time

import dns.asyncresolver
import structlog

log = structlog.get_logger(__name__)

_cache: dict[str, tuple[bool, float]] = {}
_TTL = 86400.0  # 24 hours in seconds


async def has_valid_mx(domain: str) -> bool:
    """Return True if domain has at least one MX record. Results cached 24h."""
    now = time.monotonic()
    if domain in _cache:
        result, expires = _cache[domain]
        if now < expires:
            return result

    try:
        answers = await dns.asyncresolver.resolve(domain, "MX")
        valid = len(answers) > 0
    except Exception as exc:
        log.debug("verifier.mx_fail", domain=domain, error=str(exc))
        valid = False

    _cache[domain] = (valid, now + _TTL)
    return valid
