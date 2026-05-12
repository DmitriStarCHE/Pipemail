from pathlib import Path
from unittest.mock import MagicMock

import pytest

from outreach.send.templates import TemplateError, render_template


@pytest.fixture()
def template_dir(tmp_path: Path) -> Path:
    content = (
        "Subject: Поставки труб — {{ company_name }}\n"
        "\n"
        "{{ greeting }}!\n"
        "\n"
        "Предлагаем трубы для {{ company_name }}.\n"
    )
    (tmp_path / "trader.txt").write_text(content, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def html_template_dir(tmp_path: Path) -> Path:
    content = (
        "<!-- Subject: Трубы для {{ company_name }} -->\n"
        "<html><body><p>{{ greeting }}!</p><p>Предлагаем трубы.</p></body></html>\n"
    )
    (tmp_path / "trader.html").write_text(content, encoding="utf-8")
    return tmp_path


def _company(name: str, region: str | None) -> MagicMock:
    c = MagicMock()
    c.name = name
    c.region = region
    return c


def test_render_returns_subject_and_body(template_dir: Path) -> None:
    subject, body, is_html = render_template("trader", _company("СтальТорг", "Челябинск"), _dir=template_dir)
    assert "СтальТорг" in subject
    assert "Здравствуйте, коллеги из г. Челябинск" in body
    assert is_html is False


def test_render_greeting_without_city(template_dir: Path) -> None:
    subject, body, is_html = render_template("trader", _company("СтальТорг", None), _dir=template_dir)
    assert "Здравствуйте!" in body
    assert "коллеги из г." not in body
    assert is_html is False


def test_missing_template_raises(tmp_path: Path) -> None:
    with pytest.raises(TemplateError):
        render_template("nonexistent", _company("Test", None), _dir=tmp_path)


def test_subject_rendered_with_company_name(template_dir: Path) -> None:
    subject, body, _ = render_template("trader", _company("МеталлГрупп", "Москва"), _dir=template_dir)
    assert "МеталлГрупп" in subject


def test_html_template_preferred_over_txt(tmp_path: Path) -> None:
    """HTML template takes precedence when both .html and .txt exist."""
    txt = "Subject: TXT\n\nBody txt.\n"
    html = "<!-- Subject: HTML subj -->\n<html><body><p>Body html.</p></body></html>\n"
    (tmp_path / "trader.txt").write_text(txt, encoding="utf-8")
    (tmp_path / "trader.html").write_text(html, encoding="utf-8")
    subject, body, is_html = render_template("trader", _company("Фирма", None), _dir=tmp_path)
    assert subject == "HTML subj"
    assert is_html is True


def test_html_template_subject_parsed(html_template_dir: Path) -> None:
    subject, body, is_html = render_template("trader", _company("МеталлТрейд", "Уфа"), _dir=html_template_dir)
    assert "МеталлТрейд" in subject
    assert is_html is True
    assert "<html>" in body
