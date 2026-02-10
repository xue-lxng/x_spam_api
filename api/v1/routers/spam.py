import asyncio
from fastapi import APIRouter, HTTPException
from api.v1.request_models.spam import SpamRequestModel
from api.v1.services.spaming import start_spamming
from core.utils.task_storage import get_task_result, delete_task

router = APIRouter(tags=["Spam"])


@router.post("/spam")
async def spam(data: SpamRequestModel):
    """Запускает массовую рассылку комментариев"""
    asyncio.create_task(start_spamming(data))
    return {
        "message": "Spam request received",
        "task_id": data.task_id,
        "status_url": f"/api/v1/spam/status/{data.task_id}"
    }


@router.get("/spam/status/{task_id}")
async def get_spam_status(task_id: str):
    """Получает статус выполнения задачи"""
    result = await get_task_result(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return result


@router.delete("/spam/status/{task_id}")
async def delete_spam_task(task_id: str):
    """Удаляет результат задачи из хранилища"""
    result = await get_task_result(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    await delete_task(task_id)
    return {"message": f"Task {task_id} deleted successfully"}
