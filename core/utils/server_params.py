import asyncio
import base64
import json
import socket
import random
from pathlib import Path
from typing import Dict, Any

# BIP39 словарь (английские слова, первые 100 для примера)
BIP39_WORDS = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
    "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
    "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
    "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among",
    "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry",
    "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
    "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april",
    "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor",
    "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact"
]


async def get_local_ip() -> str:
    """Асинхронно получает локальный IP адрес устройства"""
    loop = asyncio.get_event_loop()

    def _get_ip():
        try:
            # Создаем UDP соединение для определения IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    return await loop.run_in_executor(None, _get_ip)


def generate_bip39_name() -> str:
    """Генерирует имя из 2 случайных слов BIP39"""
    word1 = random.choice(BIP39_WORDS)
    word2 = random.choice(BIP39_WORDS)
    return f"{word1}-{word2}"


async def get_or_create_device_info(
        json_path: str = "/app/data/device_info.json"
) -> str:
    """
    Асинхронно получает информацию об устройстве из JSON файла,
    или создает новую запись если файл не существует.

    Args:
        json_path: Путь к JSON файлу

    Returns:
        Base64 строка с информацией об устройстве
    """
    file_path = Path(json_path)

    # Если файл существует - читаем
    if file_path.exists():
        loop = asyncio.get_event_loop()

        def _read_json():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        data = await loop.run_in_executor(None, _read_json)

        return dict_to_base64(data)

    # Если файла нет - создаем новую запись
    ip_address = await get_local_ip()
    device_name = generate_bip39_name()

    device_info = {
        "ip": ip_address,
        "port": 8000,
        "name": device_name
    }

    # Асинхронно сохраняем в файл
    loop = asyncio.get_event_loop()

    def _write_json():
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(device_info, f, ensure_ascii=False, indent=2)

    await loop.run_in_executor(None, _write_json)

    result =  dict_to_base64(device_info)
    return result


def dict_to_base64(data: Dict[str, Any]) -> str:
    """
    Преобразует словарь в Base64 строку.
    """
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    base64_bytes = base64.b64encode(json_bytes)
    return base64_bytes.decode("ascii")


def base64_to_dict(base64_str: str) -> Dict[str, Any]:
    """
    Декодирует Base64 строку обратно в словарь.
    """
    base64_bytes = base64_str.encode("ascii")
    json_bytes = base64.b64decode(base64_bytes)
    json_str = json_bytes.decode("utf-8")
    return json.loads(json_str)
