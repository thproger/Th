from database import db
from config import ROLE_LABELS, TASK_STATUSES


def format_user(user: dict) -> str:
    name = user.get("full_name") or user.get("username") or str(user["telegram_id"])
    role = user.get("role")
    role_label = ROLE_LABELS.get(role, "❓ Без ролі") if role else "❓ Без ролі"
    tg = f"@{user['username']}" if user.get("username") else f"ID: {user['telegram_id']}"
    return f"<b>{name}</b> ({tg})\nРоль: {role_label}"


async def format_task(task: dict, show_assignee=True, show_creator=True) -> str:
    status_icon = {
        "pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"
    }.get(task.get("status", "pending"), "⏳")
    status_label = TASK_STATUSES.get(task.get("status", "pending"), "")

    lines = [
        f"{status_icon} <b>{task.get('title', 'Без назви')}</b>",
        f"Статус: {status_label}",
    ]

    if task.get("description"):
        lines.append(f"📝 {task['description']}")

    if task.get("deadline"):
        lines.append(f"📅 Дедлайн: {task['deadline']}")

    if show_assignee:
        assignee = await db.get_user(task["assignee_id"])
        if assignee:
            name = assignee.get("full_name") or assignee.get("username") or str(assignee["telegram_id"])
            lines.append(f"👤 Виконавець: {name}")

    if show_creator:
        creator = await db.get_user(task["creator_id"])
        if creator:
            name = creator.get("full_name") or creator.get("username") or str(creator["telegram_id"])
            lines.append(f"📌 Від: {name}")

    created = task.get("created_at")
    if created:
        lines.append(f"🕐 Створено: {created.strftime('%d.%m.%Y %H:%M')}")

    comments = task.get("comments", [])
    if comments:
        lines.append(f"\n💬 Коментарів: {len(comments)}")
        last = comments[-1]
        author = await db.get_user(last["author_id"])
        aname = author.get("full_name") if author else "?"
        lines.append(f"  └ {aname}: {last['text'][:60]}")

    task_id = str(task["_id"])
    lines.append(f"\n🆔 ID: <code>{task_id}</code>")
    return "\n".join(lines)


def build_stats(tasks: list) -> str:
    total = len(tasks)
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
    done = sum(1 for t in tasks if t.get("status") == "done")
    cancelled = sum(1 for t in tasks if t.get("status") == "cancelled")
    return (
        f"📊 <b>Статистика завдань:</b>\n"
        f"Всього: {total}\n"
        f"⏳ Очікують: {pending}\n"
        f"🔄 В роботі: {in_progress}\n"
        f"✅ Виконано: {done}\n"
        f"❌ Скасовано: {cancelled}"
    )
