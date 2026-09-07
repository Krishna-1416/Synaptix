from typing import Optional
from pydantic import BaseModel


class SignUpRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "inspector"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "inspector"
    created_at: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserProfile] = None
    message: Optional[str] = None
