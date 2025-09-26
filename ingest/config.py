# config.py
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


def env_file_from_env() -> str:
    app_env = os.getenv("APP_ENV", "development")
    return str(REPO_ROOT / "env" / app_env / "ingest.env")


class Settings(BaseSettings):
    # Load the right .env file (override with ENV_FILE if you want)
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", env_file_from_env()),
        env_file_encoding="utf-8",
    )

    # environment selection
    APP_ENV: Literal["development", "production"] = "development"

    # --- OpenSearch ---
    OS_HOST: HttpUrl  # required everywhere
    OS_USER: Optional[str] = None  # required in prod
    OS_PASS: Optional[SecretStr] = None  # required in prod

    # --- Polygon ---
    POLYGON_API_KEY: SecretStr  # required everywhere

    @model_validator(mode="after")
    def prod_requirements(self):
        if self.APP_ENV == "production":
            missing = []
            if not self.OS_USER: missing.append("OS_USER")
            if not (self.OS_PASS and self.OS_PASS.get_secret_value().strip()):
                missing.append("OS_PASS")
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        return self


settings = Settings()
