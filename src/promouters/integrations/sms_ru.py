from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from promouters.core.config import Settings


class SMSRuClient:
    base_url = "https://sms.ru/sms/send"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_login_code(self, phone: str, code: str) -> None:
        if not self.settings.sms_ru_api_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SMS provider is not configured",
            )

        payload = {
            "api_id": self.settings.sms_ru_api_id,
            "to": phone,
            "msg": f"Code for Promouters login: {code}",
            "json": 1,
            "test": int(self.settings.sms_ru_test),
        }
        if self.settings.sms_ru_from:
            payload["from"] = self.settings.sms_ru_from

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.base_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    content=urlencode(payload),
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMS provider is unavailable",
            ) from exc

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMS provider request failed",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMS provider returned invalid JSON",
            ) from exc
        if data.get("status") != "OK":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=data.get("status_text", "SMS provider returned an error"),
            )
