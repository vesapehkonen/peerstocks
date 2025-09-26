# config.py
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import HttpUrl, SecretStr, model_validator, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Let ENV_FILE override; otherwise read root .env
        env_file=os.getenv("ENV_FILE", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # <-- lets unknown env vars pass through
    )

    APP_ENV: Literal["dev", "prod"] = "dev"

    OS_HOST: HttpUrl
    OS_USER: Optional[str] = None
    OS_PASS: Optional[SecretStr] = None
    POLYGON_API_KEY: SecretStr

    @model_validator(mode="after")
    def finalize(self):
        if self.APP_ENV == "production":
            missing = []
            if not self.OS_USER:
                missing.append("OS_USER")
            if not self.OS_PASS or not self.OS_PASS.get_secret_value().strip():
                missing.append("OS_PASS")
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")

        host_str = str(self.OS_HOST)
        if self.APP_ENV == "dev":
            if host_str.startswith("https://"):
                host_str = "http://" + host_str[len("https://"):]
        elif self.APP_ENV == "prod":
            if host_str.startswith("http://"):
                host_str = "https://" + host_str[len("http://"):]
        self.OS_HOST = AnyHttpUrl(host_str)  # revalidate as proper HttpUrl

        return self

settings = Settings()
