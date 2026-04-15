from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from config import MONGO_URI, DB_NAME

DEFAULT_RECRUITMENT_TREE = [
    {
        "name": "🌸 Цвіт",
        "kind": "group",
        "children": [
            {"name": "Керівні посади", "kind": "group", "children": [
                {"name": "Менеджер виконання", "kind": "position"},
                {"name": "Менеджер постів", "kind": "position"},
                {"name": "Відповідальний за рекламу", "kind": "position"},
                {"name": "Відповідальний за Твітер", "kind": "position"},
                {"name": "Відповідальний за Тік-Ток", "kind": "position"},
                {"name": "Фандрейзер", "kind": "position"},
                {"name": "Заміна відповідальному за ЦВІТ", "kind": "position"},
                {"name": "Заміна куратору конкурсів", "kind": "position"},
                {"name": "Заміна куратору \"Вірш дня\"", "kind": "position"},
            ]},
            {"name": "Посади", "kind": "group", "children": [
                {"name": "Редактор", "kind": "position"},
                {"name": "Дизайнер", "kind": "position"},
                {"name": "Програміст", "kind": "position"},
                {"name": "Інформатор", "kind": "position"},
                {"name": "Декламатор", "kind": "position"},
                {"name": "Лектор", "kind": "position"},
                {"name": "Організатор онлайн-заходу", "kind": "position"},
                {"name": "Контакт-менеджер", "kind": "position"},
                {"name": "Відповідальний за рубрику", "kind": "group", "children": [
                    {"name": "\"Письменницькі поради\"", "kind": "position"},
                    {"name": "\"Цікавий факт\"", "kind": "position"},
                    {"name": "\"Спогади поряд\"", "kind": "position"},
                ]},
                {"name": "Команда \"Віршу дня\"", "kind": "group", "children": [
                    {"name": "Менеджер боту", "kind": "position"},
                    {"name": "Відповідальний за збір віршів", "kind": "position"},
                    {"name": "Відповідальний за голосовалку", "kind": "position"},
                    {"name": "Журі", "kind": "position"},
                ]},
                {"name": "Блогер", "kind": "group", "children": [
                    {"name": "Інстаграм", "kind": "position"},
                    {"name": "Тредс", "kind": "position"},
                    {"name": "Твітер", "kind": "position"},
                    {"name": "Тік-Ток", "kind": "position"},
                    {"name": "Ютуб", "kind": "position"},
                ]},
            ]},
        ],
    },
    {
        "name": "🎮 СадКрафт (GardenCraft)",
        "kind": "group",
        "children": [
            {"name": "Керівні посади", "kind": "group", "children": [
                {"name": "Відповідальний за GardenCraft", "kind": "position"},
                {"name": "Відповідальний за тех. складову", "kind": "position"},
                {"name": "Адмін Діскорда", "kind": "position"},
                {"name": "Адмін тгк", "kind": "position"},
                {"name": "Відповідальний за ігрову складову", "kind": "position"},
            ]},
            {"name": "Посади", "kind": "group", "children": [
                {"name": "Ідейник", "kind": "position"},
                {"name": "Менеджер постів", "kind": "position"},
                {"name": "Організатор івентів", "kind": "position"},
                {"name": "Програміст", "kind": "position"},
                {"name": "Блогер", "kind": "group", "children": [
                    {"name": "Інстаграм", "kind": "position"},
                    {"name": "Тредс", "kind": "position"},
                    {"name": "Ютуб", "kind": "position"},
                ]},
            ]},
        ],
    },
]


