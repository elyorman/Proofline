#!/usr/bin/env python3
"""Check the public link the way a judge uses it, and fail if any part is down.

    python scripts/check_live.py --web URL --api URL

It loads the replay page and the files the replay reads, asks the live API's health, and
asks one typed question live. The question's premise is one the data contradicts, so it
is answered in seconds for about 1,600 tokens of the API's daily budget. Standard library
only, so CI runs it without installing the project.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

REPLAY_FILES = ("", "fixtures/m01/meta.json", "fixtures/m01/events.jsonl")
QUESTION = {
    "match_id": "m01",
    "asked_at": {"period": 2, "minute": 68, "second": 0},
    "text": "Is Harbour City's defence tiring since 58?",
    "locale": "en",
}
ANSWER_WITHIN_S = 120


def fetch(url: str, body: dict | None = None) -> bytes:
    data = None if body is None else json.dumps(body).encode()
    headers = {} if data is None else {"content-type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read()[:200].decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from None


def check(web: str, api: str) -> list[str]:
    failed = []
    for path in REPLAY_FILES:
        try:
            fetch(f"{web}/{path}")
        except (OSError, RuntimeError) as error:
            failed.append(f"replay {web}/{path}: {error}")
    try:
        health = json.loads(fetch(f"{api}/api/health"))
        print(f"API health: {health}")
        job = json.loads(fetch(f"{api}/api/questions", QUESTION))
        deadline = time.monotonic() + ANSWER_WITHIN_S
        while job["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(2)
            job = json.loads(fetch(f"{api}/api/questions/{job['job_id']}"))
        if job["status"] != "done":
            failed.append(f"live question ended {job['status']}: {job.get('error')}")
        else:
            print(f"Live answer: {job['answer']['text']['en']}")
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        failed.append(f"live API {api}: {error}")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--web", required=True, help="the public link")
    parser.add_argument("--api", required=True, help="the live question API")
    args = parser.parse_args()
    failed = check(args.web.rstrip("/"), args.api.rstrip("/"))
    if failed:
        print("Public link check FAILED:")
        print("\n".join(failed))
        return 1
    print("Public link OK: replay, API health and one live question.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
