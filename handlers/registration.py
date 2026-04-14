from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import ROLE_LABELS
from permissions import has_role, role_level, ROLE_ADMIN, ROLE_GROUP_LEADER
from keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    roles_keyboard,
    users_list_keyboard,
    BTN_MANAGE_USERS,
    BTN_CANCEL,
    BTN_JOIN_TEAM,
    BTN_RECRUITING_ADMIN,
)
from utils import format_user

router = Router()


class RegisterStates(StatesGroup):
    waiting_name = State()


class RecruitFlowStates(StatesGroup):
    choosing_flow = State()
    sadist_group = State()
    sadist_position = State()
    choosing_category = State()
    choosing_next_node = State()


class RecruitAdminStates(StatesGroup):
    waiting_parent_for_group = State()
    waiting_parent_for_position = State()
    waiting_name = State()

WELCOME_NEW = """👋 <b>Вітаю!</b>

Щоб почати, введи своє ім'я або псевдо."""

WELCOME_NO_ROLE = """👋 Ти вже зареєстрований.

Оберіть, будь ласка, формат подачі заявки."""

WELCOME_BACK = """👋 З поверненням, <b>{name}</b>!
Роль: {role}

<b>Команди:</b>
/me — переглянути профіль"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if user:
        role = user.get("role")
        if not role:
            await message.answer(WELCOME_NO_ROLE, parse_mode="HTML")
            await send_recruit_flow_prompt(message, state)
            return

        await message.answer(
            WELCOME_BACK.format(name=user["full_name"], role=ROLE_LABELS.get(role, role)),
            reply_markup=main_menu_keyboard(role),
            parse_mode="HTML",
        )
        return

    await message.answer(WELCOME_NEW, parse_mode="HTML")
    await message.answer("✏️ Введи своє ім'я або псевдо:", reply_markup=cancel_keyboard())
    await state.set_state(RegisterStates.waiting_name)


@router.message(RegisterStates.waiting_name, F.text == BTN_CANCEL)
async def cancel_register(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Реєстрацію скасовано.")


@router.message(RegisterStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 2:
        await message.answer("Ім'я занадто коротке. Спробуй ще раз:")
        return

    await db.create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
    )
    await message.answer(f"✅ Реєстрацію завершено!\nІм'я: <b>{full_name}</b>", parse_mode="HTML")
    await send_recruit_flow_prompt(message, state)


async def send_recruit_flow_prompt(message: Message, state: FSMContext):
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌿 САДист", callback_data="recruit_flow:sadist")],
        [InlineKeyboardButton(text="🤝 Приєднатися до команди", callback_data="recruit_flow:team")],
    ])
    await state.set_state(RecruitFlowStates.choosing_flow)
    await message.answer("Оберіть варіант:", reply_markup=buttons)


@router.message(Command("me"))
async def cmd_me(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Ти ще не зареєстрований. Введи /start")
        return
    await message.answer(format_user(user), parse_mode="HTML")


@router.message(F.text == BTN_MANAGE_USERS)
async def admin_manage_users(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return

    users = await db.get_all_users()
    if not users:
        await message.answer("Користувачів ще немає.")
        return

    await message.answer(
        f"👥 Всього користувачів: {len(users)}\nОберіть користувача для призначення ролі:",
        reply_markup=users_list_keyboard(users, "admin_set_role"),
    )


@router.callback_query(F.data.startswith("admin_set_role:"))
async def admin_select_role(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    target = await db.get_user(target_id)
    if not target:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    await state.update_data(target_id=target_id)
    name = target.get("full_name") or target.get("username") or str(target_id)
    await callback.message.edit_text(
        f"Оберіть роль для <b>{name}</b>:",
        reply_markup=roles_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("set_role:"))
async def set_role_handler(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await callback.answer("Помилка стану.", show_alert=True)
        return

    role = callback.data.split(":")[1]
    await db.update_user_role(target_id, role)

    if role_level(role) == role_level(ROLE_GROUP_LEADER):
        existing = await db.get_group_by_leader(target_id)
        if not existing:
            target = await db.get_user(target_id)
            gname = f"Група {target.get('full_name', target_id)}"
            await db.create_group(target_id, gname)

    await state.clear()
    role_label = ROLE_LABELS.get(role, role)
    await callback.message.edit_text(f"✅ Роль <b>{role_label}</b> призначено!", parse_mode="HTML")

    try:
        await callback.bot.send_message(
            target_id,
            f"🎉 Тобі призначено роль: <b>{role_label}</b>\nНатисни /start для оновлення меню.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(F.text == BTN_JOIN_TEAM)
async def join_team_start(message: Message, state: FSMContext):
    await state.clear()
    await send_recruit_flow_prompt(message, state)


@router.callback_query(F.data.startswith("recruit_flow:"), RecruitFlowStates.choosing_flow)
async def recruit_choose_flow(callback: CallbackQuery, state: FSMContext):
    flow = callback.data.split(":")[1]
    if flow == "sadist":
        await state.update_data(flow="sadist")
        await state.set_state(RecruitFlowStates.sadist_group)
        await callback.message.edit_text("Вкажіть вашу групу (текстом):")
        await callback.message.answer("Для скасування натисніть кнопку нижче.", reply_markup=cancel_keyboard())
        await callback.answer()
        return

    roots = await db.get_recruitment_children(parent_id=None)
    if not roots:
        await callback.answer("Категорії ще не налаштовані.", show_alert=True)
        return
    await state.update_data(flow="team")
    await state.set_state(RecruitFlowStates.choosing_category)
    await callback.message.edit_text(
        "Оберіть категорію:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=node["name"], callback_data=f"recruit_node:{str(node['_id'])}")]
            for node in roots
        ]),
    )
    await callback.answer()


@router.message(RecruitFlowStates.sadist_group, F.text == BTN_CANCEL)
@router.message(RecruitFlowStates.sadist_position, F.text == BTN_CANCEL)
@router.message(RecruitFlowStates.choosing_next_node, F.text == BTN_CANCEL)
async def cancel_recruit_flow(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    role = (user or {}).get("role", "member")
    await state.clear()
    await message.answer("❌ Подачу заявки скасовано.", reply_markup=main_menu_keyboard(role))


@router.message(RecruitFlowStates.sadist_group)
async def recruit_sadist_group(message: Message, state: FSMContext):
    group_name = (message.text or "").strip()
    if len(group_name) < 2:
        await message.answer("Група занадто коротка, спробуйте ще раз.")
        return
    await state.update_data(sadist_group=group_name)
    await state.set_state(RecruitFlowStates.sadist_position)
    await message.answer("Вкажіть вашу посаду (текстом):")


@router.message(RecruitFlowStates.sadist_position)
async def recruit_sadist_position(message: Message, state: FSMContext):
    position_name = (message.text or "").strip()
    if len(position_name) < 2:
        await message.answer("Посада занадто коротка, спробуйте ще раз.")
        return
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    role = (user or {}).get("role", "member")
    full_name = (user or {}).get("full_name") or message.from_user.full_name or str(message.from_user.id)
    username = (user or {}).get("username") or message.from_user.username
    tg_ref = f"@{username}" if username else f"ID: {message.from_user.id}"

    await db.create_application(
        applicant_id=message.from_user.id,
        username=username,
        full_name=full_name,
        application_type="sadist",
        selections=[data.get("sadist_group"), position_name],
        extra={"group": data.get("sadist_group"), "position": position_name},
    )

    notify_text = (
        "📥 <b>Нова заявка: САДист</b>\n\n"
        f"👤 Ім'я: <b>{full_name}</b>\n"
        f"🔗 Telegram: {tg_ref}\n"
        f"👥 Група: <b>{data.get('sadist_group')}</b>\n"
        f"💼 Посада: <b>{position_name}</b>"
    )
    await send_application_to_reviewers(message, notify_text)
    await state.clear()
    await message.answer(
        "Вітаю тепер ви також катуватимете людей!\nА тепер йдіть працювати.",
        reply_markup=main_menu_keyboard(role),
    )


@router.callback_query(F.data.startswith("recruit_node:"), RecruitFlowStates.choosing_category)
@router.callback_query(F.data.startswith("recruit_node:"), RecruitFlowStates.choosing_next_node)
async def recruit_pick_node(callback: CallbackQuery, state: FSMContext):
    node_id = callback.data.split(":")[1]
    node = await db.get_recruitment_node(node_id)
    if not node:
        await callback.answer("Позицію не знайдено.", show_alert=True)
        return

    children = await db.get_recruitment_children(parent_id=node_id)
    data = await state.get_data()
    selected_path = data.get("selected_path", [])
    selected_path.append({"id": node_id, "name": node["name"], "kind": node.get("kind")})
    await state.update_data(selected_path=selected_path)

    if children:
        await state.set_state(RecruitFlowStates.choosing_next_node)
        await callback.message.edit_text(
            f"Обрано: <b>{node['name']}</b>\nОберіть наступний пункт:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=child["name"], callback_data=f"recruit_node:{str(child['_id'])}")]
                for child in children
            ]),
        )
        await callback.answer()
        return

    user = await db.get_user(callback.from_user.id)
    role = (user or {}).get("role", "member")
    full_name = (user or {}).get("full_name") or callback.from_user.full_name or str(callback.from_user.id)
    username = (user or {}).get("username") or callback.from_user.username
    tg_ref = f"@{username}" if username else f"ID: {callback.from_user.id}"
    selection_names = [item["name"] for item in selected_path]
    await db.create_application(
        applicant_id=callback.from_user.id,
        username=username,
        full_name=full_name,
        application_type="team",
        selections=selection_names,
        extra={"path": selection_names},
    )
    notify_text = (
        "📥 <b>Нова заявка: приєднання до команди</b>\n\n"
        f"👤 Ім'я: <b>{full_name}</b>\n"
        f"🔗 Telegram: {tg_ref}\n"
        f"🧭 Шлях: <b>{' → '.join(selection_names)}</b>"
    )
    await send_application_to_reviewers(callback.message, notify_text)
    await state.clear()
    await callback.message.edit_text(
        "Чекайте поки вам напише Зеленка, та готуйтесь до пробного завдання."
    )
    await callback.message.answer("Повертаю меню.", reply_markup=main_menu_keyboard(role))
    await callback.answer()


async def send_application_to_reviewers(message: Message, notify_text: str):
    admins = await db.get_users_by_role("admin")
    for admin in admins:
        try:
            await message.bot.send_message(admin["telegram_id"], notify_text, parse_mode="HTML")
        except Exception:
            pass
    try:
        await message.bot.send_message("@helenyxs", notify_text, parse_mode="HTML")
    except Exception:
        pass


@router.message(F.text == BTN_RECRUITING_ADMIN)
async def recruit_admin_menu(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Загальна аналітика", callback_data="recruit_admin:analytics")],
        [InlineKeyboardButton(text="📄 Останні заявки", callback_data="recruit_admin:list")],
        [InlineKeyboardButton(text="➕ Додати категорію", callback_data="recruit_admin:add_category")],
        [InlineKeyboardButton(text="➕ Додати групу", callback_data="recruit_admin:add_group")],
        [InlineKeyboardButton(text="➕ Додати посаду", callback_data="recruit_admin:add_position")],
    ])
    await message.answer("Адмін-розділ заявок:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("recruit_admin:"))
async def recruit_admin_action(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    action = callback.data.split(":")[1]
    await state.clear()

    if action == "analytics":
        analytics = await db.get_application_analytics()
        lines = [
            f"📊 <b>Аналітика заявок</b>",
            f"Всього заявок: <b>{analytics['total']}</b>",
            f"Унікальних людей: <b>{analytics['unique_applicants']}</b>",
            "",
            "По типах:",
        ]
        if analytics["by_type"]:
            lines.extend([f"• {item['_id']}: {item['count']}" for item in analytics["by_type"]])
        else:
            lines.append("• Даних ще немає")
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
        await callback.answer()
        return

    if action == "list":
        applications = await db.get_recent_applications(limit=30)
        if not applications:
            await callback.message.edit_text("Заявок ще немає.")
            await callback.answer()
            return
        lines = [f"📄 <b>Останні заявки ({len(applications)})</b>\n"]
        for app in applications:
            username = app.get("username")
            tg_ref = f"@{username}" if username else f"ID:{app['applicant_id']}"
            path = " → ".join(app.get("selections", []))
            lines.append(f"• {app.get('full_name')} | {tg_ref}\n  Тип: {app.get('application_type')} | {path}")
        await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
        await callback.answer()
        return

    if action == "add_category":
        await state.update_data(add_kind="category", parent_id=None)
        await state.set_state(RecruitAdminStates.waiting_name)
        await callback.message.edit_text("Введіть назву нової категорії:")
        await callback.message.answer("Для скасування натисніть кнопку нижче.", reply_markup=cancel_keyboard())
        await callback.answer()
        return

    if action == "add_group":
        categories = await db.get_recruitment_nodes_by_kind("category")
        if not categories:
            await callback.answer("Спочатку створіть категорію.", show_alert=True)
            return
        await state.update_data(add_kind="group")
        await state.set_state(RecruitAdminStates.waiting_parent_for_group)
        await callback.message.edit_text(
            "Оберіть батьківський елемент для групи:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=node["name"], callback_data=f"recruit_parent:{str(node['_id'])}")]
                for node in categories
            ]),
        )
        await callback.answer()
        return

    if action == "add_position":
        groups = await db.get_recruitment_nodes_by_kind("group")
        if not groups:
            await callback.answer("Спочатку створіть групу.", show_alert=True)
            return
        await state.update_data(add_kind="position")
        await state.set_state(RecruitAdminStates.waiting_parent_for_position)
        await callback.message.edit_text(
            "Оберіть батьківську групу для посади:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=node["name"], callback_data=f"recruit_parent:{str(node['_id'])}")]
                for node in groups[:70]
            ]),
        )
        await callback.answer()
        return

    await callback.answer()


@router.callback_query(F.data.startswith("recruit_parent:"), RecruitAdminStates.waiting_parent_for_group)
@router.callback_query(F.data.startswith("recruit_parent:"), RecruitAdminStates.waiting_parent_for_position)
async def recruit_admin_choose_parent(callback: CallbackQuery, state: FSMContext):
    parent_id = callback.data.split(":")[1]
    await state.update_data(parent_id=parent_id)
    await state.set_state(RecruitAdminStates.waiting_name)
    await callback.message.edit_text("Введіть назву нового елемента:")
    await callback.message.answer("Для скасування натисніть кнопку нижче.", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(RecruitAdminStates.waiting_name, F.text == BTN_CANCEL)
@router.message(RecruitAdminStates.waiting_parent_for_group, F.text == BTN_CANCEL)
@router.message(RecruitAdminStates.waiting_parent_for_position, F.text == BTN_CANCEL)
async def recruit_admin_cancel(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    role = (user or {}).get("role", "member")
    await state.clear()
    await message.answer("❌ Дію скасовано.", reply_markup=main_menu_keyboard(role))


@router.message(RecruitAdminStates.waiting_name)
async def recruit_admin_save_node(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return

    data = await state.get_data()
    add_kind = data.get("add_kind")
    parent_id = data.get("parent_id")
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Назва занадто коротка. Спробуйте ще раз.")
        return

    try:
        node = await db.create_recruitment_node(name=name, kind=add_kind, parent_id=parent_id)
    except Exception:
        await message.answer("Не вдалося створити елемент (можливо, вже існує з такою назвою).")
        return

    await state.clear()
    await message.answer(f"✅ Додано: <b>{node['name']}</b> ({add_kind})", parse_mode="HTML")