class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]

    async def close(self):
        if self.client:
            self.client.close()

    async def create_indexes(self):
        await self.db.users.create_index("telegram_id", unique=True)
        await self.db.tasks.create_index("assignee_id")
        await self.db.tasks.create_index("creator_id")
        await self.db.tasks.create_index("status")
        await self.db.recruitment_nodes.create_index([("parent_id", 1), ("name", 1)], unique=True)
        await self.db.applications.create_index("created_at")
        await self.db.applications.create_index("application_type")
        await self.db.applications.create_index("applicant_id")
        await self.ensure_default_recruitment_tree()

    # ───────────────── USERS ─────────────────

    async def get_user(self, telegram_id: int):
        return await self.db.users.find_one({"telegram_id": telegram_id})

    async def get_user_by_id(self, user_id: str):
        from bson import ObjectId
        return await self.db.users.find_one({"_id": ObjectId(user_id)})

    async def create_user(self, telegram_id: int, username: str, full_name: str):
        user = {
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "role": None,           # role assigned by admin
            "group_id": None,       # group the user belongs to
            "registered_at": datetime.utcnow(),
            "is_active": True,
        }
        result = await self.db.users.insert_one(user)
        user["_id"] = result.inserted_id
        return user

    async def update_user_role(self, telegram_id: int, role: str):
        await self.db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"role": role}}
        )

    async def get_all_users(self):
        cursor = self.db.users.find({"is_active": True})
        return await cursor.to_list(length=None)

    async def get_users_by_role(self, role: str):
        cursor = self.db.users.find({"role": role, "is_active": True})
        return await cursor.to_list(length=None)

    async def get_users_without_role(self):
        cursor = self.db.users.find({"role": None, "is_active": True})
        return await cursor.to_list(length=None)

    # ───────────────── GROUPS ─────────────────

    async def create_group(self, leader_id: int, name: str):
        group = {
            "leader_id": leader_id,
            "name": name,
            "members": [],
            "created_at": datetime.utcnow(),
        }
        result = await self.db.groups.insert_one(group)
        group["_id"] = result.inserted_id
        return group

    async def get_group_by_leader(self, leader_id: int):
        return await self.db.groups.find_one({"leader_id": leader_id})

    async def get_groups_by_leader(self, leader_id: int):
        cursor = self.db.groups.find({"leader_id": leader_id}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_group_by_id(self, group_id):
        from bson import ObjectId
        return await self.db.groups.find_one({"_id": ObjectId(str(group_id))})

    async def add_member_to_group(self, leader_id: int, member_telegram_id: int):
        await self.db.groups.update_one(
            {"leader_id": leader_id},
            {"$addToSet": {"members": member_telegram_id}}
        )

    async def remove_member_from_group(self, leader_id: int, member_telegram_id: int):
        await self.db.groups.update_one(
            {"leader_id": leader_id},
            {"$pull": {"members": member_telegram_id}}
        )

    async def get_group_members(self, leader_id: int):
        groups = await self.get_groups_by_leader(leader_id)
        if not groups:
            return []
        member_ids = set()
        for group in groups:
            member_ids.update(group.get("members", []))
        if not member_ids:
            return []
        cursor = self.db.users.find({"telegram_id": {"$in": list(member_ids)}})
        return await cursor.to_list(length=None)

    async def get_all_groups(self):
        cursor = self.db.groups.find()
        return await cursor.to_list(length=None)

    async def create_group_with_members(self, leader_id: int, name: str, members: list[int] | None = None):
        group = {
            "leader_id": leader_id,
            "name": name,
            "members": members or [],
            "created_at": datetime.utcnow(),
        }
        result = await self.db.groups.insert_one(group)
        group["_id"] = result.inserted_id
        return group

    async def get_group_by_name(self, name: str):
        return await self.db.groups.find_one({"name": name})

    async def get_groups_with_member(self, member_telegram_id: int):
        cursor = self.db.groups.find({"members": member_telegram_id}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_user_groups(self, telegram_id: int):
        leader_groups = await self.get_groups_by_leader(telegram_id)
        member_groups = await self.get_groups_with_member(telegram_id)
        merged = {}
        for group in leader_groups + member_groups:
            merged[str(group["_id"])] = group
        return list(merged.values())

    async def rename_group(self, group_id: str, new_name: str):
        from bson import ObjectId
        await self.db.groups.update_one(
            {"_id": ObjectId(str(group_id))},
            {"$set": {"name": new_name}},
        )

    async def set_group_leader(self, group_id: str, new_leader_id: int):
        from bson import ObjectId
        await self.db.groups.update_one(
            {"_id": ObjectId(str(group_id))},
            {"$set": {"leader_id": new_leader_id}},
        )

    async def add_member_to_group_by_id(self, group_id: str, member_telegram_id: int):
        from bson import ObjectId
        await self.db.groups.update_one(
            {"_id": ObjectId(str(group_id))},
            {"$addToSet": {"members": member_telegram_id}},
        )

    async def remove_member_from_group_by_id(self, group_id: str, member_telegram_id: int):
        from bson import ObjectId
        await self.db.groups.update_one(
            {"_id": ObjectId(str(group_id))},
            {"$pull": {"members": member_telegram_id}},
        )

    async def get_group_members_by_group_id(self, group_id: str):
        group = await self.get_group_by_id(group_id)
        if not group or not group.get("members"):
            return []
        cursor = self.db.users.find({"telegram_id": {"$in": group["members"]}})
        return await cursor.to_list(length=None)

    async def delete_group(self, group_id: str):
        from bson import ObjectId
        await self.db.groups.delete_one({"_id": ObjectId(str(group_id))})

    # ───────────────── TASKS ─────────────────

    async def create_task(self, creator_id: int, assignee_id: int,
                          title: str, description: str, deadline: str = None):
        task = {
            "creator_id": creator_id,
            "assignee_id": assignee_id,
            "title": title,
            "description": description,
            "deadline": deadline,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "comments": [],
        }
        result = await self.db.tasks.insert_one(task)
        task["_id"] = result.inserted_id
        return task

    async def get_task(self, task_id: str):
        from bson import ObjectId
        return await self.db.tasks.find_one({"_id": ObjectId(task_id)})

    async def get_tasks_for_user(self, telegram_id: int):
        cursor = self.db.tasks.find({"assignee_id": telegram_id}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_tasks_created_by(self, telegram_id: int):
        cursor = self.db.tasks.find({"creator_id": telegram_id}).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_tasks_for_group(self, leader_id: int):
        groups = await self.get_groups_by_leader(leader_id)
        if not groups:
            return []
        members = set()
        for group in groups:
            members.update(group.get("members", []))
        if not members:
            return []
        cursor = self.db.tasks.find(
            {"assignee_id": {"$in": list(members)}}
        ).sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def get_all_tasks(self):
        cursor = self.db.tasks.find().sort("created_at", -1)
        return await cursor.to_list(length=None)

    async def update_task_status(self, task_id: str, status: str):
        from bson import ObjectId
        await self.db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )

    async def add_task_comment(self, task_id: str, author_id: int, text: str):
        from bson import ObjectId
        comment = {
            "author_id": author_id,
            "text": text,
            "created_at": datetime.utcnow(),
        }
        await self.db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$push": {"comments": comment}, "$set": {"updated_at": datetime.utcnow()}}
        )

    async def delete_task(self, task_id: str):
        from bson import ObjectId
        await self.db.tasks.delete_one({"_id": ObjectId(task_id)})

    # ───────────────── RECRUITMENT ─────────────────

    async def ensure_default_recruitment_tree(self):
        existing_count = await self.db.recruitment_nodes.count_documents({})
        if existing_count > 0:
            await self.db.recruitment_nodes.delete_many({"name": {"$in": ["Історик", "історик"]}})
            return

        async def insert_branch(node: dict, parent_id=None):
            doc = {
                "name": node["name"],
                "kind": node["kind"],
                "parent_id": parent_id,
                "created_at": datetime.utcnow(),
            }
            result = await self.db.recruitment_nodes.insert_one(doc)
            node_id = result.inserted_id
            for child in node.get("children", []):
                await insert_branch(child, node_id)

        for root in DEFAULT_RECRUITMENT_TREE:
            await insert_branch(root)

    async def create_recruitment_node(self, name: str, kind: str, parent_id: str = None):
        from bson import ObjectId
        payload = {
            "name": name.strip(),
            "kind": kind,
            "parent_id": ObjectId(parent_id) if parent_id else None,
            "created_at": datetime.utcnow(),
        }
        result = await self.db.recruitment_nodes.insert_one(payload)
        payload["_id"] = result.inserted_id
        return payload

    async def get_recruitment_children(self, parent_id: str = None):
        from bson import ObjectId
        query_parent = ObjectId(parent_id) if parent_id else None
        cursor = self.db.recruitment_nodes.find({"parent_id": query_parent}).sort("name", 1)
        return await cursor.to_list(length=None)

    async def get_recruitment_nodes_by_kind(self, kind: str):
        cursor = self.db.recruitment_nodes.find({"kind": kind}).sort("name", 1)
        return await cursor.to_list(length=None)

    async def get_recruitment_node(self, node_id: str):
        from bson import ObjectId
        return await self.db.recruitment_nodes.find_one({"_id": ObjectId(node_id)})

    async def get_recruitment_full_tree(self):
        nodes = await self.db.recruitment_nodes.find().to_list(length=None)
        by_parent: dict[str | None, list[dict]] = {}

        for node in nodes:
            parent_id = str(node["parent_id"]) if node.get("parent_id") else None
            by_parent.setdefault(parent_id, []).append(node)

        for parent_key in by_parent:
            by_parent[parent_key].sort(key=lambda item: item["name"])

        def build(parent_id: str | None):
            result = []
            for node in by_parent.get(parent_id, []):
                item = {
                    "_id": node["_id"],
                    "name": node["name"],
                    "kind": node.get("kind"),
                    "parent_id": node.get("parent_id"),
                    "children": build(str(node["_id"])),
                }
                result.append(item)
            return result

        return build(None)

    async def rename_recruitment_node(self, node_id: str, new_name: str):
        from bson import ObjectId
        await self.db.recruitment_nodes.update_one(
            {"_id": ObjectId(node_id)},
            {"$set": {"name": new_name.strip()}},
        )

    async def delete_recruitment_node(self, node_id: str):
        from bson import ObjectId

        root_id = ObjectId(node_id)
        all_nodes = await self.db.recruitment_nodes.find().to_list(length=None)
        by_parent: dict[str, list[dict]] = {}
        for node in all_nodes:
            parent_id = node.get("parent_id")
            if parent_id:
                by_parent.setdefault(str(parent_id), []).append(node)

        to_delete = [root_id]
        queue = [str(root_id)]
        while queue:
            current_id = queue.pop(0)
            children = by_parent.get(current_id, [])
            for child in children:
                child_id = child["_id"]
                to_delete.append(child_id)
                queue.append(str(child_id))

        await self.db.recruitment_nodes.delete_many({"_id": {"$in": to_delete}})

    async def get_recruitment_path(self, node_id: str):
        from bson import ObjectId
        path = []
        current = await self.db.recruitment_nodes.find_one({"_id": ObjectId(node_id)})
        while current:
            path.append(current)
            parent_id = current.get("parent_id")
            if not parent_id:
                break
            current = await self.db.recruitment_nodes.find_one({"_id": parent_id})
        path.reverse()
        return path

    async def create_application(
        self,
        applicant_id: int,
        username: str,
        full_name: str,
        application_type: str,
        selections: list,
        extra: dict = None,
    ):
        payload = {
            "applicant_id": applicant_id,
            "username": username,
            "full_name": full_name,
            "application_type": application_type,
            "selections": selections,
            "extra": extra or {},
            "created_at": datetime.utcnow(),
        }
        result = await self.db.applications.insert_one(payload)
        payload["_id"] = result.inserted_id
        return payload

    async def get_recent_applications(self, limit: int = 30):
        cursor = self.db.applications.find().sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_application_analytics(self):
        pipeline = [
            {"$group": {"_id": "$application_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        by_type = await self.db.applications.aggregate(pipeline).to_list(length=None)
        total = await self.db.applications.count_documents({})
        applicants = len(await self.db.applications.distinct("applicant_id"))
        return {"total": total, "unique_applicants": applicants, "by_type": by_type}


db = Database()
