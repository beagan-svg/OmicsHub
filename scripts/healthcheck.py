"""Check the web service and exit 0 when it is ready or 1 when it is not.

Runs `GET /healthz/` against the gunicorn in this container, so it reports what this
process can actually serve rather than what a load balancer can reach. config/health.py
answers 200 when the database, the broker, and a worker consuming the submissions queue
are all up, and 503 otherwise; this turns that into an exit status.

Two headers, both of which the check fails without under omicshub.settings.prod:

  Host                 ALLOWED_HOSTS is a production hostname, and a request to
                       127.0.0.1 is a DisallowedHost 400 unless it carries a name from
                       that list. Taken from the environment rather than hardcoded so
                       there is nothing here to keep in sync.
  X-Forwarded-Proto    prod sets SECURE_SSL_REDIRECT, which answers a plain-HTTP request
with a 301 to https://<host>/healthz/ on the external load balancer,
                       the real load balancer, which is not what we are checking. The
                       proxy header is what tells Django the request already arrived over
                       TLS; it is the same header SECURE_PROXY_SSL_HEADER names.

Plain urllib, no requests: this runs on every healthcheck interval in the runtime image,
and it should not be the reason a dependency is in it.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

URL = f"http://127.0.0.1:{os.environ.get('HEALTHCHECK_PORT', '8000')}/healthz/"
TIMEOUT = 5


def _host_header() -> str | None:
    """Return the first concrete hostname in ALLOWED_HOSTS.

Entries like "*" and ".example.com" are patterns, not names. Sending either as a Host
header would be rejected by the check it is meant to satisfy, so skip them.
    An empty result means no header, which is right for dev settings where ALLOWED_HOSTS
    already contains 127.0.0.1.
    """
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
