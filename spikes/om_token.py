import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

OM = os.environ["OM_URL"] + "/v1/"
DEFAULT_PASSWORD = "admin"
TOKEN_FILE = Path(os.environ.get("OM_BOT_TOKEN_FILE", "/run/om/bot_token"))


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(OM + path, data, headers, method=method)) as response:
        raw = response.read()
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def login(email: str, password: str) -> str | None:
    body = {"email": email, "password": base64.b64encode(password.encode()).decode()}
    try:
        return call("POST", "users/login", body)["accessToken"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None
        raise


def admin_token() -> str:
    user = os.environ["OM_ADMIN_USER"]
    password = os.environ["OM_ADMIN_PASSWORD"]
    email = f"{user}@open-metadata.org"
    token = login(email, password)
    if token:
        return token
    token = login(email, DEFAULT_PASSWORD)
    if not token:
        raise SystemExit("OpenMetadata admin login failed with OM_ADMIN_PASSWORD and the default password")
    change = {
        "username": user,
        "oldPassword": DEFAULT_PASSWORD,
        "newPassword": password,
        "confirmPassword": password,
        "requestType": "SELF",
    }
    call("PUT", "users/changePassword", change, token)
    print("admin password set from OM_ADMIN_PASSWORD", flush=True)
    return login(email, password)


if __name__ == "__main__":
    token = admin_token()
    bot_user = call("GET", "bots/name/ingestion-bot", token=token)["botUser"]["id"]
    jwt = call("GET", f"users/auth-mechanism/{bot_user}", token=token)["config"]["JWTToken"]
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(jwt)
    TOKEN_FILE.chmod(0o600)
    print(f"bot token written to {TOKEN_FILE}", flush=True)
