from api.v1.request_models.spam import SpamRequestModel
from core.utils.x_spam import start_mass_reply
from core.utils.task_storage import init_task, finish_task, get_task_result, update_task_progress
import asyncio
import random


async def start_spamming(data: SpamRequestModel):
    """Бесконечный параллельный спам с полным concurrency"""
    await init_task(data.task_id, 0)  # total=0 для бесконечной
    success = True
    batch_count = 0
    try:
        while True:
            # Проверяем флаг остановки (на случай штатного завершения)
            task = await get_task_result(data.task_id)
            if task and task.get("stopped", False):
                print(f"🛑 Task {data.task_id} stopped by user (flag)")
                success = True
                break

            batch_count += 1
            batch_size = data.concurrency * 5

            print(f"🚀 Task {data.task_id}: Batch #{batch_count}, size={batch_size}, concurrency={data.concurrency}")

            batch_success = await start_mass_reply(
                url=data.url,
                cookies_list=data.cookies_list,
                proxies=data.proxies,
                proxies_string=data.proxies_string,
                count=1000 if not data.slow_mode else 100,
                concurrency=data.concurrency,
                min_delay=data.min_delay,
                max_delay=data.max_delay,
                session_pool_size=data.session_pool_size,
                slow_mode=data.slow_mode,
                task_id=data.task_id
            )

            # Пауза между батчами (1-3 сек)
            await asyncio.sleep(random.uniform(1, 3))

        await finish_task(data.task_id, success)
    except asyncio.CancelledError:
        print(f"🛑 Task {data.task_id} instantly cancelled via API")
        await finish_task(data.task_id, True) # Помечаем как корректно остановленную
        raise # Пробрасываем выше, чтобы asyncio корректно закрыл корутину
    except Exception as e:
        print(f"❌ Error in task {data.task_id}: {e}")
        await finish_task(data.task_id, False)

