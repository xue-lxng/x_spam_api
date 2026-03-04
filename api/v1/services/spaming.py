import asyncio
import random

from api.v1.request_models.spam import SpamRequestModel
from core.utils.x_spam import start_mass_reply, init_session_pool, cleanup_session_pool
from core.utils.task_storage import finish_task, update_task_progress


async def start_spamming(data: SpamRequestModel, stop_event: asyncio.Event):
    """Бесконечный параллельный спам с полным concurrency"""

    # FIX: init_task уже вызван в роутере — не дублируем.
    # FIX: Инициализируем пул сессий ОДИН РАЗ на весь срок жизни задачи.
    # Раньше пул создавался и уничтожался в каждом батче — лишние соединения.
    await init_session_pool(data.session_pool_size)

    success = True
    batch_count = 0

    try:
        while True:
            # FIX: Синхронная проверка Event — без await, без lock, мгновенно
            if stop_event.is_set():
                print(f"🛑 Task {data.task_id} stopped by event (between batches)")
                break

            batch_count += 1
            batch_size = data.concurrency * 5
            print(
                f"🚀 Task {data.task_id}: Batch #{batch_count}, "
                f"size={batch_size}, concurrency={data.concurrency}"
            )

            await start_mass_reply(
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
                task_id=data.task_id,
                stop_event=stop_event,  # FIX: передаём Event вглубь
            )

            # Проверяем сразу после батча — не спим лишний раз
            if stop_event.is_set():
                print(f"🛑 Task {data.task_id} stopped by event (after batch)")
                break

            await asyncio.sleep(random.uniform(1, 3))

        await finish_task(data.task_id, success)

    except asyncio.CancelledError:
        print(f"🛑 Task {data.task_id} instantly cancelled via task.cancel()")
        await finish_task(data.task_id, True)
        raise  # обязательно пробрасываем — asyncio должен знать, что задача отменена

    except Exception as e:
        print(f"❌ Error in task {data.task_id}: {e}")
        await finish_task(data.task_id, False)

    finally:
        # FIX: cleanup пула ОДИН РАЗ при завершении задачи (любом — стоп/ошибка/cancel)
        # asyncio.shield защищает cleanup от повторного CancelledError в finally
        try:
            await asyncio.shield(cleanup_session_pool())
        except asyncio.CancelledError:
            # shield поймал второй cancel — cleanup продолжит работу в фоне
            pass
        except Exception as e:
            print(f"⚠️ Session pool cleanup error: {e}")
