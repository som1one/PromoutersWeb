from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


class CompanyProfileData(BaseModel):
    website: str | None = Field(default=None)
    social_networks: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None)
    prepayment_available: bool = Field(default=False)
    phone_number: str | None = Field(default=None)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str | None) -> str | None:
        if not value:
            return value
        clean_phone = re.sub(r"[^\d+]", "", value)
        digits_only = re.sub(r"[^\d]", "", clean_phone)
        if clean_phone.startswith("+"):
            if len(digits_only) >= 10:
                return value
            raise ValueError("номер телефона должен содержать минимум 10 цифр")
        if len(digits_only) == 10:
            return value
        if len(digits_only) == 11 and clean_phone.startswith(("8", "7")):
            return value
        raise ValueError("используйте формат +XXXXXXXXXX или 8XXXXXXXXXX/7XXXXXXXXXX")

    @field_validator("photos")
    @classmethod
    def validate_photos(cls, value: list[str]) -> list[str]:
        if len(value) > 6:
            raise ValueError("максимум 6 фотографий")
        return value

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if not value:
            return value
        if not (value.startswith("http://") or value.startswith("https://")):
            return f"https://{value}"
        return value
