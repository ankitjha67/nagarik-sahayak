"""Profile management routes."""
import json
from fastapi import HTTPException
from database import prisma
from models import ProfileUpdate
from routes import api_router


@api_router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = {}
    if user.profile:
        profile = json.loads(user.profile) if isinstance(user.profile, str) else user.profile
    return {
        "id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "profile_complete": profile.get("_complete", False),
        "created_at": user.createdAt.isoformat() if user.createdAt else "",
    }


@api_router.put("/profile/{user_id}")
async def update_profile(user_id: str, update: ProfileUpdate):
    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = {}
    if update.language:
        data["language"] = update.language
    if update.profile_data:
        data["profile"] = json.dumps(update.profile_data, ensure_ascii=False)
        # Refresh identity fingerprints from the merged view, since the fraud
        # engine compares against a merged profile too. Computing them from this
        # endpoint's payload alone would drop identifiers held in fullProfile.
        import identity_index

        merged = {}
        if user.fullProfile:
            try:
                merged = (json.loads(user.fullProfile)
                          if isinstance(user.fullProfile, str)
                          else dict(user.fullProfile))
            except (ValueError, TypeError):
                merged = {}
        merged.update(update.profile_data)
        data = identity_index.merge_into_update(data, merged)

        # Fingerprints are derived above from the full values; what gets
        # written must not contain the Aadhaar itself.
        from dpdp import aadhaar_policy
        storable, _ = aadhaar_policy.strip_for_storage(update.profile_data)
        aadhaar_policy.assert_no_stored_aadhaar(storable, where="User.profile")
        data["profile"] = json.dumps(storable, ensure_ascii=False)
    if data:
        user = await prisma.user.update(where={"id": user_id}, data=data)
    profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    return {
        "id": user.id, "phone": user.phone, "language": user.language,
        "name": profile.get("name", ""), "profile_data": profile,
        "created_at": user.createdAt.isoformat() if user.createdAt else "",
    }
