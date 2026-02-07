from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "sqlite+pysqlite:///./vf_agent.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"


settings = Settings()
