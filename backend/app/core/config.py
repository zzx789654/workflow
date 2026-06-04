from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://workflow:workflow_pass@localhost:5432/workflow_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    APP_ENV: str = "development"
    FIRST_SUPERADMIN_EMAIL: str = "admin@example.com"
    FIRST_SUPERADMIN_PASSWORD: str = "admin123456"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    def validate_production_secrets(self) -> None:
        """Refuse to start in production with insecure default credentials."""
        if self.APP_ENV == "production":
            weak_keys = {"dev_secret_key_change_in_production", ""}
            if self.SECRET_KEY in weak_keys:
                raise RuntimeError("SECRET_KEY must be set to a strong value in production")
            weak_passwords = {"admin123456", "change_me_admin_password", ""}
            if self.FIRST_SUPERADMIN_PASSWORD in weak_passwords:
                raise RuntimeError("FIRST_SUPERADMIN_PASSWORD must be set to a strong value in production")


settings = Settings()
settings.validate_production_secrets()
