# config.py
import json
import os
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


def env_file_from_env() -> str:
    app_env = os.getenv("APP_ENV", "development")
    return str(REPO_ROOT / "env" / app_env / "backend.env")


class Settings(BaseSettings):
    # pick the env file by APP_ENV, but allow overriding with ENV_FILE
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", env_file_from_env()),
        env_file_encoding="utf-8",
    )

    # ---- environment selection
    APP_ENV: Literal["development", "production"] = "development"

    # ---- optionals
    OPENAI_MODEL: str = "gpt-5"

    # ---- mandatory everywhere
    OPENAI_API_KEY: SecretStr
    CORS_ORIGINS: Union[str, List[str]]
    OS_HOST: HttpUrl  # stricter than str; ensures proper http(s)://...

    # ---- mandatory only in production (optional otherwise)
    OS_USER: Optional[str] = None
    OS_PASS: Optional[SecretStr] = None  # keep secrets out of repr

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if v is None or v == "":
            raise ValueError("CORS_ORIGINS must be defined")
        if isinstance(v, str):
            # accept JSON array or comma-separated values
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @model_validator(mode="after")
    def require_prod_creds(self):
        if self.APP_ENV == "production":
            missing = []
            if not self.OS_USER:
                missing.append("OS_USER")
            if not self.OS_PASS or not self.OS_PASS.get_secret_value().strip():
                missing.append("OS_PASS")
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        return self


settings = Settings()
