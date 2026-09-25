from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str = ""
    webhook_base_url: str = ""  # публичный HTTPS-адрес сервера, напр. https://bot.example.com
    fly_app_name: str = ""  # выставляется Fly.io автоматически
    telegram_webhook_path: str = "/webhooks/telegram"
    getcourse_webhook_path: str = "/webhooks/getcourse"
    webapp_host: str = "0.0.0.0"
    webapp_port: int = 8000
    database_path: str = "selfheal.db"
    admin_telegram_id: int = 5925313775  # telegram_id администратора (команда /getfileid)
    # шаблон ссылки оплаты GetCourse: плейсхолдеры {track_id}, {telegram_id}, {track_title}
    getcourse_pay_url_template: str = (
        "https://edu.selfheal369.ru/pay-stub?track={track_id}&telegram_id={telegram_id}"
    )
    # ключ для GET /admin/db-dump (выгрузка базы для бэкапов); пусто = отключено
    backup_key: str = ""
    # прокси/замена Bot API endpoint (напр. https://tg-proxy.example.workers.dev),
    # когда api.telegram.org недоступен с сервера; пусто = https://api.telegram.org
    telegram_api_base: str = ""

    @property
    def public_base_url(self) -> str:
        if self.webhook_base_url:
            return self.webhook_base_url.rstrip("/")
        if self.fly_app_name:
            return f"https://{self.fly_app_name}.fly.dev"
        return ""

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.public_base_url}{self.telegram_webhook_path}"


settings = Settings()
