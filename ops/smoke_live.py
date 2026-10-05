"""One-time live deployment check; run on the VM as root from the checkout.

Creates a random probe account, restarts the API container, then logs in again
to verify that HTTPS, the registration secret, and the SQLite volume work.
No password, invitation code, or session token is printed or saved.
"""

import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
domain = next(
    line.partition("=")[2].strip()
    for line in (ROOT / "ops/production.env").read_text().splitlines()
    if line.startswith("TRIPOTHON_DOMAIN=")
)
base = f"https://{domain}"
invitation = (ROOT / "ops/secrets/registration-code").read_text().strip()
username = "probe_" + secrets.token_hex(4)
password = secrets.token_urlsafe(24) + 'Aa!'


def request(method, path, payload=None, token=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(base + path, body, headers, method=method), timeout=20) as response:
        return json.load(response)


def ready():
    for _ in range(20):
        try:
            status = request("GET", "/health")
            if status.get("ok") and status.get("mode") == "live":
                return
        except (HTTPError, URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError("HTTPS health check did not recover")


ready()
credentials = {"username": username, "password": password, "invitation": invitation}
session = request("POST", "/v1/auth/register", credentials)
assert request("GET", "/v1/me", token=session["token"])["username"] == username

subprocess.run(["docker", "restart", "ops-api-1"], check=True, capture_output=True)
ready()
session = request("POST", "/v1/auth/login", credentials)
assert request("GET", "/v1/me", token=session["token"])["username"] == username

print("OK: HTTPS registration, authenticated read, and SQLite persistence after API restart")
