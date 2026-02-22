from typing import Dict, Any
from datetime import datetime
import asyncio

# Глобальное хранилище результатов задач
TASK_RESULTS: Dict[str, Dict[str, Any]] = {}
# Хранилище объектов asyncio.Task для мгновенной отмены
RUNNING_TASKS: Dict[str, asyncio.Task] = {}
_storage_lock = asyncio.Lock()


async def init_task(task_id: str, total_count: int):
    """Инициализирует задачу в хранилище"""
    async with _storage_lock:
        TASK_RESULTS[task_id] = {
            "task_id": task_id,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "total": total_count,  # 0 для бесконечной
            "successful": 0,
            "failed": 0,
            "errors": [],
            "progress_percentage": 0.0,
            "stopped": False  # флаг остановки
        }


async def register_running_task(task_id: str, task: asyncio.Task):
    """Привязывает asyncio.Task к ID задачи для возможности отмены"""
    async with _storage_lock:
        RUNNING_TASKS[task_id] = task


async def stop_task(task_id: str) -> bool:
    """Устанавливает флаг остановки задачи и мгновенно отменяет корутину"""
    async with _storage_lock:
        if task_id not in TASK_RESULTS:
            return False
        TASK_RESULTS[task_id]["stopped"] = True
        TASK_RESULTS[task_id]["status"] = "stopping"

        # ✨ Мгновенная отмена: вызываем cancel() у Task
        task = RUNNING_TASKS.get(task_id)
        if task and not task.done():
            task.cancel()

        return True


async def update_task_progress(task_id: str, success: bool, error_msg: str = None):
    """Обновляет прогресс выполнения задачи"""
    async with _storage_lock:
        if task_id not in TASK_RESULTS:
            return
        task = TASK_RESULTS[task_id]
        if task.get("stopped", False):
            return  # Прекращаем обновления если остановлено

        if success:
            task["successful"] += 1
        else:
            task["failed"] += 1
        if error_msg and len(task["errors"]) < 10:
            task["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "message": error_msg
            })
        # Для бесконечной задачи
        completed = task["successful"] + task["failed"]
        task["progress_percentage"] = min(100, (task["successful"] / completed * 100) if completed > 0 else 0)


async def finish_task(task_id: str, success: bool):
    """Завершает задачу"""
    async with _storage_lock:
        if task_id in TASK_RESULTS:
            if TASK_RESULTS[task_id].get("stopped"):
                TASK_RESULTS[task_id]["status"] = "stopped"
            else:
                TASK_RESULTS[task_id]["status"] = "completed" if success else "failed"
            TASK_RESULTS[task_id]["finished_at"] = datetime.now().isoformat()

        # Удаляем задачу из пула запущенных
        if task_id in RUNNING_TASKS:
            del RUNNING_TASKS[task_id]


async def get_task_result(task_id: str) -> Dict[str, Any] | None:
    """Получает результат задачи"""
    async with _storage_lock:
        return TASK_RESULTS.get(task_id)


async def delete_task(task_id: str):
    """Удаляет задачу из хранилища и прерывает, если она еще идет"""
    async with _storage_lock:
        task = RUNNING_TASKS.get(task_id)
        if task and not task.done():
            task.cancel()

        if task_id in RUNNING_TASKS:
            del RUNNING_TASKS[task_id]

        if task_id in TASK_RESULTS:
            del TASK_RESULTS[task_id]
