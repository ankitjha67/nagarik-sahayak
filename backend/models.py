"""Pydantic request/response models."""
import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, Any
from config import validate_phone


class SendOTPRequest(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v):
        v = re.sub(r'\D', '', v.strip())
        if not validate_phone(v):
            raise ValueError('Invalid Indian phone number (10 digits, starting with 6-9)')
        return v


class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    # Admins with an enrolled authenticator must also present its code.
    totp: Optional[str] = None
    # A signed-in operator sets this to record the citizen's consent (the
    # citizen just proved the phone is theirs on the operator's device)
    # instead of starting a session for the citizen.
    for_operator: bool = False
    consent_minutes: Optional[int] = 60

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v):
        v = re.sub(r'\D', '', v.strip())
        if not validate_phone(v):
            raise ValueError('Invalid phone number')
        return v


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    message: str
    user_id: Optional[str] = None
    phone: Optional[str] = None
    # Issued on a successful verify-otp. The access token is short-lived and
    # signed; the refresh token is opaque and rotates on every use.
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    role: Optional[str] = None
    # send-otp: whether a fixed demo code was used instead of a delivered one.
    mock: Optional[bool] = None
    # verify-otp with for_operator: how long the recorded consent lasts.
    consent_expires_in: Optional[int] = None


class ChatMessageRequest(BaseModel):
    user_id: str
    content: str
    language: str = "hi"


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None


class SearchSchemesRequest(BaseModel):
    query: str


class EligibilityCheckRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    query: Optional[str] = ""


class GeneratePDFRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    scheme_id: Optional[str] = None


class FilledFormRequest(BaseModel):
    user_id: str
    scheme_id: str
