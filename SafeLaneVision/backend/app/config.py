import os

def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)

# Core toggles
PROVIDER_MODE = os.getenv("PROVIDER_MODE", "free").lower()  # "free" or "premium"
MODE = PROVIDER_MODE  # backward compatibility if other modules used MODE
ALLOW_PUBLIC_READS = os.getenv("ALLOW_PUBLIC_READS", "true").lower() == "true"

# Networking and auth
HTTP_TIMEOUT_S = _get_float("HTTP_TIMEOUT_S", 15.0)
AUTH_CLOCK_SKEW_S = int(os.getenv("AUTH_CLOCK_SKEW_S", "300"))
DEVICE_SECRET = os.getenv("DEVICE_SECRET", "change_me")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/safelane",
)

# Providers (premium mode)
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

# API defaults
DEFAULT_RADIUS_M = int(os.getenv("DEFAULT_RADIUS_M", "800"))
DEFAULT_SINCE_MIN = int(os.getenv("DEFAULT_SINCE_MIN", "1440"))
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200"))

# Caching and limits
WEATHER_TTL_S = int(os.getenv("WEATHER_TTL_S", "300"))
ROUTE_RPS = _get_float("ROUTE_RPS", 1.0)
WEATHER_RPS = _get_float("WEATHER_RPS", 1.0)

# CORS
CORS_ALLOW_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]