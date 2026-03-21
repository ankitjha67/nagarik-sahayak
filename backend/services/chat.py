"""Chat history persistence via Prisma ChatLog."""
import json
import logging
import traceback
from database import prisma

logger = logging.getLogger(__name__)


async def save_chat_prisma(user_id: str, msg_dict: dict, sender: str):
    """Save a rich message dict to Prisma ChatLog."""
    try:
        await prisma.chatlog.create(data={
            "userId": user_id,
            "message": json.dumps(msg_dict, ensure_ascii=False, default=str),
            "sender": sender,
        })
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"ChatLog serialization failed: {e}")
    except Exception as e:
        logger.error(f"Prisma ChatLog save failed: {e}\n{traceback.format_exc()}")


async def get_chat_history_prisma(user_id: str) -> list:
    """Read chat history for a user from Prisma ChatLog."""
    try:
        logs = await prisma.chatlog.find_many(
            where={"userId": user_id},
            order={"timestamp": "asc"},
            take=500,
        )
        messages = []
        for log in logs:
            try:
                msg = json.loads(log.message)
            except (json.JSONDecodeError, TypeError):
                msg = {"content": log.message, "role": log.sender}
            msg.setdefault("id", log.id)
            msg.setdefault("created_at", log.timestamp.isoformat() if log.timestamp else "")
            messages.append(msg)
        return messages
    except Exception as e:
        logger.error(f"Prisma ChatLog read failed: {e}\n{traceback.format_exc()}")
        return []
