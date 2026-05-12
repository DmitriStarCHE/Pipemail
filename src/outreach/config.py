from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_url: str
    redis_url: str = "redis://localhost:6379"

    twogis_api_key: str = ""
    yandex_geo_key: str = ""

    smtp_host: str = "smtp.mail.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    sender_name: str = ""
    sender_email: str = ""
    reply_to: str = ""

    imap_host: str = "imap.mail.ru"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    llm_backend: Literal["ollama", "openai"] = "ollama"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    daily_send_limit: int = 100
    work_hours_start: int = 9
    work_hours_end: int = 18
    timezone: str = "Asia/Yekaterinburg"

    log_level: str = "INFO"

    twogis_default_categories: list[str] = [
        "трубы стальные",
        "металлопрокат",
        "нефтегазовое оборудование",
        "трубопроводная арматура",
    ]
    twogis_default_regions: list[int] = [1, 2, 4, 38, 70]


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
