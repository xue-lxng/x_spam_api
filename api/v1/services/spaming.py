from api.v1.request_models.spam import SpamRequestModel
from core.utils.x_spam import start_mass_reply
from core.utils.task_storage import init_task, finish_task


async def start_spamming(data: SpamRequestModel):
    """Запускает рассылку и отслеживает результат"""
    # Инициализируем задачу в хранилище
    await init_task(data.task_id, data.count)

    try:
        # Запускаем рассылку с передачей task_id
        success = await start_mass_reply(
            url=data.url,
            cookies_list=data.cookies_list,
            proxies=data.proxies,
            proxies_string=data.proxies_string,
            count=data.count,
            concurrency=data.concurrency,
            min_delay=data.min_delay,
            max_delay=data.max_delay,
            session_pool_size=data.session_pool_size,
            slow_mode=data.slow_mode,
            task_id=data.task_id,  # ← НОВОЕ: передаём task_id
        )

        # Завершаем задачу
        await finish_task(data.task_id, success)

    except Exception as e:
        # При ошибке тоже фиксируем завершение
        await finish_task(data.task_id, success=False)
        print(f"❌ Ошибка в задаче {data.task_id}: {e}")
