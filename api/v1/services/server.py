from core.utils.server_params import get_or_create_device_info


async def get_params():
    return await get_or_create_device_info()