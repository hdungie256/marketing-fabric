import json
import urllib.error
import urllib.request
from typing import Any


class HttpError(Exception):
    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}: {body[:500]}")
        self.status = status


def request(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 60) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as e:
        raise HttpError(method, url, e.code, e.read().decode(errors="replace")) from e
    try:
        return json.loads(raw)
    except ValueError:
        return {}
