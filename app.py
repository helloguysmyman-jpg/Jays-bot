"""Killarney SMS bot: Twilio webhook + local test CLI.

Run the webhook (production uses gunicorn, see Procfile):
    python app.py

Test a command locally with no SMS and no Twilio:
    python app.py test "JAYS"
    python app.py test "weather"
"""
import logging
import os
import sys
import time

from flask import Flask, Response, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

import config, router
from ratelimit import limiter

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("app")

app = Flask(__name__)
_validator = (
    RequestValidator(config.TWILIO_AUTH_TOKEN) if config.TWILIO_AUTH_TOKEN else None
)


def _mask(number):
    return "****" + number[-4:] if number and len(number) >= 4 else "****"


def _webhook_url():
    """The exact public URL Twilio signed (needed to verify the signature)."""
    if config.PUBLIC_URL:
        return config.PUBLIC_URL
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}{request.path}"


def _valid_signature():
    if not config.VALIDATE_TWILIO_SIGNATURE:
        return True
    if not _validator:
        log.error("Signature validation is on but TWILIO_AUTH_TOKEN is not set")
        return False
    signature = request.headers.get("X-Twilio-Signature", "")
    return _validator.validate(_webhook_url(), request.form.to_dict(), signature)


@app.get("/health")
def health():
    return "ok", 200


@app.post("/sms")
def sms():
    start = time.time()
    if not _valid_signature():
        log.warning("rejected request with bad/absent Twilio signature")
        return Response("Forbidden", status=403)

    sender = request.form.get("From", "")
    body = request.form.get("Body", "")
    resp = MessagingResponse()

    if not limiter.allow(sender):
        # Silently drop: return empty TwiML so no outbound SMS is sent and a
        # leaked number cannot rack up usage.
        log.warning("rate-limited %s", _mask(sender))
        return Response(str(resp), mimetype="application/xml")

    reply = router.handle(body)
    resp.message(reply)
    log.info("from=%s body=%r reply_len=%d ms=%d",
             _mask(sender), (body or "").strip()[:24], len(reply),
             int((time.time() - start) * 1000))
    return Response(str(resp), mimetype="application/xml")


def _run_test(args):
    body = " ".join(args)
    reply = router.handle(body)
    if len(reply) <= 160:
        segments = 1
    else:
        segments = -(-len(reply) // 153)  # ceil; concatenated SMS use 153/seg
    print("-" * 44)
    print(reply)
    print("-" * 44)
    print(f"[{len(reply)} chars, ~{segments} SMS segment(s)]")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].lower() == "test":
        _run_test(sys.argv[2:])
    else:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
