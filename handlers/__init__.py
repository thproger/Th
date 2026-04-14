from aiogram import Dispatcher
from .registration import router as registration_router
from .tasks import router as tasks_router
from .groups import router as groups_router


def register_all_handlers(dp: Dispatcher):
    dp.include_router(registration_router)
    dp.include_router(tasks_router)
    dp.include_router(groups_router)
