import asyncio
from fastapi import APIRouter, HTTPException
from api.v1.request_models.spam import SpamRequestModel
from api.v1.services.spaming import start_spamming
from core.utils.task_storage import get_task_result, delete_task, stop_task

router = APIRouter(tags=["Spam"])


@router.post("/spam")
async def spam(data: SpamRequestModel):
    """Запускает бесконечную рассылку с полным concurrency"""
    asyncio.create_task(start_spamming(data))
    return {
        "message": "Infinite spam started with full concurrency",
        "task_id": data.task_id,
        "status_url": f"/api/v1/spam/status/{data.task_id}",
        "stop_url": f"/api/v1/spam/{data.task_id}/stop"
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
    """Останавливает задачу (установка флага stopped)"""
    task = await get_task_result(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in ["running", "stopping"]:
        raise HTTPException(status_code=400, detail="Task not running")

    stopped = await stop_task(task_id)
    if stopped:
        return {"message": f"Stop requested for task {task_id}. Finishing current batch..."}
    raise HTTPException(status_code=500, detail="Failed to stop task")


@router.delete("/spam/status/{task_id}")
async def delete_spam_task(task_id: str):
    """Удаляет завершённую задачу из хранилища"""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    await delete_task(task_id)
    return {"message": f"Task {task_id} deleted successfully"}
