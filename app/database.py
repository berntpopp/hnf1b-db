# app/database.py
import motor.motor_asyncio
from app.config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
db = client[settings.DATABASE_NAME]

print("Connected to database:", db.name)  # Debug output
