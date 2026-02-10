import os
from dataclasses import dataclass

import dotenv

dotenv.load_dotenv()


@dataclass
class Settings:
    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    admin_username: str
    admin_password: str

    consumer_key: str
    consumer_secret: str

    terminal_id: str
    terminal_password: str
    base_url: str

    @property
    def db_url(self):
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings(
    db_host=os.getenv("POSTGRES_HOST", "localhost"),
    db_port=int(os.getenv("POSTGRES_PORT", "5432")),
    db_name=os.getenv("POSTGRES_DB"),
    db_user=os.getenv("POSTGRES_USER"),
    db_password=os.getenv("POSTGRES_PASSWORD"),
    admin_username=os.getenv("ADMIN_USERNAME"),
    admin_password=os.getenv("ADMIN_PASSWORD"),
    consumer_key=os.getenv("CONSUMER_KEY"),
    consumer_secret=os.getenv("CONSUMER_SECRET"),
    terminal_id=os.getenv("TERMINAL_ID"),
    terminal_password=os.getenv("TERMINAL_PASSWORD"),
    base_url=os.getenv("BASE_URL"),
)
