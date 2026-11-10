from pydantic import BaseModel, Field, field_validator

# 与 frontend/src/pages/onboarding/options.js 的兴趣标签保持一致；服务端以此目录为唯一校验来源。
INTEREST_CATALOG: dict[str, str] = {
    "sport": "体育运动",
    "film": "电影放映",
    "club": "社团活动",
    "lecture": "学术讲座",
    "music": "音乐演出",
    "volunteer": "课程旁听",
}


class InterestTag(BaseModel):
    tag: str
    label: str


class ProfileResponse(BaseModel):
    display_name: str
    bio: str
    interests: list[str]


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=32)
    bio: str | None = Field(default=None, max_length=200)
    interests: list[str] | None = Field(default=None, max_length=10)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Display name cannot be blank")
        return stripped

    @field_validator("bio")
    @classmethod
    def strip_bio(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()
