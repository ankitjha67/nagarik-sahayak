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
