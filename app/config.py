from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"   # ignore unknown env vars
    )

    DATABASE_URL: str
    JWT_SECRET: str
    GROQ_API_KEY: str
    ANTHROPIC_API_KEY: str = ""   # optional – required for Claude features

settings = Settings()
