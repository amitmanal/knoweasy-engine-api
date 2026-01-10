from __future__ import annotations

from pydantic import BaseModel, Field

class RequestOtpIn(BaseModel):
    email: str = Field(..., examples=["student@example.com"])
    role: str = Field(..., examples=["student"])

class RequestOtpOut(BaseModel):
    ok: bool
    message: str
    cooldown_seconds: int = 0

class VerifyOtpIn(BaseModel):
    email: str
    role: str
    otp: str = Field(..., min_length=4, max_length=10)

class VerifyOtpOut(BaseModel):
    ok: bool
    session_token: str | None = None
    is_new_user: bool | None = None
    user: dict | None = None
    error: str | None = None
    message: str | None = None
    retry_after_seconds: int | None = None

class LogoutIn(BaseModel):
    session_token: str

class BasicOut(BaseModel):
    ok: bool
    message: str | None = None


class ProfileUpsertIn(BaseModel):
    full_name: str = Field(..., examples=["Amit Manal"])
    board: str = Field(..., examples=["CBSE"])
    class_level: int = Field(..., examples=[9])

class ProfileOut(BaseModel):
    ok: bool
    profile: dict | None = None
    error: str | None = None
    message: str | None = None
