from datetime import datetime,timezone,timedelta, date
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from app.db.mongo import users_collection,sessions_collection,email_pin_collection,security_events_collection

async def create_user(
    name: str,
    email: str,
    phone: str | None,
    date: date,
    sex: str,
    role: str = "client",
):
    user = {
        "name": name.strip(),
        "email": email.lower().strip(),
        "phone": phone.strip() if phone else None,
        "date": datetime.combine(date, datetime.min.time()),
        "sex": sex,
        "role": role,
        "is_verified": False,
        "is_blocked": False,
        "history":[],
        "failed_login_attempts": 0,
        "blocked_until": None,
        "password_hash": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await users_collection.insert_one(user)
    user_id = str(result.inserted_id)
    return {
        "id": user_id,
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "date": user["date"],
        "sex": user["sex"],
        "role": user["role"],
        "is_verified": user["is_verified"],
        "is_blocked": user["is_blocked"],
        "created_at": user["created_at"],
    }

async def get_user_by_id(user_id: str):
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    if not user:
        return None
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "phone": user.get("phone"),
        "date": user["date"],
        "sex": user["sex"],
        "role": user["role"],
        "is_verified": user["is_verified"],
        "is_blocked": user["is_blocked"],
        "created_at": user["created_at"],
        "blocked_until": user.get("blocked_until"),
        "failed_login_attempts": user.get("failed_login_attempts", 0),
    }

async def get_user_by_email(email: str):
    user = await users_collection.find_one(
        {"email": email.lower().strip()}
    )
    if not user:
        return None
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "date": user["date"],
        "sex": user["sex"],
        "role": user["role"],
        "is_verified": user["is_verified"],
        "is_blocked": user["is_blocked"],
        "failed_login_attempts": user["failed_login_attempts"],
        "blocked_until": user["blocked_until"],
        "created_at": user["created_at"],
        "password_hash": user["password_hash"]
    }

async def set_user_verified(user_id: str):
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_verified": True}}
    )
    return result.modified_count > 0

async def set_user_password(user_id: str, password_hash: str):
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": password_hash}}
    )
    return result.modified_count > 0

async def log_security_event(user_id=None, email=None, ip=None, event_type=None, metadata=None):
    await security_events_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "ip_address": ip,
        "event_type": event_type,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc)
    })

async def upsert_email_pin(user_id: str, pin_hash: str, purpose: str, expires_at: datetime,
                            request_count: int, last_requested_at: datetime, ip_address: str | None):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {
            "$set": {
                "pin_hash": pin_hash,
                "expires_at": expires_at,
                "attempts": 0,
                "request_count": request_count,
                "last_requested_at": last_requested_at,
                "blocked_until": None,
                "is_verified": False,
                "ip_address": ip_address,
                "updated_at": datetime.now(timezone.utc)
            },
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )
async def get_active_pin(user_id: str):
    now = datetime.now(timezone.utc)
    return await email_pin_collection.find_one({
        "user_id": user_id,
        "expires_at": {"$gt": now},
        "$or": [
            {"blocked_until": None},
            {"blocked_until": {"$lt": now}}
        ]
    })

async def block_pin_requests(user_id: str, purpose: str, blocked_until: datetime):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {"$set": {"blocked_until": blocked_until}}
    )

async def count_active_sessions(user_id: str) -> int:
    return await sessions_collection.count_documents({
        "user_id": user_id,
        "is_active": True
    })

async def create_session(user_id: str, refresh_hash: str, user_agent: str | None, ip: str | None):
    session = {
        "user_id": user_id,
        "refresh_token_hash": refresh_hash,
        "user_agent": user_agent,
        "ip_address": ip,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    result = await sessions_collection.insert_one(session)
    session["_id"] = str(result.inserted_id)
    return session

async def get_session_by_refresh_hash(refresh_hash: str):
    session = await sessions_collection.find_one({
        "refresh_token_hash": refresh_hash,
        "is_active": True
    })
    if not session:
        return None
    session["id"] = str(session["_id"])
    del session["_id"]
    return session

async def get_session_by_id(session_id: str):
    session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
    if not session:
        return None
    session["id"] = str(session["_id"])
    del session["_id"]
    return session

async def deactivate_session(session_id: str):
    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"is_active": False}}
    )

