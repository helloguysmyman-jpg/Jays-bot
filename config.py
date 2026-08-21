"""Configuration and constants.

Every secret comes from an environment variable - nothing sensitive is
hard-coded. A local .env file is loaded automatically for development; in
production the host (Railway/Render/Fly) injects the same variables.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Location: Killarney Provincial Park, George Lake Campground (Ontario) ---
# Deliberately the George Lake gatehouse - the park's only developed
# campground - NOT the town of Killarney (-81.51) or any other "Killarney".
KILLARNEY_LAT = 46.0126
KILLARNEY_LON = -81.4019
LOCATION_NAME = "Killarney PP"
TIMEZONE = "America/Toronto"  # Eastern Time; handles EDT/EST automatically

# --- MLB ---
BLUE_JAYS_ID = 141  # Toronto Blue Jays team id in the MLB Stats API

# --- HTTP ---
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "8"))  # seconds per API call
USER_AGENT = "killarney-sms-bot/1.0"

# --- Twilio ---
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
# Validate the X-Twilio-Signature header so only Twilio can trigger replies.
VALIDATE_TWILIO_SIGNATURE = (
    os.getenv("VALIDATE_TWILIO_SIGNATURE", "true").lower() == "true"
)
# Optional explicit public URL of the /sms webhook (recommended behind a proxy).
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")

# --- Rate limiting (stops a leaked number racking up unlimited usage) ---
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "6"))
RATE_LIMIT_PER_DAY = int(os.getenv("RATE_LIMIT_PER_DAY", "100"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
