# config.py
import json
import os
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import HttpUrl, SecretStr, field_validator, model_validator, AnyHttpUrl
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

    OPENAI_MODEL: str = "gpt-5-mini"
    OPENAI_API_KEY: SecretStr
    CORS_ORIGINS: Optional[Union[str, List[str]]] = None
    OS_HOST: HttpUrl
    OS_USER: Optional[str] = None
    OS_PASS: Optional[SecretStr] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @model_validator(mode="after")
    def finalize(self):
        if not self.CORS_ORIGINS:
            self.CORS_ORIGINS = (
                ["http://localhost", "http://127.0.0.1:80"]
                if self.APP_ENV == "prod"
                else [
                    "http://localhost:8080", "http://127.0.0.1:8080",
                    "http://localhost:3000", "http://127.0.0.1:3000",
                ]
            )
        if self.APP_ENV == "prod":
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
