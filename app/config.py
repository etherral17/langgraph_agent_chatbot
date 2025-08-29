from pydantic_settings import BaseSettings
from pydantic import Field, AnyHttpUrl
from typing import Optional

# ...existing code...

class Settings(BaseSettings):
    APP_NAME: str = "lang-graph-agent"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    # MCP endpoints - point to real services in prod
    MCP_COMMON_URL: AnyHttpUrl = Field(..., env="MCP_COMMON_URL")
    MCP_ATLAS_URL: AnyHttpUrl = Field(..., env="MCP_ATLAS_URL")
    MCP_TIMEOUT_SECONDS: int = 10

    # Database (Postgres)
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    # Retry config
    RETRY_ATTEMPTS: int = 3
    RETRY_WAIT_SECONDS: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()