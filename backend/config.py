# config.py
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",   # tolerate extra env vars
    )

    # For docker-compose prod: backend talks to "opensearch" service
    OPENSEARCH_URL: str = "https://opensearch:9200"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    OS_USER: Optional[str] = None
    OS_PASS: Optional[str] = None
    OS_VERIFY_SSL: bool = False          # set to False for demo self-signed
    OS_CA_CERT: Optional[str] = None    # path to CA PEM if you want proper verify
    
    # You can switch to List[AnyHttpUrl] if you want URL validation
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    REQUEST_CONNECT_TIMEOUT: float = 3.0
    REQUEST_READ_TIMEOUT: float = 7.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if v is None or v == "":
            return v  # keep default
        if isinstance(v, str):
            try:
                parsed = json.loads(v)  # JSON array
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                # comma-separated
                return [s.strip() for s in v.split(",") if s.strip()]
        return v

settings = Settings()
