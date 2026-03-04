import asyncio
from fastapi import APIRouter, HTTPException
from api.v1.request_models.spam import SpamRequestModel
from api.v1.services.spaming import start_spamming
from core.utils.task_storage import (
    get_task_result,
    delete_task,
    stop_task,
    register_running_task,
    init_task,               # FIX: импортируем
    register_stop_event,     # FIX: импортируем
)

router = APIRouter(tags=["Spam"])


@router.post("/spam")
async def spam(data: SpamRequestModel):
    """Запускает бесконечную рассылку с полным concurrency"""

    # FIX 1: init_task ПЕРЕД create_task — исключаем race condition.
    # Если /stop придёт сразу после ответа, task_id уже есть в TASK_RESULTS.
    await init_task(data.task_id, 0)

    # FIX 2: Создаём Event и регистрируем его ДО запуска задачи.
    # stop_task() вызовет event.set() — send_one_comment увидит это синхронно.
    stop_event = asyncio.Event()
    await register_stop_event(data.task_id, stop_event)

    # FIX 3: Теперь создаём задачу и сразу регистрируем её handle.
    task = asyncio.create_task(start_spamming(data, stop_event))
    await register_running_task(data.task_id, task)

    return {
        "message": "Infinite spam started with full concurrency",
        "task_id": data.task_id,
        "status_url": f"/api/v1/spam/status/{data.task_id}",
        "stop_url": f"/api/v1/spam/{data.task_id}/stop",
    }


@router.get("/spam/status/{task_id}")
async def get_spam_status(task_id: str):
    """Получает статус выполнения задачи"""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.patch("/spam/{task_id}/stop")
async def stop_spam_task(task_id: str):
    """Мгновенно останавливает задачу"""
    task = await get_task_result(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ["running", "stopping"]:
        raise HTTPException(status_code=400, detail="Task not running")

    stopped = await stop_task(task_id)
    if stopped:
        return {"message": f"Stop requested for task {task_id}. Execution cancelled immediately."}
    raise HTTPException(status_code=500, detail="Failed to stop task")


@router.delete("/spam/status/{task_id}")
async def delete_spam_task(task_id: str):
    """Удаляет завершённую задачу из хранилища"""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    await delete_task(task_id)
    return {"message": f"Task {task_id} deleted successfully"}
