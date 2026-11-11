"""Validate incoming Alexa HTTPS requests using Amazon's official ASK verifiers.

Only safe stage codes are exposed to logs. Never log headers, request bodies,
signature/certificate contents, questions, or skill identifiers.
"""
import json
import os

from ask_sdk_core.serialize import DefaultSerializer
from ask_sdk_model.request_envelope import RequestEnvelope
from ask_sdk_webservice_support.verifier import RequestVerifier, TimestampVerifier


class AlexaValidationError(ValueError):
    def __init__(self, stage: str, category: str):
        super().__init__(stage)
        self.stage = stage
        self.category = category


def _checked(stage, operation):
    try:
        return operation()
    except Exception as exc:
        raise AlexaValidationError(stage, type(exc).__name__) from None


def validate_alexa_request(headers, raw_body: bytes) -> dict:
    expected_skill_id = os.environ.get("ALEXA_SKILL_ID", "").strip()
    if not expected_skill_id:
        raise AlexaValidationError("configuration", "MissingSkillId")
    if len(raw_body) > 65536:
        raise AlexaValidationError("body_size", "TooLarge")

    serialized = _checked("body_utf8", lambda: raw_body.decode("utf-8"))
    payload = _checked("body_json", lambda: json.loads(serialized))
    envelope = _checked(
        "sdk_deserialization",
        lambda: DefaultSerializer().deserialize(
            payload=serialized, obj_type=RequestEnvelope
        ),
    )

    # Verify the original body, certificate chain and timestamp; never bypass.
    _checked(
        "signature",
        lambda: RequestVerifier().verify(headers, serialized, envelope),
    )
    _checked(
        "timestamp",
        lambda: TimestampVerifier().verify(headers, serialized, envelope),
    )

    session_app = (payload.get("session") or {}).get("application") or {}
    context_app = ((payload.get("context") or {}).get("System") or {}).get("application") or {}
    received_skill_id = session_app.get("applicationId") or context_app.get("applicationId")
    if received_skill_id != expected_skill_id:
        raise AlexaValidationError("skill_id", "Mismatch")
    return payload
