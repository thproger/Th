from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from config import ROLE_LABELS, ROLES
from permissions import has_role, ROLE_ADMIN, ROLE_MANAGER, ROLE_GROUP_LEADER


BTN_MY_TASKS = "📋 Мої завдання"
BTN_MANAGE_USERS = "👥 Управління користувачами"
BTN_ALL_TASKS = "📊 Всі завдання"
BTN_ALL_GROUPS = "📁 Всі групи"
BTN_CREATE_TASK = "➕ Створити завдання"
BTN_TASKS_ISSUED = "📊 Завдання що я видав"
BTN_MY_GROUP = "👥 Моя група"
BTN_GROUP_TASKS = "📊 Завдання моєї групи"
BTN_CANCEL = "❌ Скасувати"
BTN_JOIN_TEAM = "🤝 Приєднатися до команди"
BTN_RECRUITING_ADMIN = "🛠 Заявки та аналітика"


def main_menu_keyboard(role: str) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=BTN_MY_TASKS)]]
    button_texts = {BTN_MY_TASKS}

    def add_button(text: str):
        if text in button_texts:
            return
        button_texts.add(text)
        buttons.append([KeyboardButton(text=text)])

    if has_role(role, ROLE_ADMIN):
        add_button(BTN_MANAGE_USERS)
        add_button(BTN_ALL_TASKS)
        add_button(BTN_ALL_GROUPS)
        add_button(BTN_RECRUITING_ADMIN)

    if has_role(role, ROLE_MANAGER):
        add_button(BTN_CREATE_TASK)
        add_button(BTN_TASKS_ISSUED)

    if has_role(role, ROLE_GROUP_LEADER):
        add_button(BTN_CREATE_TASK)
        add_button(BTN_MY_GROUP)
        add_button(BTN_GROUP_TASKS)

    add_button(BTN_JOIN_TEAM)

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def roles_keyboard(exclude_admin=False) -> InlineKeyboardMarkup:
    buttons = []
    for role_key in ROLES.keys():
        if exclude_admin and role_key == "admin":
            continue
        label = ROLE_LABELS.get(role_key, role_key)
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"set_role:{role_key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def users_list_keyboard(users: list, action: str) -> InlineKeyboardMarkup:
    buttons = []
    for user in users:
        name = user.get("full_name") or user.get("username") or str(user["telegram_id"])
        role = user.get("role")
        role_label = ROLE_LABELS.get(role, "Без ролі") if role else "Без ролі"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{name} | {role_label}",
                    callback_data=f"{action}:{user['telegram_id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def task_actions_keyboard(task_id: str, user_role: str, is_assignee: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_assignee:
        buttons.append(
            [
                InlineKeyboardButton(text="🔄 В роботі", callback_data=f"task_status:{task_id}:in_progress"),
                InlineKeyboardButton(text="✅ Виконано", callback_data=f"task_status:{task_id}:done"),
            ]
        )
    if has_role(user_role, ROLE_GROUP_LEADER):
        buttons.append(
            [
                InlineKeyboardButton(text="❌ Скасувати", callback_data=f"task_status:{task_id}:cancelled"),
                InlineKeyboardButton(text="🗑 Видалити", callback_data=f"task_delete:{task_id}"),
            ]
        )
    buttons.append([InlineKeyboardButton(text="💬 Коментар", callback_data=f"task_comment:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tasks_list_keyboard(tasks: list, prefix: str = "view_task") -> InlineKeyboardMarkup:
    buttons = []
    statuses = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}
    for task in tasks:
        icon = statuses.get(task.get("status", "pending"), "⏳")
        title = task.get("title", "Без назви")[:30]
        task_id = str(task["_id"])
        buttons.append([InlineKeyboardButton(text=f"{icon} {title}", callback_data=f"{prefix}:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def task_filter_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="⏳ Очікують", callback_data="filter_tasks:pending"),
            InlineKeyboardButton(text="🔄 В роботі", callback_data="filter_tasks:in_progress"),
        ],
        [
            InlineKeyboardButton(text="✅ Виконані", callback_data="filter_tasks:done"),
            InlineKeyboardButton(text="❌ Скасовані", callback_data="filter_tasks:cancelled"),
        ],
        [InlineKeyboardButton(text="📋 Всі", callback_data="filter_tasks:all")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def group_member_keyboard(members: list, action: str) -> InlineKeyboardMarkup:
    buttons = []
    for user in members:
        name = user.get("full_name") or user.get("username") or str(user["telegram_id"])
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"{action}:{user['telegram_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard(action: str, obj_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так", callback_data=f"confirm_{action}:{obj_id}"),
                InlineKeyboardButton(text="❌ Ні", callback_data="cancel_action"),
            ]
        ]
    )
