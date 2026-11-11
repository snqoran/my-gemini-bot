"""Validate incoming Alexa HTTPS requests using Amazon's official ASK verifier."""
import json
import os

from ask_sdk_core.serialize import DefaultSerializer
from ask_sdk_model.request_envelope import RequestEnvelope
from ask_sdk_webservice_support.verifier import RequestVerifier, TimestampVerifier


def validate_alexa_request(headers, raw_body: bytes) -> dict:
    expected_skill_id = os.environ.get("ALEXA_SKILL_ID", "").strip()
    if not expected_skill_id:
        raise ValueError("ALEXA_SKILL_ID is not configured")

    if len(raw_body) > 65536:
        raise ValueError("Request too large")
    text = raw_body.decode("utf-8")
    payload = json.loads(text)
    envelope = DefaultSerializer().deserialize(text, RequestEnvelope)

    # The SHA-256 signature is calculated over the *original* request body.
    RequestVerifier().verify(headers, text, envelope)
    TimestampVerifier().verify(headers, text, envelope)

    session_app = (payload.get("session") or {}).get("application") or {}
    context_app = ((payload.get("context") or {}).get("System") or {}).get("application") or {}
    app_id = session_app.get("applicationId") or context_app.get("applicationId")
    if app_id != expected_skill_id:
        raise ValueError("Wrong Alexa applicationId")
    return payload
