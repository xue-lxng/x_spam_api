from typing import Dict, Any
from datetime import datetime
import asyncio

# Глобальное хранилище результатов задач
TASK_RESULTS: Dict[str, Dict[str, Any]] = {}
_storage_lock = asyncio.Lock()


async def init_task(task_id: str, total_count: int):
    """Инициализирует задачу в хранилище"""
    async with _storage_lock:
        TASK_RESULTS[task_id] = {
            "task_id": task_id,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "total": total_count,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "progress_percentage": 0.0,
        }


async def update_task_progress(task_id: str, success: bool, error_msg: str = None):
    """Обновляет прогресс выполнения задачи"""
    async with _storage_lock:
        if task_id not in TASK_RESULTS:
            return

        task = TASK_RESULTS[task_id]

        if success:
            task["successful"] += 1
        else:
            task["failed"] += 1
            if error_msg and len(task["errors"]) < 10:  # Храним max 10 последних ошибок
                task["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "message": error_msg
                })

        # Обновляем прогресс
        completed = task["successful"] + task["failed"]
        task["progress_percentage"] = (completed / task["total"]) * 100 if task["total"] > 0 else 0


async def finish_task(task_id: str, success: bool):
    """Завершает задачу"""
    async with _storage_lock:
        if task_id not in TASK_RESULTS:
            return

        TASK_RESULTS[task_id]["status"] = "completed" if success else "failed"
        TASK_RESULTS[task_id]["finished_at"] = datetime.now().isoformat()


async def get_task_result(task_id: str) -> Dict[str, Any] | None:
    """Получает результат задачи"""
    async with _storage_lock:
        return TASK_RESULTS.get(task_id)


async def delete_task(task_id: str):
    """Удаляет задачу из хранилища"""
    async with _storage_lock:
        if task_id in TASK_RESULTS:
            del TASK_RESULTS[task_id]
