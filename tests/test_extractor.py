from outreach.harvest.extractor import extract_emails, EmailResult

SAMPLE_HTML = """
<html><body>
<a href="mailto:zakupki@steel-co.ru">Написать нам</a>
<p>Также пишите на sales@steel-co.ru или info[at]steel-co.ru</p>
<p>Спам: noreply@steel-co.ru</p>
<p>Бесплатный: manager@gmail.com</p>
</body></html>
"""


def test_extracts_mailto_first() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "zakupki@steel-co.ru" in emails
    mailto_result = next(r for r in results if r.email == "zakupki@steel-co.ru")
    assert mailto_result.priority <= 10


def test_extracts_plain_text_email() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "sales@steel-co.ru" in emails


def test_deobfuscates_at() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "info@steel-co.ru" in emails


def test_drops_noreply() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    emails = [r.email for r in results]
    assert "noreply@steel-co.ru" not in emails


def test_flags_free_provider() -> None:
    results = extract_emails(SAMPLE_HTML, "steel-co.ru")
    gmail = next((r for r in results if "gmail" in r.email), None)
    assert gmail is not None
    assert gmail.is_free_provider is True


def test_max_three_emails() -> None:
    html = " ".join(
        f'<a href="mailto:e{i}@corp.ru">e</a>' for i in range(10)
    )
    results = extract_emails(html, "corp.ru")
    assert len(results) <= 3


def test_role_email_flagged() -> None:
    html = '<a href="mailto:snab@corp.ru">snab</a>'
    results = extract_emails(html, "corp.ru")
    assert results[0].is_role is True
    assert results[0].priority <= 20


def test_deobfuscates_sobaka() -> None:
    html = "<p>contact[собака]company.ru</p>"
    results = extract_emails(html, "company.ru")
    assert any("contact@company.ru" == r.email for r in results)


def test_deobfuscates_paren_at() -> None:
    html = "<p>info(at)firm.ru</p>"
    results = extract_emails(html, "firm.ru")
    assert any("info@firm.ru" == r.email for r in results)


def test_drops_webmaster() -> None:
    html = '<a href="mailto:webmaster@corp.ru">link</a>'
    results = extract_emails(html, "corp.ru")
    assert not any("webmaster" in r.email for r in results)
