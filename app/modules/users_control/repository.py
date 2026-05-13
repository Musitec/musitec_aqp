from app.db.mongo import users_collection
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from bson.errors import InvalidId
import logging, re

logger = logging.getLogger(__name__)

async def add_user_history(
    email: str,
    action: str,
    message: str,
    request,
    role: str,
    entity: str = None,
    entity_id: str = None,
    result: str = "success",
    extra: dict = None,
    now: datetime = None
):
    try:
        if now is None:
            now = datetime.now(timezone.utc)
        ip = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None
        history_item = {
            "action": action,
            "message": message,
            "made_at": now,
            "ts": now.timestamp(),
            "role": role,
            "entity": entity,
            "entity_id": entity_id,
            "result": result,
            "context": {
                "ip": ip,
                "user_agent": user_agent,
                "method": request.method,
                "path": request.url.path
            }
        }
        if extra:
            history_item["extra"] = extra
        result_db = await users_collection.update_one(
            {"email": email},
            {
                "$push": {
                    "history": {
                        "$each": [history_item],
                        "$slice": -50
                    }
                }
            }
        )
        return result_db.matched_count == 1
    except Exception as e:
        print(f"Error {e}")
        return False
    
async def update_user_role(email: str, new_role: str, now:datetime):
    try:
        result = await users_collection.update_one(
            {"email": email.lower().strip()},
            {
                "$set": {
                    "role": new_role,
                    "updated_at": now
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error actualizando rol de usuario {email}: {e}")
        return False
    
async def update_user_block_status(
    email: str,
    is_blocked: bool,
    now: datetime,
    blocked_until: Optional[datetime] = None
) -> bool:
    try:
        email = email.lower().strip()
        update_fields = {
            "is_blocked": is_blocked,
            "updated_at": now
        }
        if is_blocked:
            update_fields["blocked_until"] = blocked_until
        else:
            update_fields["blocked_until"] = None
        result = await users_collection.update_one(
            {"email": email},
            {"$set": update_fields}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error actualizando bloqueo de usuario {email}: {e}")
        return False
    
async def get_user_by_id(user_id: str):
    try:
        obj_id = ObjectId(user_id)
    except InvalidId:
        return None
    user = await users_collection.find_one({"_id": obj_id})
    if not user:
        return None
    user["id"] = str(user["_id"])
    del user["_id"]
    return user

async def get_users(
    page: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    role: Optional[str] = None
):
    query = {}
    if search:
        search_regex = re.compile(re.escape(search), re.IGNORECASE)
        query["$or"] = [
            {"name": search_regex},
            {"email": search_regex}
        ]
    if is_blocked is not None:
        query["is_blocked"] = is_blocked
    if role:
        if role == "staff":
            query["role"] = {"$in": ["admin", "moderator"]}
        else:
            query["role"] = role
    total = await users_collection.count_documents(query)
    cursor = users_collection.find(query)\
        .skip(page * limit)\
        .limit(limit)\
        .sort("created_at", -1)
    users = []
    async for user in cursor:
        user["id"] = str(user["_id"])
        del user["_id"]
        users.append(user)
    return {
        "data": users,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }