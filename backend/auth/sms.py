"""One-time code delivery, behind a provider interface.

The code never reaches a provider that is not configured. Providers:

  log      - writes the message to the server log (development only)
  msg91    - MSG91 Flow API, DLT-registered template (India)
  twilio   - Twilio Messages API
  webhook  - POST {phone, message, code} to any URL you run; the most
             portable option: route it to a gateway, a queue, a Kafka bridge

Select with SMS_PROVIDER. Every provider raises SmsError on failure so the
caller can answer 502 rather than tell the citizen a code was sent when it
was not.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TEMPLATE = "{code} is your Nagarik Sahayak OTP. Valid for 5 minutes. Never share it with anyone."


class SmsError(Exception):
    pass


class SmsProvider:
    key = "base"

    async def send(self, phone: str, message: str, code: str) -> None:
        raise NotImplementedError


class LogSms(SmsProvider):
    key = "log"

    async def send(self, phone, message, code):
        # The code itself is deliberately not logged outside DEBUG: logs are
        # shipped, and an OTP in a log line is an account takeover waiting.
        logger.info("SMS to %s****: OTP issued (log provider)", phone[:4])
        logger.debug("OTP for %s: %s", phone, code)


class Msg91Sms(SmsProvider):
    key = "msg91"

    async def send(self, phone, message, code):
        authkey = os.environ.get("MSG91_AUTHKEY", "")
        template = os.environ.get("MSG91_TEMPLATE_ID", "")
        if not authkey or not template:
            raise SmsError("MSG91_AUTHKEY and MSG91_TEMPLATE_ID are required")
        payload = {"template_id": template, "short_url": "0",
                   "recipients": [{"mobiles": f"91{phone}", "otp": code}]}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post("https://control.msg91.com/api/v5/flow/",
                                  headers={"authkey": authkey, "accept": "application/json"},
                                  json=payload)
        if r.status_code >= 300:
            raise SmsError(f"MSG91 refused: {r.status_code}")


class TwilioSms(SmsProvider):
    key = "twilio"

    async def send(self, phone, message, code):
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        sender = os.environ.get("TWILIO_FROM", "")
        if not (sid and token and sender):
            raise SmsError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM are required")
        async with httpx.AsyncClient(timeout=10, auth=(sid, token)) as client:
            r = await client.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                                  data={"From": sender, "To": f"+91{phone}", "Body": message})
        if r.status_code >= 300:
            raise SmsError(f"Twilio refused: {r.status_code}")


class WebhookSms(SmsProvider):
    key = "webhook"

    async def send(self, phone, message, code):
        url = os.environ.get("SMS_WEBHOOK_URL", "")
        if not url:
            raise SmsError("SMS_WEBHOOK_URL is required")
        headers = {"content-type": "application/json"}
        bearer = os.environ.get("SMS_WEBHOOK_TOKEN", "")
        if bearer:
            headers["authorization"] = f"Bearer {bearer}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, headers=headers, json={"phone": phone, "message": message, "code": code})
        if r.status_code >= 300:
            raise SmsError(f"SMS webhook refused: {r.status_code}")


_PROVIDERS = {p.key: p for p in (LogSms, Msg91Sms, TwilioSms, WebhookSms)}


def provider() -> SmsProvider:
    key = os.environ.get("SMS_PROVIDER", "log").strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise SmsError(f"Unknown SMS_PROVIDER '{key}'; choose one of {sorted(_PROVIDERS)}")
    return cls()


async def send_otp(phone: str, code: str) -> str:
    """Deliver the code; returns the provider key used."""
    p = provider()
    await p.send(phone, TEMPLATE.format(code=code), code)
    return p.key
