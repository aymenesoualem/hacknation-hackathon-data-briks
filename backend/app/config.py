from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://vf:vf@localhost:5432/vf_agent"
    app_env: str = "local"


settings = Settings()
