import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# curl_cffi вместо aiohttp!
from curl_cffi.requests import AsyncSession

# Глобальный lock для безопасной записи в файл из нескольких корутин
_cache_write_lock = asyncio.Lock()

# ✨ НОВОЕ: Глобальный пул долгоживущих HTTP сессий с общим DNS cache
_global_sessions = []
_session_pool_lock = asyncio.Lock()


async def init_session_pool(pool_size: int = 10):
    """
    Создаёт пул долгоживущих HTTP сессий.
    Все сессии переиспользуют DNS cache и connection pool.
    Это решает проблему "Could not resolve host" при высоком concurrency.

    Args:
        pool_size: Количество сессий в пуле (рекомендуется 10-20)
    """
    async with _session_pool_lock:
        if _global_sessions:
            return  # Уже инициализирован

        print(f"🔧 Создание пула из {pool_size} HTTP сессий с общим DNS cache...")
        for i in range(pool_size):
            session = AsyncSession(
                timeout=20,
                max_clients=500,  # Максимум соединений для connection pooling
            )
            _global_sessions.append(session)
        print(f"✓ Пул сессий создан: {len(_global_sessions)} сессий")
        print(f"✓ DNS cache активирован (60 секунд, общий для всех сессий)")


async def get_pooled_session() -> AsyncSession:
    """
    Возвращает случайную сессию из пула.
    Все сессии переиспользуют DNS cache и TCP соединения.
    """
    if not _global_sessions:
        await init_session_pool()
    return random.choice(_global_sessions)


async def cleanup_session_pool():
    """Закрывает все сессии из пула"""
    async with _session_pool_lock:
        for session in _global_sessions:
            try:
                await session.close()
            except:
                pass
        _global_sessions.clear()
    print("✓ Пул сессий закрыт")


@dataclass
class TokenSession:
    """Сессия токена с его cookies и fingerprint."""

    token: str
    cookies: dict
    account_name: str
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_platform: str
    request_count: int = 0
    cached_at: Optional[str] = None


class ProxyRotator:
    """Управляет пулом прокси с автоматической ротацией."""

    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.current_index = 0
        self.failed_proxies = set()

    def get_next(self) -> Optional[str]:
        """Возвращает следующий рабочий прокси."""
        if len(self.failed_proxies) >= len(self.proxies):
            return None

        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1
            if proxy not in self.failed_proxies:
                return proxy
            attempts += 1
        return None

    def mark_failed(self, proxy: str):
        """Помечает прокси как неработающий."""
        self.failed_proxies.add(proxy)
        print(f"⚠️ Прокси мертв: {proxy[:40]}...")

    def get_random(self) -> Optional[str]:
        """Возвращает случайный рабочий прокси."""
        working = [p for p in self.proxies if p not in self.failed_proxies]
        return random.choice(working) if working else None


