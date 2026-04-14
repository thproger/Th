import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "task_manager_bot")

# Canonical role keys
ROLES = {
    "admin": 4,
    "manager": 3,
    "group_leader": 2,
    "member": 1,
}

# Display labels (also include legacy aliases for backward compatibility in UI)
ROLE_LABELS = {
    "admin": "👑 Адмін",
    "manager": "🏢 Керівник",
    "group_leader": "👥 Керівник групи",
    "member": "👤 Рядовий",
    "керівник": "🏢 Керівник",
    "керівник групи": "👥 Керівник групи",
    "рядовий": "👤 Рядовий",
    "РєРµСЂС–РІРЅРёРє": "🏢 Керівник",
    "РєРµСЂС–РІРЅРёРє РіСЂСѓРїРё": "👥 Керівник групи",
    "СЂСЏРґРѕРІРёР№": "👤 Рядовий",
}

TASK_STATUSES = {
    "pending": "⏳ Очікує",
    "in_progress": "🔄 В роботі",
    "done": "✅ Виконано",
    "cancelled": "❌ Скасовано",
}
