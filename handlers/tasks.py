from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import TASK_STATUSES
from permissions import has_role, ROLE_ADMIN, ROLE_MANAGER, ROLE_GROUP_LEADER
from keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    users_list_keyboard,
    task_actions_keyboard,
    tasks_list_keyboard,
    task_filter_keyboard,
    BTN_CREATE_TASK,
    BTN_MY_TASKS,
    BTN_TASKS_ISSUED,
    BTN_GROUP_TASKS,
    BTN_ALL_TASKS,
    BTN_CANCEL,
)
from utils import format_task, build_stats

router = Router()


class CreateTaskStates(StatesGroup):
    selecting_assignee = State()
    entering_title = State()
    entering_description = State()
    entering_deadline = State()


class CommentStates(StatesGroup):
    entering_comment = State()


async def get_assignable_users(creator: dict) -> list:
    role = creator.get("role")
    if has_role(role, ROLE_ADMIN):
        return await db.get_all_users()
    if has_role(role, ROLE_MANAGER):
        all_users = await db.get_all_users()
        return [u for u in all_users if u["telegram_id"] != creator["telegram_id"] and u.get("role")]
    if has_role(role, ROLE_GROUP_LEADER):
        return await db.get_group_members(creator["telegram_id"])
    return []


@router.message(F.text == BTN_CREATE_TASK)
async def start_create_task(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await message.answer("❌ Немає доступу.")
        return

    assignees = await get_assignable_users(user)
    if not assignees:
        await message.answer("❌ Немає доступних виконавців.")
        return

    await state.set_state(CreateTaskStates.selecting_assignee)
    await message.answer("👤 Оберіть виконавця:", reply_markup=users_list_keyboard(assignees, "pick_assignee"))


@router.callback_query(F.data.startswith("pick_assignee:"), CreateTaskStates.selecting_assignee)
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    assignee_id = int(callback.data.split(":")[1])
    assignee = await db.get_user(assignee_id)
    if not assignee:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    await state.update_data(assignee_id=assignee_id)
    name = assignee.get("full_name") or assignee.get("username") or str(assignee_id)
    await state.set_state(CreateTaskStates.entering_title)
    await callback.message.edit_text(f"✏️ Виконавець: <b>{name}</b>\n\nВведіть назву завдання:", parse_mode="HTML")
    await callback.message.answer("Введи назву:", reply_markup=cancel_keyboard())


@router.message(CreateTaskStates.entering_title, F.text == BTN_CANCEL)
@router.message(CreateTaskStates.entering_description, F.text == BTN_CANCEL)
@router.message(CreateTaskStates.entering_deadline, F.text == BTN_CANCEL)
async def cancel_task_creation(message: Message, state: FSMContext):
    role = (await db.get_user(message.from_user.id) or {}).get("role", "member")
    await state.clear()
    await message.answer("❌ Створення завдання скасовано.", reply_markup=main_menu_keyboard(role))


@router.message(CreateTaskStates.entering_title)
async def enter_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Назва занадто коротка. Спробуй ще раз:")
        return
    await state.update_data(title=title)
    await state.set_state(CreateTaskStates.entering_description)
    await message.answer("📝 Введіть опис (або «-», щоб пропустити):")


@router.message(CreateTaskStates.entering_description)
async def enter_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    if description == "-":
        description = ""
    await state.update_data(description=description)
    await state.set_state(CreateTaskStates.entering_deadline)
    await message.answer("📅 Введіть дедлайн (або «-», щоб пропустити):")


@router.message(CreateTaskStates.entering_deadline)
async def enter_deadline(message: Message, state: FSMContext):
    deadline = (message.text or "").strip()
    if deadline == "-":
        deadline = None

    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    role = user.get("role", "member")

    task = await db.create_task(
        creator_id=message.from_user.id,
        assignee_id=data["assignee_id"],
        title=data["title"],
        description=data.get("description", ""),
        deadline=deadline,
    )
    await state.clear()

    task_text = await format_task(task)
    await message.answer(f"✅ Завдання створено!\n\n{task_text}", reply_markup=main_menu_keyboard(role), parse_mode="HTML")


@router.message(F.text == BTN_MY_TASKS)
async def my_tasks(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Ти ще не зареєстрований. Введи /start")
        return

    tasks = await db.get_tasks_for_user(message.from_user.id)
    if not tasks:
        await message.answer("📭 У тебе немає завдань.")
        return

    await message.answer(build_stats(tasks), parse_mode="HTML")
    await message.answer("📋 Твої завдання:", reply_markup=tasks_list_keyboard(tasks, "view_task"))


@router.message(F.text == BTN_TASKS_ISSUED)
async def tasks_issued(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_MANAGER):
        await message.answer("❌ Немає доступу.")
        return

    tasks = await db.get_tasks_created_by(message.from_user.id)
    if not tasks:
        await message.answer("📭 Ти ще не видавав завдань.")
        return

    await message.answer(f"{build_stats(tasks)}\n\n🔍 Фільтр:", reply_markup=task_filter_keyboard(), parse_mode="HTML")
    await message.answer("📋 Видані завдання:", reply_markup=tasks_list_keyboard(tasks, "view_task"))


@router.message(F.text == BTN_GROUP_TASKS)
async def group_tasks(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await message.answer("❌ Немає доступу.")
        return

    tasks = await db.get_tasks_for_group(message.from_user.id)
    if not tasks:
        await message.answer("📭 У групи немає завдань.")
        return

    await message.answer(f"{build_stats(tasks)}\n\n🔍 Фільтр:", reply_markup=task_filter_keyboard(), parse_mode="HTML")
    await message.answer("📋 Завдання групи:", reply_markup=tasks_list_keyboard(tasks, "view_task"))


@router.message(F.text == BTN_ALL_TASKS)
async def all_tasks(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return

    tasks = await db.get_all_tasks()
    if not tasks:
        await message.answer("📭 Завдань ще немає.")
        return

    await message.answer(f"{build_stats(tasks)}\n\n🔍 Фільтр:", reply_markup=task_filter_keyboard(), parse_mode="HTML")
    await message.answer("📋 Всі завдання:", reply_markup=tasks_list_keyboard(tasks, "view_task"))


@router.callback_query(F.data.startswith("filter_tasks:"))
async def filter_tasks(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Не авторизований.", show_alert=True)
        return

    status_filter = callback.data.split(":")[1]
    role = user.get("role")

    if has_role(role, ROLE_ADMIN):
        tasks = await db.get_all_tasks()
    elif has_role(role, ROLE_MANAGER):
        tasks = await db.get_tasks_created_by(callback.from_user.id)
    elif has_role(role, ROLE_GROUP_LEADER):
        tasks = await db.get_tasks_for_group(callback.from_user.id)
    else:
        tasks = await db.get_tasks_for_user(callback.from_user.id)

    if status_filter != "all":
        tasks = [t for t in tasks if t.get("status") == status_filter]

    label = TASK_STATUSES.get(status_filter, "Всі")
    if not tasks:
        await callback.answer(f"Немає завдань зі статусом «{label}».", show_alert=True)
        return

    await callback.message.answer(f"📋 Завдання ({label}):", reply_markup=tasks_list_keyboard(tasks, "view_task"))
    await callback.answer()


@router.callback_query(F.data.startswith("view_task:"))
async def view_task(callback: CallbackQuery):
    task_id = callback.data.split(":")[1]
    task = await db.get_task(task_id)
    if not task:
        await callback.answer("Завдання не знайдено.", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    role = user.get("role") if user else "member"
    is_assignee = task["assignee_id"] == callback.from_user.id

    await callback.message.answer(
        await format_task(task),
        reply_markup=task_actions_keyboard(task_id, role, is_assignee),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_status:"))
async def update_task_status(callback: CallbackQuery):
    task_id, new_status = callback.data.split(":")[1:3]

    task = await db.get_task(task_id)
    if not task:
        await callback.answer("Завдання не знайдено.", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    role = user.get("role") if user else "member"
    is_assignee = task["assignee_id"] == callback.from_user.id

    if new_status in ("in_progress", "done") and not is_assignee:
        await callback.answer("Лише виконавець може змінити цей статус.", show_alert=True)
        return
    if new_status == "cancelled" and not has_role(role, ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає прав.", show_alert=True)
        return

    await db.update_task_status(task_id, new_status)
    await callback.answer(f"✅ Статус оновлено: {TASK_STATUSES.get(new_status, new_status)}")


@router.callback_query(F.data.startswith("task_delete:"))
async def delete_task_confirm(callback: CallbackQuery):
    task_id = callback.data.split(":")[1]
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає прав.", show_alert=True)
        return

    from keyboards import confirm_keyboard

    await callback.message.edit_text(
        "🗑 Ви впевнені, що хочете видалити це завдання?",
        reply_markup=confirm_keyboard("delete_task", task_id),
    )


@router.callback_query(F.data.startswith("confirm_delete_task:"))
async def delete_task_confirmed(callback: CallbackQuery):
    task_id = callback.data.split(":")[1]
    await db.delete_task(task_id)
    await callback.message.edit_text("🗑 Завдання видалено.")
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery):
    await callback.message.edit_text("❌ Дію скасовано.")
    await callback.answer()


@router.callback_query(F.data.startswith("task_comment:"))
async def start_comment(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.split(":")[1]
    await state.update_data(comment_task_id=task_id)
    await state.set_state(CommentStates.entering_comment)
    await callback.message.answer("💬 Введіть коментар:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(CommentStates.entering_comment, F.text == BTN_CANCEL)
async def cancel_comment(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    role = user.get("role", "member") if user else "member"
    await state.clear()
    await message.answer("❌ Коментар скасовано.", reply_markup=main_menu_keyboard(role))


@router.message(CommentStates.entering_comment)
async def save_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("comment_task_id")
    user = await db.get_user(message.from_user.id)
    role = user.get("role", "member") if user else "member"

    await db.add_task_comment(task_id, message.from_user.id, (message.text or "").strip())
    await state.clear()
    await message.answer("✅ Коментар додано!", reply_markup=main_menu_keyboard(role))
