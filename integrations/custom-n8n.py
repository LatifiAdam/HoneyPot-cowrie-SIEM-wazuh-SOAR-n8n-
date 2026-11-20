#!/usr/bin/env python3
"""Wazuh custom integration: forward one JSON alert to an n8n webhook.

Wazuh supplies: alert JSON path, API key/token, webhook URL.
The secret is passed at runtime and must never be hard-coded here.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: custom-n8n.py <alert-json-path> <api-key> <webhook-url>",
            file=sys.stderr,
        )
        return 2

    alert_path = Path(sys.argv[1])
    api_key = sys.argv[2]
    webhook_url = sys.argv[3]

    if not alert_path.is_file():
        print(f"Alert file does not exist: {alert_path}", file=sys.stderr)
        return 2
    if not api_key or not webhook_url.startswith(("http://", "https://")):
        print("Missing token or invalid webhook URL", file=sys.stderr)
        return 2

    try:
        with alert_path.open("r", encoding="utf-8") as handle:
            alert = json.load(handle)

        payload = json.dumps(alert).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Wazuh-Token": api_key,
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            print(f"n8n webhook returned HTTP {response.status}")
            return 0 if 200 <= response.status < 300 else 1

    except urllib.error.HTTPError as exc:
        print(f"n8n HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"Integration error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
