from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    app_env: str = "local"
    database_url: str = "sqlite+pysqlite:///./vf_agent.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    databricks_server_hostname: str | None = None
    databricks_http_path: str | None = None
    databricks_access_token: str | None = None


settings = Settings()
