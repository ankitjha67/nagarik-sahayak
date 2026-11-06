"""Profile management routes."""
import json
from fastapi import HTTPException
from prisma import Json
from database import prisma, find_user
from models import ProfileUpdate
from routes import api_router


@api_router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from dpdp import profile_store
    profile = profile_store.load_basic(user)
    return {
        "id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "profile_complete": profile.get("_complete", False),
        "created_at": user.createdAt.isoformat() if user.createdAt else "",
    }


@api_router.put("/profile/{user_id}")
async def update_profile(user_id: str, update: ProfileUpdate):
    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = {}
    if update.language:
        data["language"] = update.language
    if update.profile_data:
        data["profile"] = update.profile_data   # replaced below, post-fingerprint
        # Refresh identity fingerprints from the merged view, since the fraud
        # engine compares against a merged profile too. Computing them from this
        # endpoint's payload alone would drop identifiers held in fullProfile.
        import identity_index

        from dpdp import profile_store

        merged = profile_store.load_full(user)
        merged.update(update.profile_data)
        data = identity_index.merge_into_update(data, merged)

        # Fingerprints are derived above from the full values; what is written
        # has the Aadhaar stripped and is encrypted at rest.
        #
        # profile is a Json column, so the prepared value — a ciphertext string
        # when encryption is on, a JSON string otherwise — must be wrapped in
        # Json(). Passing the raw ciphertext string unwrapped makes Prisma's
        # engine try to parse it as JSON and 500 every save once encryption is
        # enabled. The read path (profile_store) decodes a dict, a ciphertext
        # string or a plain JSON string alike, so Json() round-trips either way.
        prepared, _ = profile_store.prepare_basic_profile(update.profile_data)
        data["profile"] = Json(prepared)
    if data:
        user = await prisma.user.update(where={"id": user_id}, data=data)
    profile = profile_store.load_basic(user)
    return {
        "id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "created_at": user.createdAt.isoformat() if user.createdAt else "",
    }
