import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or email.count("@") != 1:
        raise ValueError("Invalid email address")
    local, domain = email.rsplit("@", 1)
    if (
        domain not in {"pku.edu.cn", "stu.pku.edu.cn"}
        or not local
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local) is None
    ):
        raise ValueError("Invalid email address")
    return email


class EmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class RegistrationRequest(EmailRequest):
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    remember: bool = False

    @model_validator(mode="after")
    def validate_credentials(self) -> "LoginRequest":
        if not self.email.strip() and not self.password:
            self.email = ""
            return self
        self.email = normalize_email(self.email)
        if not self.password:
            raise ValueError("Password is required")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
