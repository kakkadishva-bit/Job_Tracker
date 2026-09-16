"""
services/location/resolver.py

Per the product decision: the location a user *set in their profile*
is the source of truth. IP geolocation is only used as a fallback
default for users who haven't set one (e.g. logged-out visitors, or a
user who just signed up) - it is NOT allowed to override an explicit
profile setting, since IP location is frequently wrong (VPNs, mobile
carriers, corporate NAT, shared offices) and silently overriding a
user's own stated location would be a worse experience than just
defaulting to USD.

The role guides in app.py already carry salary_estimate.{usd,inr,eur} -
this module just decides which of those three keys to show first.
"""
from typing import Dict, Optional

import requests

from utils.logger import get_logger

logger = get_logger()

_INDIA_HINTS = {
    "india", "bharat", "bengaluru", "bangalore", "mumbai", "delhi", "new delhi",
    "hyderabad", "pune", "chennai", "kolkata", "noida", "gurugram", "gurgaon",
    "ahmedabad", "jaipur", "kochi", "chandigarh",
}
_EUROZONE_HINTS = {
    "germany", "france", "spain", "italy", "netherlands", "belgium", "austria",
    "portugal", "ireland", "greece", "finland", "luxembourg", "slovakia",
    "slovenia", "estonia", "latvia", "lithuania", "cyprus", "malta", "eurozone",
    "berlin", "paris", "madrid", "rome", "amsterdam", "lisbon", "dublin",
}

DEFAULT_CURRENCY_KEY = "usd"
DEFAULT_LOCATION_LABEL = "United States"
_IP_GEOLOCATE_TIMEOUT = 3


def resolve_currency_key(location_text: str) -> str:
    """Maps a free-text location to one of the currency keys already
    present in the role guides' salary_estimate dict (usd/inr/eur)."""
    if not location_text:
        return DEFAULT_CURRENCY_KEY
    text = location_text.strip().lower()
    if any(hint in text for hint in _INDIA_HINTS):
        return "inr"
    if any(hint in text for hint in _EUROZONE_HINTS):
        return "eur"
    return DEFAULT_CURRENCY_KEY


def _geolocate_ip(ip_address: str) -> Optional[str]:
    """Best-effort free IP geolocation. Returns None on any failure
    (private/local IP, network unavailable, rate-limited, etc.) so
    callers always have a safe default to fall back to."""
    if not ip_address or ip_address in ("127.0.0.1", "localhost", "::1"):
        return None
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip_address}",
            params={"fields": "status,country,city"},
            timeout=_IP_GEOLOCATE_TIMEOUT,
        )
        data = resp.json()
        if data.get("status") == "success":
            city, country = data.get("city", ""), data.get("country", "")
            label = ", ".join(p for p in (city, country) if p)
            return label or None
    except Exception as exc:
        logger.debug("IP geolocation skipped: %s", exc)
    return None


def resolve_location(user=None, request_ip: Optional[str] = None) -> Dict:
    """Returns {location, currency_key, source}.

    source is one of 'profile' | 'ip' | 'default', so the frontend can
    show something like "Showing salaries for Ahmedabad, India (from
    your profile) - change in Settings" and be transparent about where
    the number came from.
    """
    if user is not None and getattr(user, "is_authenticated", False):
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "location", None) and profile.location.strip():
            loc = profile.location.strip()
            return {"location": loc, "currency_key": resolve_currency_key(loc), "source": "profile"}

    ip_location = _geolocate_ip(request_ip) if request_ip else None
    if ip_location:
        return {"location": ip_location, "currency_key": resolve_currency_key(ip_location), "source": "ip"}

    return {"location": DEFAULT_LOCATION_LABEL, "currency_key": DEFAULT_CURRENCY_KEY, "source": "default"}


def annotate_salary_for_location(role_guide: Dict, currency_key: str) -> Dict:
    """Adds salary_estimate_local (a single string) to a role guide dict,
    without removing the original salary_estimate (usd/inr/eur) so the
    frontend can still offer a currency switcher if it wants one."""
    guide = dict(role_guide)
    salary = guide.get("salary_estimate")
    if isinstance(salary, dict):
        guide["salary_estimate_local"] = salary.get(currency_key) or salary.get(DEFAULT_CURRENCY_KEY)
        guide["salary_estimate_currency"] = currency_key
    return guide
