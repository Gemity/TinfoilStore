from pydantic_settings import BaseSettings, SettingsConfigDict


from datetime import timezone, timedelta

# Vietnam timezone (UTC+7)
VN_TZ = timezone(timedelta(hours=7))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/tinfoilstore"

    JWT_SECRET_KEY: str = "changeme-set-a-real-secret"
    JWT_ACCESS_TOKEN_TTL_MINUTES: int = 60
    ENABLE_HTTP_SHOP: bool = False

    WASABI_ACCESS_KEY_ID: str = ""
    WASABI_SECRET_ACCESS_KEY: str = ""
    WASABI_BUCKET: str = ""
    WASABI_REGION: str = "us-east-1"
    WASABI_ENDPOINT_URL: str = "https://s3.wasabisys.com"
    WASABI_PRESIGN_TTL_SECONDS: int = 300


settings = Settings()