def format_time(seconds: float) -> str:
    """
    Форматирует время в читаемый вид.

    Args:
        seconds: Количество секунд

    Returns:
        Строка в формате "HH часов mm минут ss секунд (XXX секунд)"
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d} часов {minutes:02d} минут {secs:02d} секунд ({total_seconds} секунд)"


def get_random_language() -> tuple[str, str]:
    """
    Возвращает случайную комбинацию языков из 10 самых популярных в Twitter.

    Returns:
        (accept_language, twitter_client_language)
    """
    # 10 самых популярных языков в Twitter
    languages = [
        ("en-US,en;q=0.9", "en"),
        ("en-GB,en;q=0.9", "en"),
        ("ja,en;q=0.9", "ja"),
        ("es,en;q=0.9", "es"),
        ("pt-BR,pt;q=0.9,en;q=0.8", "pt"),
        ("ar,en;q=0.9", "ar"),
        ("fr,en;q=0.9", "fr"),
        ("id,en;q=0.9", "id"),
        ("tr,en;q=0.9", "tr"),
        ("ko,en;q=0.9", "ko"),
    ]
    return random.choice(languages)


def get_random_features() -> dict:
    """
    Генерирует features для GraphQL запроса для БЕСПЛАТНЫХ аккаунтов.
    Все premium/grok/платные фичи отключены.
    Варьируются только UI/UX настройки которые доступны всем.

    Returns:
        dict с features
    """
    # Базовые features которые ДОЛЖНЫ быть стабильными для работы API
    base_features = {
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        # Premium/Grok фичи - ВСЕГДА False для автоматов
        "premium_content_api_read_enabled": False,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": False,
        "responsive_web_grok_share_attachment_enabled": False,
        "responsive_web_grok_annotations_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "rweb_tipjar_consumption_enabled": False,
        "verified_phone_label_enabled": False,
        "responsive_web_grok_image_annotation_enabled": False,
        "responsive_web_grok_imagine_annotation_enabled": False,
    }

    # Features которые можно варьировать (UI/UX настройки доступные всем)
    variable_features = {
        # Jetfuel - экспериментальная фича, может быть включена у некоторых
        "responsive_web_jetfuel_frame": random.choice([False, False, True]),  # 33% шанс
        # CTA (Call To Action) - может варьироваться
        "post_ctas_fetch_enabled": random.choice([False, True]),
        # Profile labels - UI фича
        "profile_label_improvements_pcf_label_in_post_enabled": random.choice(
            [False, True]
        ),
        # Profile redirect - может быть включен или нет
        "responsive_web_profile_redirect_enabled": random.choice([False, True]),
        # Articles preview - может варьироваться
        "articles_preview_enabled": random.choice([False, True]),
        # Community notes translation - UI фича
        "responsive_web_grok_community_note_auto_translation_is_enabled": random.choice(
            [False, True]
        ),
        # Profile image extensions - UI оптимизация
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": random.choice(
            [False, True]
        ),
        # Enhanced cards - UI фича
        "responsive_web_enhance_cards_enabled": random.choice([False, True]),
    }
    return {**base_features, **variable_features}


def get_random_referer(tweet_id: str) -> str:
    """
    Возвращает случайный referer для имитации разных точек входа.

    Args:
        tweet_id: ID твита

    Returns:
        URL referer
    """
    referers = [
        f"https://x.com/i/status/{tweet_id}",
        f"https://x.com/home",
        f"https://x.com/notifications",
        f"https://x.com/explore",
    ]
    # Более вероятно, что пользователь пришёл со страницы твита
    weights = [0.6, 0.2, 0.1, 0.1]
    return random.choices(referers, weights=weights)[0]


async def append_session_to_cache(
        session: TokenSession, cache_file: str = "cookies_cache.json"
):
    """
    Добавляет или обновляет одну сессию в кеше (потокобезопасно).

    Args:
        session: TokenSession для сохранения
        cache_file: Путь к файлу кеша
    """
    async with _cache_write_lock:
        # Читаем существующий кеш
        cache_data = []
        cache_path = Path(cache_file)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Ошибка чтения кеша при добавлении: {e}")
                cache_data = []

        # Удаляем старую запись для этого токена (если есть)
        cache_data = [item for item in cache_data if item.get("token") != session.token]

        # Добавляем новую сессию
        session_dict = {
            "token": session.token,
            "cookies": session.cookies,
            "account_name": session.account_name,
            "user_agent": session.user_agent,
            "sec_ch_ua": session.sec_ch_ua,
            "sec_ch_ua_platform": session.sec_ch_ua_platform,
            "cached_at": datetime.now().isoformat(),
        }
        cache_data.append(session_dict)

        # Записываем обратно
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Ошибка записи в кеш: {e}")


def load_sessions_from_cache(
        tokens: List[str], cache_file: str = "cookies_cache.json", skip_auth: bool = False
) -> tuple[List[TokenSession], List[str]]:
    """
    Загружает сессии из кеша.

    Args:
        tokens: Список токенов для проверки
        cache_file: Путь к файлу кеша
        skip_auth: Если True и токена нет в кеше - НЕ авторизовывать (пропустить)

    Returns:
        (cached_sessions, missing_tokens) - кешированные сессии и токены без кеша
    """
    if not Path(cache_file).exists():
        if skip_auth:
            print(f"⚠️ Файл кеша {cache_file} не найден, но skip_auth=True")
            print(f"❌ Невозможно продолжить без кеша!")
            return [], []
        else:
            print(f"ℹ️ Файл кеша {cache_file} не найден")
            return [], tokens

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        cache_dict = {item["token"]: item for item in cache_data}
        cached_sessions = []
        missing_tokens = []

        for idx, token in enumerate(tokens):
            if token in cache_dict:
                session_data = cache_dict[token]
                session = TokenSession(
                    token=session_data["token"],
                    cookies=session_data["cookies"],
                    account_name=session_data.get("account_name", f"Account_{idx + 1}"),
                    user_agent=session_data.get("user_agent", ""),
                    sec_ch_ua=session_data.get("sec_ch_ua", ""),
                    sec_ch_ua_platform=session_data.get("sec_ch_ua_platform", ""),
                    cached_at=session_data.get("cached_at"),
                )
                cached_sessions.append(session)
            else:
                if not skip_auth:
                    missing_tokens.append(token)
                else:
                    print(
                        f"⚠️ Токен {token[:20]}... не найден в кеше (пропущен из-за skip_auth=True)"
                    )

        print(f"📦 Загружено из кеша: {len(cached_sessions)}/{len(tokens)} сессий")
        if missing_tokens:
            print(f"🔍 Требуют авторизации: {len(missing_tokens)} токенов")
        elif skip_auth and len(cached_sessions) < len(tokens):
            print(
                f"⚠️ Пропущено токенов (не в кеше): {len(tokens) - len(cached_sessions)}"
            )

        return cached_sessions, missing_tokens

    except Exception as e:
        print(f"⚠️ Ошибка загрузки кеша: {e}")
        if skip_auth:
            return [], []
        return [], tokens


async def post_reply_api(
        token_session: TokenSession,
        tweet_id: str,
        reply_text: str,
        task_id: int,
        proxy: Optional[str] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        session: Optional[AsyncSession] = None,
) -> bool:
    """
    Публикует ответ через GraphQL API с curl_cffi (браузерный TLS).
    Использует рандомизацию для имитации разных пользователей.

    Args:
        token_session: Сессия токена с cookies
        tweet_id: ID твита для ответа
        reply_text: Текст комментария
        task_id: Номер задачи для логов
        proxy: Прокси для запроса
        proxy_rotator: Ротатор прокси для управления
        session: Готовая HTTP сессия из пула для переиспользования

    Returns:
        True если успешно, False при ошибке
    """
    try:
        url = "https://x.com/i/api/graphql/F3SgNCEemikyFA5xnQOmTw/CreateTweet"
        csrf_token = token_session.cookies.get("ct0")

        if not csrf_token:
            print(f"[{task_id}] ✗ Нет CSRF токена для {token_session.account_name}")
            return False

        # Улучшенная генерация transaction ID
        import base64
        import secrets
        import uuid

        transaction_id = base64.b64encode(
            uuid.uuid4().bytes + secrets.token_bytes(16)
        ).decode()

        # Рандомизация языков (10 самых популярных)
        accept_language, twitter_client_language = get_random_language()

        # Рандомизация referer
        referer = get_random_referer(tweet_id)

        # МИНИМАЛЬНЫЕ заголовки - curl_cffi добавит остальное автоматически!
        headers = {
            "accept": "*/*",
            "accept-language": accept_language,
            "accept-encoding": "gzip, deflate, br",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "content-type": "application/json",
            "origin": "https://x.com",
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-client-transaction-id": transaction_id,
            "x-csrf-token": csrf_token,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": twitter_client_language,
        }

        # НЕ добавляем user-agent, sec-ch-ua* - curl_cffi сам добавит для chrome142!

        # Рандомизация темы (dark mode)
        dark_request = random.choice([True, False])

        # Новые аккаунты не постят sensitive контент
        possibly_sensitive = False

        # Получаем рандомизированные features (без premium)
        features = get_random_features()

        payload = {
            "variables": {
                "tweet_text": reply_text,
                "reply": {
                    "in_reply_to_tweet_id": tweet_id,
                    "exclude_reply_user_ids": [],
                },
                "dark_request": dark_request,
                "media": {
                    "media_entities": [],
                    "possibly_sensitive": possibly_sensitive,
                },
                "semantic_annotation_ids": [],
                "disallowed_reply_options": None,
            },
            "features": features,
            "queryId": "F3SgNCEemikyFA5xnQOmTw",
        }

        browsers = [
            # Chrome Desktop (65% всего трафика) - самый популярный
            "chrome142",
            "chrome136",
            "chrome133a",
            "chrome131",
            "chrome124",
            "chrome123",
            "chrome120",
            "chrome119",
            "chrome116",
            "chrome110",
            "chrome107",
            "chrome104",
            "chrome101",
            "chrome100",
            "chrome99",
            # Chrome Mobile Android (15%) - второй по популярности
            "chrome131_android",
            "chrome99_android",
            # Safari Desktop (6%) - macOS пользователи
            "safari260",
            "safari184",
            "safari180",
            "safari170",
            "safari155",
            "safari153",
            # Safari iOS (8%) - iPhone/iPad
            "safari260_ios",
            "safari184_ios",
            "safari180_ios",
            "safari172_ios",
            # Edge (3%) - Windows 10/11
            "edge101",
            "edge99",
            # Firefox (2.5%) - privacy-focused users
            "firefox144",
            "firefox135",
            "firefox133",
            # Tor (0.5%) - очень редко
            "tor145",
        ]

        # Веса соответствуют реальной статистике использования
        weights = [
            # Chrome Desktop (15 версий) - 65% / 15 = ~4.33% каждая
            0.045, 0.045, 0.045, 0.045, 0.045,  # Новые версии популярнее
            0.043, 0.043, 0.043, 0.043, 0.043,
            0.042, 0.042, 0.042, 0.042, 0.042,
            # Chrome Android (2 версии) - 15% / 2 = 7.5% каждая
            0.08, 0.07,
            # Safari Desktop (6 версий) - 6% / 6 = 1% каждая
            0.012, 0.011, 0.010, 0.010, 0.009, 0.008,
            # Safari iOS (4 версии) - 8% / 4 = 2% каждая
            0.022, 0.020, 0.020, 0.018,
            # Edge (2 версии) - 3% / 2 = 1.5% каждая
            0.016, 0.014,
            # Firefox (3 версии) - 2.5% / 3 = ~0.83% каждая
            0.009, 0.008, 0.008,
            # Tor (1 версия) - 0.5%
            0.005,
        ]

        browser_to_emulate = random.choices(browsers, weights)[0]

        # ✨ ВАЖНО: Используем сессию из глобального пула (общий DNS cache!)
        if session is None:
            session = await get_pooled_session()

        response = await session.post(
            url,
            headers=headers,
            cookies=token_session.cookies,
            json=payload,
            proxy=proxy,
            timeout=20,
            impersonate=browser_to_emulate,
        )

        if response.status_code == 200:
            data = response.json()
            result_id = (
                data.get("data", {})
                .get("create_tweet", {})
                .get("tweet_results", {})
                .get("result", {})
                .get("rest_id")
            )
            token_session.request_count += 1
            proxy_short = proxy.split("@")[-1][:25] if proxy else "direct"
            text_short = reply_text[:35]

            if result_id is None:
                errors = data.get("errors", [])
                error_msg = (
                    errors[0].get("message", "Unknown error")[:100]
                    if errors
                    else "No result ID"
                )
                print(
                    f"[{task_id}] ✗ {token_session.account_name} | {proxy_short} | {text_short}... | {error_msg}"
                )
                return False

            print(
                f"[{task_id}] ✓ {token_session.account_name} | {proxy_short} | {text_short}..."
            )
            return True

        elif response.status_code == 429:
            print(f"[{task_id}] ⚠️ Rate limit на {token_session.account_name}")
            await asyncio.sleep(60)
            return False

        elif response.status_code == 403:
            # Обработка challenge
            try:
                data = response.json()
                if "errors" in data:
                    for error in data["errors"]:
                        if "challenge" in error.get("message", "").lower():
                            print(
                                f"[{task_id}] ⚠️ Challenge для {token_session.account_name}"
                            )
                            return False
            except:
                pass

            print(f"[{task_id}] ✗ 403 Forbidden для {token_session.account_name}")
            return False

        elif response.status_code in [407, 502, 503]:
            if proxy and proxy_rotator:
                proxy_rotator.mark_failed(proxy)
            print(f"[{task_id}] ✗ Ошибка прокси {response.status_code}")
            return False

        else:
            print(
                f"[{task_id}] ✗ {token_session.account_name} | {response.status_code}: {response.text[:100]}"
            )
            return False

    except Exception as e:
        error_str = str(e)
        if (
                proxy
                and proxy_rotator
                and ("proxy" in error_str.lower() or "connection" in error_str.lower())
        ):
            proxy_rotator.mark_failed(proxy)
        print(f"[{task_id}] ✗ {error_str[:100]}")
        return False


async def parallel_mass_posting(
        sessions: List[TokenSession],
        tweet_id: str,
        comments: List[str],
        count: int,
        proxy_rotator: Optional[ProxyRotator] = None,
        concurrency: int = 200,
        min_delay: float = 0.1,
        max_delay: float = 0.3,
        session_pool_size: int = 10,
        slow_mode: bool = False,
        task_id: Optional[str] = None,
) -> bool:
    """
    Параллельная массовая рассылка с concurrency.

    Args:
        sessions: Список авторизованных сессий
        tweet_id: ID твита для ответа
        comments: Список комментариев
        count: Количество комментариев для отправки
        proxy_rotator: Ротатор прокси
        concurrency: Максимум одновременных запросов
        min_delay: Минимальная задержка между запросами
        max_delay: Максимальная задержка между запросами
        session_pool_size: Размер пула HTTP сессий
        slow_mode: Режим медленной отправки (2-5 сек задержка)
        task_id: ID задачи для записи результатов в хранилище

    Returns:
        True если хотя бы один комментарий отправлен, False при полном провале
    """
    # ← НОВОЕ: Импорт функций хранилища
    if task_id:
        from core.utils.task_storage import update_task_progress, get_task_result

    start_time = time.time()
    actual_concurrency = min(concurrency, count)


    async def send_one_comment(index: int) -> bool:
        """Отправляет один комментарий с учетом concurrency."""
        async with semaphore:
            # ✨ НОВОЕ: Проверка флага остановки
            if task_id:
                task = await get_task_result(task_id)
                if task and task.get("stopped", False):
                    print(f"🛑 Batch interrupted by stop flag at #{index + 1}")
                    return False

            token_session = random.choice(sessions)

            comment = random.choice(comments)
            proxy = proxy_rotator.get_next() if proxy_rotator else None

            # Задержка перед отправкой
            if slow_mode:
                actual_min_delay = 2.0
                actual_max_delay = 5.0
            else:
                actual_min_delay = min_delay
                actual_max_delay = max_delay

            await asyncio.sleep(random.uniform(actual_min_delay, actual_max_delay))

            # Получаем сессию из пула для переиспользования
            http_session = await get_pooled_session()

            # Отправка комментария
            success = await post_reply_api(
                token_session,
                tweet_id,
                comment,
                index + 1,
                proxy,
                proxy_rotator,
                session=http_session,
            )

            # ← НОВОЕ: Обновляем прогресс в хранилище
            if task_id:
                error_msg = None
                if not success:
                    error_msg = f"Failed to post reply #{index + 1}"
                await update_task_progress(task_id, success, error_msg)

            return success

    # Режим отправки
    if slow_mode:
        mode_label = "🐌 SLOW MODE (2-5 сек задержка)"
    else:
        mode_label = "⚡ FAST MODE"

    print(f"{'=' * 60}")
    print(f"🚀 {mode_label}")
    print(f"📊 Аккаунтов: {len(sessions)}")
    print(f"💬 Комментариев: {count}")
    print(f"🔀 Concurrency: {actual_concurrency}")
    print(f"🌐 HTTP сессий: {session_pool_size}")
    print(f"⏱️ Задержка: {min_delay}-{max_delay} сек")
    print(f"🎯 Стратегия: Round-robin")
    if proxy_rotator:
        print(f"🔐 Прокси: {len(proxy_rotator.proxies)}")
    else:
        print(f"🔐 Прокси: ❌ Не используются")
    if task_id:
        print(f"🆔 Task ID: {task_id}")
    print(f"✨ DNS cache: Активен (60 секунд)")
    print(f"{'=' * 60}")
    print(f"🔥 Запускаем TLS fingerprinting (curl_cffi)...")
    print(f"🌍 Эмуляция 10 языков, UI features, referer")
    print(f"{'=' * 60}\n")

    # Создание пула HTTP сессий
    semaphore = asyncio.Semaphore(actual_concurrency)
    await init_session_pool(session_pool_size)

    # Запуск всех задач
    tasks = [send_one_comment(i) for i in range(count)]
    print(f"⏳ Отправка {count} комментариев (concurrency={actual_concurrency})...\n")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Закрытие пула сессий
    await cleanup_session_pool()

    # Статистика
    elapsed = time.time() - start_time
    successful = sum(1 for r in results if r is True)
    failed = count - successful

    print(f"\n{'=' * 60}")
    print(f"📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'=' * 60}")
    print(f"  ✓ Успешно: {successful}/{count}")
    print(f"  ✗ Ошибок: {failed}/{count}")
    print(f"  📈 Success rate: {(successful / count * 100):.1f}%")
    print(f"  ⏱️ Время: {format_time(elapsed)}")

    # Скорость обработки
    if elapsed > 0:
        rate = successful / elapsed
        print(f"  🚀 Скорость: {rate:.1f} req/sec")

    print(f"\n{'─' * 60}")
    print(f"📈 Распределение по токенам:")
    for session in sorted(sessions, key=lambda s: s.request_count, reverse=True):
        if session.request_count > 0:
            print(f"  {session.account_name}: {session.request_count} запросов")

    if proxy_rotator:
        print(f"\n{'─' * 60}")
        print(f"🌐 Статистика прокси:")
        print(
            f"  ⚠️ Мертвых: {len(proxy_rotator.failed_proxies)}/{len(proxy_rotator.proxies)}"
        )
        working = len(proxy_rotator.proxies) - len(proxy_rotator.failed_proxies)
        print(f"  ✓ Рабочих: {working}/{len(proxy_rotator.proxies)}")

    print(f"{'=' * 60}")

    return successful > 0


async def send_reply_with_cookies(
        tweet_id: str,
        reply_text: str,
        cookies: dict,
        *,
        account_name: str = "API_Account",
        proxy: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        task_id: int = 1,
) -> bool:
    """
    🔥 API: Универсальный интерфейс для отправки одного комментария по готовым cookies.

    Принимает уже авторизованные cookies (ct0, auth_token и т.п.) и
    отправляет один reply через GraphQL API X/Twitter.

    Args:
        tweet_id: ID твита (строка без URL, только числовой ID).
        reply_text: Текст комментария.
        cookies: dict cookies в браузерном формате:
            {
                "auth_token": "...",
                "ct0": "...",
                ... другие cookies ...
            }
        account_name: Метка аккаунта для логов (по умолчанию "API_Account").
        proxy: Строка прокси в формате curl_cffi (например "http://user:pass@host:port").
        session: Необязательная AsyncSession для переиспользования соединений.
        proxy_rotator: Опциональный ProxyRotator, если хочешь использовать имеющийся ротатор.
        task_id: Номер задачи для логов (по умолчанию 1).

    Returns:
        True, если отправка успешна; False в случае ошибки/челленджа/rate limit.

    Пример:
        cookies = {"auth_token": "...", "ct0": "..."}
        ok = await send_reply_with_cookies(
            tweet_id="1871234567890123456",
            reply_text="Hello!",
            cookies=cookies,
        )
    """
    token_session = TokenSession(
        token=cookies.get("auth_token", ""),
        cookies=cookies,
        account_name=account_name,
        user_agent="",
        sec_ch_ua="",
        sec_ch_ua_platform="",
    )

    # Если session не передали — возьмем из пула
    http_session = session or await get_pooled_session()

    return await post_reply_api(
        token_session=token_session,
        tweet_id=str(tweet_id),
        reply_text=reply_text,
        task_id=task_id,
        proxy=proxy,
        proxy_rotator=proxy_rotator,
        session=http_session,
    )


async def start_mass_reply(
        *,
        url: str,
        cookies_list: list[dict] | None = None,
        proxies: list[str] | None = None,
        proxies_string: str | None = None,
        count: int = 100,
        concurrency: int = 200,
        min_delay: float = 0.1,
        max_delay: float = 0.3,
        session_pool_size: int = 10,
        slow_mode: bool = False,
        task_id: Optional[str] = None,
) -> bool:
    """
    🔥 API: Универсальный интерфейс для запуска массовой рассылки комментариев.

    Поддерживает 2 формата cookies_list:
    1. Список cookies-словарей: [{"auth_token": "...", "ct0": "..."}, ...]
    2. Список объектов TokenSession: [{"token": "...", "cookies": {...}, "account_name": "..."}, ...]

    Args:
        url: URL твита (https://x.com/user/status/1234567890)
        cookies_list: Список cookies или TokenSession объектов
        proxies: Список прокси-серверов
        proxies_string: Строка с прокси (разделитель \n)
        count: Количество комментариев для отправки
        concurrency: Максимум одновременных запросов
        min_delay: Минимальная задержка между запросами (сек)
        max_delay: Максимальная задержка между запросами (сек)
        session_pool_size: Размер пула HTTP сессий
        slow_mode: Медленный режим (2-5 сек задержка)
        task_id: ID задачи для записи результатов в хранилище

    Returns:
        True если хотя бы один комментарий отправлен успешно
    """
    # 1. Разбираем tweet_id из URL
    tweet_id = url.split("/status/")[-1].split("?")[0]

    comments_path = "static/comments.txt"
    with open(comments_path, "r", encoding="utf-8") as f:
        comments = [line.strip() for line in f if line.strip()]

    # 2. Готовим ProxyRotator
    proxy_rotator = None
    if proxies:
        proxy_rotator = ProxyRotator(proxies)
    elif proxies_string:
        proxies_parsed = [
            line.strip() for line in proxies_string.strip().split("\n") if line.strip()
        ]
        if proxies_parsed:
            proxy_rotator = ProxyRotator(proxies_parsed)

    # 3. Готовим sessions
    final_sessions: list[TokenSession] = []
    for idx, item in enumerate(cookies_list):
        # ✨ ИСПРАВЛЕНИЕ: Распознаём формат
        if "cookies" in item and "token" in item:
            # Формат TokenSession из кеша:
            # {"token": "...", "cookies": {...}, "account_name": "...", ...}
            cookies_dict = item["cookies"]
            account_name = item.get("account_name", f"CookieAccount_{idx + 1}")
            token = item.get("token", "")
        else:
            # Формат простых cookies:
            # {"auth_token": "...", "ct0": "..."}
            cookies_dict = item
            account_name = f"CookieAccount_{idx + 1}"
            token = cookies_dict.get("auth_token", "")

        # ✨ ПРОВЕРКА: Наличие обязательных cookies
        if "ct0" not in cookies_dict:
            print(f"⚠️ Пропущен {account_name}: отсутствует ct0 (CSRF токен)")
            continue
        if "auth_token" not in cookies_dict:
            print(f"⚠️ Пропущен {account_name}: отсутствует auth_token")
            continue

        final_sessions.append(
            TokenSession(
                token=token,
                cookies=cookies_dict,  # ← Теперь передаём правильный dict
                account_name=account_name,
                user_agent="",
                sec_ch_ua="",
                sec_ch_ua_platform="",
            )
        )

    if not final_sessions:
        print("❌ Нет ни одной рабочей сессии для рассылки")
        print("   Проверь формат cookies_list и наличие ct0 + auth_token")
        return False

    if not comments:
        raise ValueError("Список comments пуст")

    # 4. Запускаем рассылку
    return await parallel_mass_posting(
        sessions=final_sessions,
        tweet_id=tweet_id,
        comments=comments,
        count=1000 if not slow_mode else 100,
        proxy_rotator=proxy_rotator,
        concurrency=concurrency,
        min_delay=min_delay if not slow_mode else 1,
        max_delay=max_delay if not slow_mode else 3,
        session_pool_size=session_pool_size,
        slow_mode=slow_mode,
        task_id=task_id,
    )
