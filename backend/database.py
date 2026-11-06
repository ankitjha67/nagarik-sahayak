"""Database clients — Prisma (async) and Motor (for OTP sessions)."""
import os
import re
from prisma import Prisma
from motor.motor_asyncio import AsyncIOMotorClient

prisma = Prisma()

# A Mongo ObjectId: 24 hex characters. Prisma raises (and the API answered
# 500) when a user id of any other shape reached it — a trailing space, a
# demo placeholder, a number. Checking the shape here turns every such call
# into the ordinary "no such user" path that each caller already handles.
_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{24}$")


def is_object_id(value) -> bool:
    return isinstance(value, str) and bool(_OBJECT_ID.match(value))


async def find_user(user_id):
    """The user with this id, or None — including for a malformed id."""
    if not is_object_id(user_id):
        return None
    return await prisma.user.find_unique(where={"id": user_id})


mongo_url = os.environ.get('MONGO_URL', '')
db_name = os.environ.get('DB_NAME', 'nagarik_sahayak')
motor_client = AsyncIOMotorClient(mongo_url) if mongo_url else None
motor_db = motor_client[db_name] if motor_client else None
