from typing import Dict, Any
from datetime import datetime
import asyncio

TASK_RESULTS: Dict[str, Dict[str, Any]] = {}
RUNNING_TASKS: Dict[str, asyncio.Task] = {}
STOP_EVENTS: Dict[str, asyncio.Event] = {}  # FIX: Event для мгновенной сигнализации
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
            "stopped": False,
        }


async def register_stop_event(task_id: str, event: asyncio.Event):
    """Регистрирует asyncio.Event для мгновенной остановки без lock"""
    async with _storage_lock:
        STOP_EVENTS[task_id] = event


async def register_running_task(task_id: str, task: asyncio.Task):
    """Привязывает asyncio.Task к ID задачи для возможности отмены"""
    async with _storage_lock:
        RUNNING_TASKS[task_id] = task


async def stop_task(task_id: str) -> bool:
    """Мгновенно останавливает задачу через Event + task.cancel()"""
    async with _storage_lock:
        if task_id not in TASK_RESULTS:
            return False

        TASK_RESULTS[task_id]["stopped"] = True
        TASK_RESULTS[task_id]["status"] = "stopping"

        # FIX: Сначала Event — синхронная операция, без await
        # send_one_comment увидит is_set()=True перед следующим HTTP-запросом
        event = STOP_EVENTS.get(task_id)
        if event:
            event.set()

        # Затем cancel() — прерывает текущий await в корутине
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
            return

        if success:
            task["successful"] += 1
        else:
            task["failed"] += 1
            if error_msg and len(task["errors"]) < 10:
                task["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "message": error_msg,
                })

        completed = task["successful"] + task["failed"]
        task["progress_percentage"] = (
            min(100, task["successful"] / completed * 100) if completed > 0 else 0
        )


async def finish_task(task_id: str, success: bool):
    """Завершает задачу"""
    async with _storage_lock:
        if task_id in TASK_RESULTS:
            if TASK_RESULTS[task_id].get("stopped"):
                TASK_RESULTS[task_id]["status"] = "stopped"
            else:
                TASK_RESULTS[task_id]["status"] = "completed" if success else "failed"
            TASK_RESULTS[task_id]["finished_at"] = datetime.now().isoformat()

        RUNNING_TASKS.pop(task_id, None)
        STOP_EVENTS.pop(task_id, None)  # FIX: чистим Event после завершения


async def get_task_result(task_id: str) -> Dict[str, Any] | None:
    """Получает результат задачи"""
    async with _storage_lock:
        return TASK_RESULTS.get(task_id)


async def delete_task(task_id: str):
    """Удаляет задачу из хранилища и прерывает, если она ещё идёт"""
    async with _storage_lock:
        # Сигналим через Event
        event = STOP_EVENTS.get(task_id)
        if event:
            event.set()

        task = RUNNING_TASKS.get(task_id)
        if task and not task.done():
            task.cancel()

        RUNNING_TASKS.pop(task_id, None)
        TASK_RESULTS.pop(task_id, None)
        STOP_EVENTS.pop(task_id, None)
