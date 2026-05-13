from app.db.mongo import reclamations_collection, counters_collection
from typing import Optional,List
from pydantic import EmailStr
from datetime import datetime, timedelta
from bson.errors import InvalidId
from bson import ObjectId
from pymongo import ReturnDocument

def parse_object_id(id: str):
    try:
        return ObjectId(id)
    except InvalidId:
        return None

def status_traductor(my_status):
    if my_status =="open":
        return "Abierto"
    elif my_status=="in_review":
        return "En revisión"
    elif my_status=="resolved":
        return "Resuelto"
    else:
        return "Rechazado"

def add_business_days(start_date: datetime, days: int) -> datetime:
    current_date = start_date
    business_days_added = 0
    peru_holidays_2026 = [
        datetime(2026, 1, 1),
        datetime(2026, 4, 2),
        datetime(2026, 4, 3),
        datetime(2026, 5, 1),
        datetime(2026, 6, 29),
        datetime(2026, 7, 28),
        datetime(2026, 7, 29),
        datetime(2026, 8, 30),
        datetime(2026, 10, 8),
        datetime(2026, 11, 1),
        datetime(2026, 12, 8),
        datetime(2026, 12, 25),
    ]
    while business_days_added < days:
        current_date += timedelta(days=1)
        is_weekday = current_date.weekday() < 5
        is_holiday = any(holiday.date() == current_date.date() for holiday in peru_holidays_2026)
        if is_weekday and not is_holiday:
            business_days_added += 1
    return current_date

async def get_next_sequence(name: str):
    result = await counters_collection.find_one_and_update(
        {"_id": name},
        {"$setOnInsert": {"type":"reclamation"},
        "$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return result.get("seq", 1)

async def generate_reclamation_code(now:datetime):
    year = now.year
    seq = await get_next_sequence(f"reclamations_{year}")
    return f"REC-{year}-{str(seq).zfill(6)}"

async def create_reclamation(
    reclamation_code: str,
    name: str,
    customer_request:str,
    lastname: str,
    document_type: str,
    address: str,
    claimed_amount:Optional[float],
    phone: str,
    reclamation_type:str,
    document_number:str,
    user_email: EmailStr,
    order_id: str,
    products: Optional[List[str]],
    reason: str,
    now: datetime
):
    try:
        result = await reclamations_collection.insert_one({
            "code": reclamation_code,
            "company": {
                "name": "Musitec",
                "ruc": "10481821211",
                "address": "Calle Pizarro 341 segundo piso tienda 103"
            },
            "user":{
                "name": name,
                "lastname":lastname,
                "email":user_email,
                "document_type":document_type,
                "document_number":document_number,
                "address":address,
                "phone":phone
            },
            "claimed_amount":claimed_amount,
            "type": reclamation_type,
            "order": order_id,
            "products": products,
            "reason": reason,
            "customer_request": customer_request,
            "history": [],
            "attended_by":None,
            "current_status":"open",
            "response_channel": "email",
            "support_channel": "whatsapp",
            "close": False,
            "created_at": now,
            "accepted_terms": False,
            "accepted_at": None,
            "due_date" : add_business_days(now, 15)
        })
        return result.inserted_id
    except Exception as e:
        print(f"Error {e}")
        return None

async def find_by_order_and_user(order_id: str, user_email: str):
    return await reclamations_collection.find_one({
        "order": order_id,
        "user.email": user_email
    })

async def update_reclamation(employee_email: EmailStr, is_closed: bool, reclamation_id: str, current_status:str, status: str, message: str, now: datetime, evidences: Optional[List[dict]]):
    try:
        result = await reclamations_collection.update_one(
            {"_id": ObjectId(reclamation_id)},
            {
                "$set": {
                    "close": is_closed,
                    "current_status": status,
                    "attended_by": employee_email,
                    "updated_at": now
                },
                "$push": {
                    "history": {
                        "message": message,
                        "old_status": current_status,
                        "new_status": status,
                        "changed_by": employee_email,
                        "evidences": evidences,
                        "date": now
                    }
                }
            }
        )
        return result.matched_count == 1
    except InvalidId:
        print("ID inválido")
        return None
    except Exception as e:
        print(f"Error {e}")
        return None

async def get_reclamation(reclamation_id:str):
    try:
        rec_id = parse_object_id(reclamation_id)
        if not rec_id:
            return None
        result = await reclamations_collection.find_one({"_id":rec_id})
        if not result:
            return None
        result["id"] = str(result["_id"])
        del result["_id"]
        return result
    except InvalidId:
        print("ID inválido")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

async def set_reclamation_status(
    employee_email: EmailStr,
    reclamation_id: str,
    current_status: str,
    is_closed: bool,
    status: str,
    now: datetime
):
    try:
        result = await reclamations_collection.update_one(
            {"_id": ObjectId(reclamation_id)},
            {
                "$set": {
                    "close": is_closed,
                    "current_status": status,
                    "attended_by": employee_email,
                    "updated_at": now
                },
                "$push": {
                    "history": {
                        "message": f"Estado cambiado de {status_traductor(current_status)} a {status_traductor(status)} por {employee_email}",
                        "old_status": current_status,
                        "new_status": status,
                        "changed_by": employee_email,
                        "date": now
                    }
                }
            }
        )
        return result.matched_count == 1
    except InvalidId:
        print("ID inválido")
        return None
    except Exception as e:
        print(f"Error {e}")
        return None

async def get_user_reclamations(user_email: EmailStr, page: int = 0):
    try:
        page_size = 8
        if page == 0:
            skip = 0
            limit = page_size - 1
        else:
            skip = (page_size - 1) + (page_size * (page - 1))
            limit = page_size
        cursor = reclamations_collection.find(
            {"user.email": user_email}
        ).sort("created_at", -1).skip(skip).limit(limit)
        results = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            results.append(doc)
        total = await reclamations_collection.count_documents(
            {"user.email": user_email}
        )
        return {
            "data": results,
            "total": total,
            "page": page,
            "pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        print(f"Error: {e}")
        return None
    
async def accept_reclamation(reclamation_id: str, now: datetime):
    try:
        result = await reclamations_collection.update_one(
            {"_id": ObjectId(reclamation_id)},
            {
                "$set": {
                    
                    "accepted_terms": True,
                    "updated_at": now,
                    "accepted_at": now
                }
            }
        )
        return result.matched_count == 1
    except InvalidId:
        print("ID inválido")
        return None
    except Exception as e:
        print(f"Error {e}")
        return None

async def get_reclamations(
    page: int = 0,
    user_email: Optional[EmailStr] = None,
    employee_email: Optional[EmailStr] = None,
    status: Optional[str] = None,
    code: Optional[str] = None,
    is_closed: Optional[bool] = None
):
    try:
        page_size = 8
        skip = page * page_size
        query = {}
        if user_email:
            query["user.email"] = user_email
        if employee_email:
            query["attended_by"] = employee_email
        if status:
            query["current_status"] = status
        if is_closed is not None:
            query["close"] = is_closed
        if code:
            query["code"] = code.upper()
        cursor = reclamations_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(page_size)
        results = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            results.append(doc)
        total = await reclamations_collection.count_documents(query)
        return {
            "data": results,
            "total": total,
            "page": page,
            "pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        print(f"Error: {e}")
        return None