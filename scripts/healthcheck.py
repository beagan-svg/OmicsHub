"""Check the local web service and return an exit status."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

URL = f"http://127.0.0.1:{os.environ.get('HEALTHCHECK_PORT', '8000')}/healthz/"
TIMEOUT = 15


def _host_header() -> str | None:
    """Return the first concrete hostname in ALLOWED_HOSTS."""
    for entry in os.environ.get("ALLOWED_HOSTS", "").split(","):
        host = entry.strip()
        if host and not host.startswith((".", "*")):
            return host
    return None


def main() -> int:
    headers = {"X-Forwarded-Proto": "https"}
    host = _host_header()
    if host:
        headers["Host"] = host

    request = urllib.request.Request(URL, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status == 200:
                return 0
            print(f"{URL} returned {response.status}", file=sys.stderr)
            return 1
    except urllib.error.HTTPError as error:
        # 503 is the interesting one: the body names which dependency is down, and Docker
        # keeps the last healthcheck output, so printing it is how the reason survives.
        body = error.read(2000).decode("utf-8", "replace")
        print(f"{URL} returned {error.code}: {body}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - a healthcheck reports failures, never raises
        print(f"{URL} unreachable: {error!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
