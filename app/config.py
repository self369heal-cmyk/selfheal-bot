from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str = ""
    webhook_base_url: str = ""  # публичный HTTPS-адрес сервера, напр. https://bot.example.com
    telegram_webhook_path: str = "/webhooks/telegram"
    getcourse_webhook_path: str = "/webhooks/getcourse"
    webapp_host: str = "0.0.0.0"
    webapp_port: int = 8000
    database_path: str = "selfheal.db"
    admin_telegram_id: int = 5925313775  # telegram_id администратора (команда /getfileid)

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.telegram_webhook_path}"


settings = Settings()
