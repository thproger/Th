from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
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

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    for g in groups:
        leader = await db.get_user(g["leader_id"])
        leader_name = leader.get("full_name") if leader else f"ID:{g['leader_id']}"
        members_count = len(g.get("members", []))
        lines.append(f"• <b>{g.get('name', '?')}</b>\n  Керівник: {leader_name} | Учасників: {members_count}")

    await message.answer("\n".join(lines), parse_mode="HTML")
