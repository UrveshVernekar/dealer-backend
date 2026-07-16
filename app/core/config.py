from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Any

class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str = "Dealer Schemes"
    SECRET_KEY: str = "supersecretkeyfordealerbackenddevelopmentuseonly"
    BACKEND_CORS_ORIGINS: str | list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                return json.loads(v)
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return []

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
