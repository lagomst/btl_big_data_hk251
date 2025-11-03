from typing import Annotated, Any
from pydantic import AnyUrl, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv
load_dotenv(override=True)

def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    API_V1_STR: str = "/v1"
    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []
    DEFAULT_KNOWLEDGE: str = "neo4j"
    PROJECT_NAME: str = "NewsRAG"

    # LLM settings
    LLM_MODEL: str = 'gpt-4o-mini'
    LLM_API_KEY: str  # <- Let pydantic load it from .env
    EMBEDDING_MODEL: str = 'text-embedding-3-large'
    EMBEDDING_MAX_TOKEN_SIZE: int = 8192
    EMBEDDING_FUNC_MAX_ASYNC: int = 16
    EMBEDDING_BATCH_NUM: int = 32

    VERBOSE: bool = True
    MAX_BUFFER_LENGTH: int = 128

settings = Settings()