"""powstock settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./powstock.db"
    companies_house_api_key: str = ""
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    r2_account_id: str = "954612afb5a97bb15dddcdc70176813d"
    r2_endpoint: str = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
    r2_bucket: str = "powstock-garden"

    model_config = {"env_prefix": "POWSTOCK_"}


_settings = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