async def deactivate_all_sessions(user_id: str):
    await sessions_collection.update_many(
        {"user_id": user_id},
        {"$set": {"is_active": False}}
    )

async def increment_pin_attempts(user_id: str, purpose: str):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {"$inc": {"attempts": 1}}
    )

async def invalidate_pin_success(user_id: str, purpose: str):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {
            "$set": {
                "expires_at": datetime.now(timezone.utc),
                "attempts": 0,
                "blocked_until": None,
                "request_count": 0,
                "is_verified": True,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

async def invalidate_pin(user_id: str, purpose: str):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {
            "$set": {
                "expires_at": datetime.now(timezone.utc),
                "blocked_until": datetime.now(timezone.utc) + timedelta(hours=1),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

async def block_pin(user_id: str, until: datetime):
    await email_pin_collection.update_many(
        {"user_id": user_id},
        {"$set": {"blocked_until": until}}
    )

async def cleanup_expired_pins():
    limit = datetime.now(timezone.utc) - timedelta(days=1)
    await email_pin_collection.delete_many({"expires_at": {"$lt": limit}})

async def get_active_pin_by_purpose(user_id: str, purpose: str):
    now = datetime.now(timezone.utc)
    return await email_pin_collection.find_one({
        "user_id": user_id,
        "purpose": purpose,
        "expires_at": {"$gt": now},
        "$or": [
            {"blocked_until": None},
            {"blocked_until": {"$lt": now}}
        ]
    })

async def mark_pin_verified(user_id: str, purpose: str):
    await email_pin_collection.update_one(
        {"user_id": user_id, "purpose": purpose},
        {"$set": {"is_verified": True, "updated_at": datetime.now(timezone.utc)}}
    )
async def count_recent_pin_requests_by_ip(ip: str, window_minutes: int):
    limit = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return await email_pin_collection.count_documents({
        "ip_address": ip,
        "last_requested_at": {"$gt": limit}
    })

async def increment_failed_login(user_id: str):
    result = await users_collection.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$inc": {"failed_login_attempts": 1}},
        return_document=ReturnDocument.AFTER
    )
    if not result:
        return None
    return result.get("failed_login_attempts", 0)

async def block_user_until(user_id: str, until: datetime):
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"blocked_until": until}}
    )

async def reset_failed_logins(user_id: str):
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"failed_login_attempts": 0, "blocked_until": None}}
    )

async def update_session_refresh_hash(session_id: str, refresh_hash: str):
    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"refresh_token_hash": refresh_hash}}
    )

async def get_verified_pin_by_purpose(user_id: str, purpose: str):
    now = datetime.now(timezone.utc)
    return await email_pin_collection.find_one({
        "user_id": user_id,
        "purpose": purpose,
        "is_verified": True,
        "expires_at": {"$gt": now},
        "$or": [
            {"blocked_until": None},
            {"blocked_until": {"$lt": now}}
        ]
    })

async def update_user_profile(user_id: str, data: dict):
    allowed = {"name", "phone", "sex"}
    clean_data = {k: v for k, v in data.items() if k in allowed}
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return False
    if not clean_data:
        return False
    if "name" in clean_data:
        clean_data["name"] = clean_data["name"].strip()
    if "phone" in clean_data and clean_data["phone"]:
        clean_data["phone"] = clean_data["phone"].strip()
    result = await users_collection.update_one(
        {"_id": ObjectId(oid)},
        {"$set": clean_data}
    )
    return result.modified_count > 0

async def get_staff_emails(exclude_email: str) -> list[str]:
    cursor = users_collection.find(
        {
            "role": {"$in": ["admin", "moderator"]},
            "email": {"$ne": exclude_email}
        },
        {"email": 1}
    )
    emails = [doc["email"] async for doc in cursor if doc.get("email")]
    return list(set(emails))