from pydantic import BaseModel

class SpamRequestModel(BaseModel):
    task_id: str  # ← НОВОЕ: уникальный ID задачи
    url: str
    cookies_list: list[dict] | None = None
    proxies: list[str] | None = None
    proxies_string: str | None = None
    count: int = 100
    concurrency: int = 200
    min_delay: float = 0.1
    max_delay: float = 0.3
    session_pool_size: int = 10
    slow_mode: bool = False
