from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "backend-api"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = Field(default="sqlite:///./backend_api.db")
    jwt_secret: str = Field(default="change-me")
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 24 * 60
    s3_bucket: str = ""
    s3_region: str = ""
    cdn_base_url: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
