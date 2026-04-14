from config import ROLES

ROLE_ALIASES = {
    "керівник": "manager",
    "керівник групи": "group_leader",
    "рядовий": "member",
    "РєРµСЂС–РІРЅРёРє": "manager",
    "РєРµСЂС–РІРЅРёРє РіСЂСѓРїРё": "group_leader",
    "СЂСЏРґРѕРІРёР№": "member",
}


def role_level(role: str | None) -> int:
    if not role:
        return 0
    normalized = ROLE_ALIASES.get(role, role)
    return ROLES.get(normalized, 0)


def has_role(user_role: str | None, required_role: str) -> bool:
    return role_level(user_role) >= role_level(required_role)


def _role_key_by_level(level: int) -> str:
    for key, value in ROLES.items():
        if value == level:
            return key
    raise ValueError(f"Role with level={level} not found")


ROLE_ADMIN = _role_key_by_level(4)
ROLE_MANAGER = _role_key_by_level(3)
ROLE_GROUP_LEADER = _role_key_by_level(2)
ROLE_MEMBER = _role_key_by_level(1)
