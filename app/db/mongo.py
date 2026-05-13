from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)

mongo_db = client[settings.musitec_db]
products_collection = mongo_db["products"]
users_collection = mongo_db["users"]
sessions_collection = mongo_db["sessions"]
email_pin_collection = mongo_db["email_pins"]
security_events_collection = mongo_db["security_events"]
carts_collection=mongo_db["carts"]
orders_collection=mongo_db["orders"]
reclamations_collection=mongo_db["reclamations"]
counters_collection = mongo_db["counters"]