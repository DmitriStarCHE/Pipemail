from pathlib import Path

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


def test_render_returns_subject_and_body(
    template_dir: Path,
) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "СтальТорг"
    company.region = "Челябинск"

    subject, body = render_template("trader", company, _dir=template_dir)
    assert "СтальТорг" in subject
    assert "Здравствуйте, коллеги из г. Челябинск" in body


def test_render_greeting_without_city(template_dir: Path) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "СтальТорг"
    company.region = None

    subject, body = render_template("trader", company, _dir=template_dir)
    assert "Здравствуйте!" in body
    assert "коллеги из г." not in body


def test_missing_template_raises(tmp_path: Path) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "Test"
    company.region = None

    with pytest.raises(TemplateError):
        render_template("nonexistent", company, _dir=tmp_path)


def test_subject_rendered_with_company_name(template_dir: Path) -> None:
    from unittest.mock import MagicMock
    company = MagicMock()
    company.name = "МеталлГрупп"
    company.region = "Москва"

    subject, body = render_template("trader", company, _dir=template_dir)
    assert "МеталлГрупп" in subject
