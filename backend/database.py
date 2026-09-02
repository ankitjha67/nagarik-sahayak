"""Database clients — Prisma (async) and Motor (for OTP sessions)."""
import os
from prisma import Prisma
from motor.motor_asyncio import AsyncIOMotorClient

prisma = Prisma()

mongo_url = os.environ.get('MONGO_URL', '')
db_name = os.environ.get('DB_NAME', 'nagarik_sahayak')
motor_client = AsyncIOMotorClient(mongo_url) if mongo_url else None
motor_db = motor_client[db_name] if motor_client else None
