from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import ROLE_LABELS
from permissions import has_role, role_level, ROLE_ADMIN, ROLE_GROUP_LEADER, ROLE_MEMBER
from keyboards import users_list_keyboard, group_member_keyboard, BTN_MY_GROUP, BTN_ALL_GROUPS

router = Router()


class GroupStates(StatesGroup):
    adding_member = State()
    removing_member = State()
    admin_creating_group_name = State()
    admin_renaming_group = State()


@router.message(F.text == BTN_MY_GROUP)
async def my_group(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await message.answer("❌ Немає доступу.")
        return

    group = await db.get_group_by_leader(message.from_user.id)
    members = await db.get_group_members(message.from_user.id)

    if not members:
        member_text = "  (порожньо)"
    else:
        lines = []
        for m in members:
            name = m.get("full_name") or m.get("username") or str(m["telegram_id"])
            lines.append(f"  • {name} | {ROLE_LABELS.get(m.get('role'), 'Без ролі')}")
        member_text = "\n".join(lines)

    group_name = group.get("name", "Моя група") if group else "Моя група"
    await message.answer(f"👥 <b>{group_name}</b>\nУчасників: {len(members)}\n\n{member_text}", parse_mode="HTML")

    buttons = [[InlineKeyboardButton(text="➕ Додати учасника", callback_data="group_add_member")]]
    if members:
        buttons.append([InlineKeyboardButton(text="➖ Видалити учасника", callback_data="group_remove_member")])

    await message.answer("Управління групою:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "group_add_member")
async def start_add_member(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    all_users = await db.get_all_users()
    group = await db.get_group_by_leader(callback.from_user.id)
    current_members = group.get("members", []) if group else []

    available = [
        u for u in all_users
        if u["telegram_id"] != callback.from_user.id
        and role_level(u.get("role")) == role_level(ROLE_MEMBER)
        and u["telegram_id"] not in current_members
    ]

    if not available:
        await callback.answer("❌ Немає доступних рядових для додавання.", show_alert=True)
        return

    await state.set_state(GroupStates.adding_member)
    await callback.message.answer(
        "👤 Оберіть користувача:",
        reply_markup=users_list_keyboard(available, "add_to_group"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add_to_group:"), GroupStates.adding_member)
async def add_member_confirmed(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    member_id = int(callback.data.split(":")[1])
    member = await db.get_user(member_id)
    if not member:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    group = await db.get_group_by_leader(callback.from_user.id)
    if not group:
        leader = await db.get_user(callback.from_user.id)
        await db.create_group(callback.from_user.id, f"Група {leader.get('full_name', '')}")

    await db.add_member_to_group(callback.from_user.id, member_id)
    await state.clear()

    name = member.get("full_name") or member.get("username") or str(member_id)
    await callback.message.edit_text(f"✅ <b>{name}</b> додано до групи!", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "group_remove_member")
async def start_remove_member(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    members = await db.get_group_members(callback.from_user.id)
    if not members:
        await callback.answer("Група порожня.", show_alert=True)
        return

    await state.set_state(GroupStates.removing_member)
    await callback.message.answer("👤 Оберіть учасника:", reply_markup=group_member_keyboard(members, "remove_from_group"))
    await callback.answer()


@router.callback_query(F.data.startswith("remove_from_group:"), GroupStates.removing_member)
async def remove_member_confirmed(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_GROUP_LEADER):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return

    member_id = int(callback.data.split(":")[1])
    await db.remove_member_from_group(callback.from_user.id, member_id)
    await state.clear()
    await callback.message.edit_text("✅ Учасника видалено з групи.")
    await callback.answer()


@router.message(F.text == BTN_ALL_GROUPS)
async def all_groups(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return

    groups = await db.get_all_groups()
    if not groups:
        await message.answer("📭 Груп ще немає.")
        return

    lines = [f"📁 <b>Всі групи ({len(groups)}):</b>\n"]
    buttons = [[InlineKeyboardButton(text="➕ Створити групу", callback_data="admin_group_create")]]
    for g in groups:
        leader = await db.get_user(g["leader_id"])
        leader_name = leader.get("full_name") if leader else f"ID:{g['leader_id']}"
        members_count = len(g.get("members", []))
        lines.append(f"• <b>{g.get('name', '?')}</b>\n  Керівник: {leader_name} | Учасників: {members_count}")
        buttons.append([
            InlineKeyboardButton(
                text=f"⚙️ {g.get('name', '?')[:35]}",
                callback_data=f"admin_group_manage:{str(g['_id'])}",
            )
        ])

    await message.answer("\n".join(lines), parse_mode="HTML")
    await message.answer(
        "Оберіть дію:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons[:90]),
    )


@router.callback_query(F.data == "admin_group_create")
async def admin_group_create_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    await state.clear()
    await state.set_state(GroupStates.admin_creating_group_name)
    await callback.message.answer("Введіть назву нової групи:")
    await callback.answer()


@router.message(GroupStates.admin_creating_group_name)
async def admin_group_create_save(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return
    group_name = (message.text or "").strip()
    if len(group_name) < 2:
        await message.answer("Назва занадто коротка, спробуйте ще раз.")
        return
    existing = await db.get_group_by_name(group_name)
    if existing:
        await message.answer("Група з такою назвою вже існує.")
        return
    all_users = await db.get_all_users()
    if not all_users:
        await message.answer("Немає користувачів для призначення керівника.")
        return
    await state.update_data(new_group_name=group_name)
    await state.set_state(GroupStates.adding_member)
    await message.answer(
        f"Оберіть керівника для групи <b>{group_name}</b>:",
        parse_mode="HTML",
        reply_markup=users_list_keyboard(all_users, "admin_group_pick_leader"),
    )


@router.callback_query(F.data.startswith("admin_group_pick_leader:"), GroupStates.adding_member)
async def admin_group_pick_leader(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    leader_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    group_name = data.get("new_group_name")
    if not group_name:
        await callback.answer("Помилка стану.", show_alert=True)
        return
    await db.update_user_role(leader_id, ROLE_GROUP_LEADER)
    await db.create_group(leader_id, group_name)
    await state.clear()
    await callback.message.edit_text(f"✅ Групу <b>{group_name}</b> створено.", parse_mode="HTML")
    await callback.answer()


def _admin_group_actions_keyboard(group_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Призначити керівника", callback_data=f"admin_group_set_leader:{group_id}")],
        [InlineKeyboardButton(text="✏️ Перейменувати", callback_data=f"admin_group_rename:{group_id}")],
        [InlineKeyboardButton(text="➕ Додати учасника", callback_data=f"admin_group_add_member:{group_id}")],
        [InlineKeyboardButton(text="➖ Видалити учасника", callback_data=f"admin_group_remove_member:{group_id}")],
        [InlineKeyboardButton(text="🗑 Видалити групу", callback_data=f"admin_group_delete:{group_id}")],
    ])


@router.callback_query(F.data.startswith("admin_group_manage:"))
async def admin_group_manage(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not has_role(user.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    group = await db.get_group_by_id(group_id)
    if not group:
        await callback.answer("Групу не знайдено.", show_alert=True)
        return
    leader = await db.get_user(group["leader_id"])
    leader_name = leader.get("full_name") if leader else f"ID:{group['leader_id']}"
    members = await db.get_group_members_by_group_id(group_id)
    members_text = ", ".join([(m.get("full_name") or str(m["telegram_id"])) for m in members[:8]])
    if len(members) > 8:
        members_text += "..."
    if not members_text:
        members_text = "немає"
    await state.clear()
    await state.update_data(admin_group_id=group_id)
    await callback.message.edit_text(
        f"⚙️ <b>{group.get('name', '?')}</b>\n"
        f"Керівник: {leader_name}\n"
        f"Учасників: {len(members)}\n"
        f"Склад: {members_text}",
        parse_mode="HTML",
        reply_markup=_admin_group_actions_keyboard(group_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_set_leader:"))
async def admin_group_set_leader_start(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    all_users = await db.get_all_users()
    if not all_users:
        await callback.answer("Немає користувачів.", show_alert=True)
        return
    await state.update_data(admin_group_id=group_id)
    await callback.message.answer(
        "Оберіть нового керівника:",
        reply_markup=users_list_keyboard(all_users, "admin_group_set_leader_pick"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_set_leader_pick:"))
async def admin_group_set_leader_pick(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    new_leader_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    group_id = data.get("admin_group_id")
    if not group_id:
        await callback.answer("Помилка стану.", show_alert=True)
        return
    await db.update_user_role(new_leader_id, ROLE_GROUP_LEADER)
    await db.set_group_leader(group_id, new_leader_id)
    leader = await db.get_user(new_leader_id)
    leader_name = (leader or {}).get("full_name") or str(new_leader_id)
    await callback.message.edit_text(f"✅ Керівника групи змінено на <b>{leader_name}</b>.", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_rename:"))
async def admin_group_rename_start(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    await state.update_data(admin_group_id=group_id)
    await state.set_state(GroupStates.admin_renaming_group)
    await callback.message.answer("Введіть нову назву групи:")
    await callback.answer()


@router.message(GroupStates.admin_renaming_group)
async def admin_group_rename_save(message: Message, state: FSMContext):
    admin = await db.get_user(message.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await message.answer("❌ Немає доступу.")
        return
    data = await state.get_data()
    group_id = data.get("admin_group_id")
    if not group_id:
        await message.answer("Помилка стану.")
        return
    new_name = (message.text or "").strip()
    if len(new_name) < 2:
        await message.answer("Назва занадто коротка.")
        return
    await db.rename_group(group_id, new_name)
    await state.clear()
    await message.answer(f"✅ Назву групи змінено на <b>{new_name}</b>.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_group_add_member:"))
async def admin_group_add_member_start(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    group = await db.get_group_by_id(group_id)
    if not group:
        await callback.answer("Групу не знайдено.", show_alert=True)
        return
    all_users = await db.get_all_users()
    current_members = set(group.get("members", []))
    available = [
        u for u in all_users
        if u["telegram_id"] != group["leader_id"] and u["telegram_id"] not in current_members
    ]
    if not available:
        await callback.answer("Немає користувачів для додавання.", show_alert=True)
        return
    await state.update_data(admin_group_id=group_id)
    await callback.message.answer(
        "Оберіть користувача для додавання:",
        reply_markup=users_list_keyboard(available, "admin_group_add_member_pick"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_add_member_pick:"))
async def admin_group_add_member_pick(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    member_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    group_id = data.get("admin_group_id")
    if not group_id:
        await callback.answer("Помилка стану.", show_alert=True)
        return
    await db.add_member_to_group_by_id(group_id, member_id)
    member = await db.get_user(member_id)
    name = (member or {}).get("full_name") or str(member_id)
    await callback.message.edit_text(f"✅ <b>{name}</b> додано до групи.", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_remove_member:"))
async def admin_group_remove_member_start(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    members = await db.get_group_members_by_group_id(group_id)
    if not members:
        await callback.answer("У групі немає учасників.", show_alert=True)
        return
    await state.update_data(admin_group_id=group_id)
    await callback.message.answer(
        "Оберіть учасника для видалення:",
        reply_markup=group_member_keyboard(members, "admin_group_remove_member_pick"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_remove_member_pick:"))
async def admin_group_remove_member_pick(callback: CallbackQuery, state: FSMContext):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    member_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    group_id = data.get("admin_group_id")
    if not group_id:
        await callback.answer("Помилка стану.", show_alert=True)
        return
    await db.remove_member_from_group_by_id(group_id, member_id)
    await callback.message.edit_text("✅ Учасника видалено з групи.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_group_delete:"))
async def admin_group_delete(callback: CallbackQuery):
    admin = await db.get_user(callback.from_user.id)
    if not admin or not has_role(admin.get("role"), ROLE_ADMIN):
        await callback.answer("❌ Немає доступу.", show_alert=True)
        return
    group_id = callback.data.split(":")[1]
    group = await db.get_group_by_id(group_id)
    if not group:
        await callback.answer("Групу не знайдено.", show_alert=True)
        return
    await db.delete_group(group_id)
    await callback.message.edit_text(f"✅ Групу <b>{group.get('name', '?')}</b> видалено.", parse_mode="HTML")
    await callback.answer()
