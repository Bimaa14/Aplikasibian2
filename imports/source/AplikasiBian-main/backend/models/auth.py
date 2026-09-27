"""Auth models — login request and the user payload returned by /api/auth/*."""
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    username: str
    role: Literal["admin", "kasir"] = "kasir"
