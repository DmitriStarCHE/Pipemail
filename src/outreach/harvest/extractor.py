import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

_DROP_LOCAL = re.compile(
    r"^(noreply|no-reply|webmaster|postmaster|admin|abuse|hostmaster|root|mailer-daemon)$",
    re.IGNORECASE,
)

_ROLE_LOCAL = {
    "info", "sales", "office", "hello", "contact", "support",
    "sekretar", "secretary", "zakupki", "snab", "omts",
    "prodaja", "prodazhi",
}

_FREE_PROVIDERS = {
    "mail.ru", "gmail.com", "yandex.ru", "yandex.com",
    "yahoo.com", "rambler.ru", "list.ru", "bk.ru", "inbox.ru",
}

_DEOBFUSCATE = [
    (re.compile(r"\[at\]|\(at\)", re.IGNORECASE), "@"),
    (re.compile(r"\s+AT\s+", re.IGNORECASE), "@"),
    (re.compile(r"\[собака\]|\(собака\)", re.IGNORECASE), "@"),
    (re.compile(r"\[dot\]|\(точка\)", re.IGNORECASE), "."),
    (re.compile(r"\s+DOT\s+|\s+точка\s+", re.IGNORECASE), "."),
    (re.compile(r"&#64;|&commat;"), "@"),
]


@dataclass
class EmailResult:
    email: str
    priority: int = 50
    is_role: bool = False
    is_free_provider: bool = False


def extract_emails(html: str, company_domain: str) -> list[EmailResult]:
    """Extract, deduplicate, and rank email addresses from HTML."""
    tree = HTMLParser(html)
    for tag in tree.css("script, style"):
        tag.decompose()

    results: dict[str, EmailResult] = {}

    # mailto links — highest confidence
    for node in tree.css("a[href]"):
        href = node.attributes.get("href", "") or ""
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if addr and _EMAIL_RE.match(addr):
                _add(results, addr, mailto=True)

    # plain text (with deobfuscation)
    text = tree.body.text(separator=" ") if tree.body else tree.text()
    for pattern, replacement in _DEOBFUSCATE:
        text = pattern.sub(replacement, text)
    for match in _EMAIL_RE.finditer(text):
        addr = match.group(0).lower()
        _add(results, addr, mailto=False)

    sorted_results = sorted(results.values(), key=lambda r: r.priority)

    # If all results have the same priority (likely duplicates/junk),
    # limit to 3. Otherwise return all (different quality levels).
    priorities = {r.priority for r in sorted_results}
    if len(priorities) == 1:
        return sorted_results[:3]
    else:
        return sorted_results


def _add(results: dict[str, EmailResult], addr: str, *, mailto: bool) -> None:
    local, _, domain = addr.partition("@")
    if not domain:
        return
    if _DROP_LOCAL.match(local):
        return

    is_role = local in _ROLE_LOCAL or bool(
        re.match(r"^(zakup|snab)", local, re.IGNORECASE)
    )
    is_free = domain in _FREE_PROVIDERS

    if mailto:
        if re.match(r"^(zakup|snab)", local, re.IGNORECASE):
            priority = 10
        elif local in {"sales", "info"}:
            priority = 20
        else:
            priority = 30
    else:
        if re.match(r"^(zakup|snab)", local, re.IGNORECASE):
            priority = 30
        elif local in {"sales", "info"}:
            priority = 40
        else:
            priority = 50

    if is_free and is_role:
        priority += 20

    if addr not in results or results[addr].priority > priority:
        results[addr] = EmailResult(
            email=addr,
            priority=priority,
            is_role=is_role,
            is_free_provider=is_free,
        )
