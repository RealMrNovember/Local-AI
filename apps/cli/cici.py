#!/usr/bin/env python3
"""cici — CiciByte AI command-line client.

Phase 3 scope: just enough to exercise the kill switch from a terminal
(ROADMAP.md Phase 3, product brief Section 51/15). This is a thin HTTP
client against the backend's REST API — it holds no agent logic of its
own, per ARCHITECTURE.md's "no tight coupling" rule. More subcommands
(`cici chat`, `cici models`, ...) are added as their backend endpoints
mature in later phases.

Usage:
    cici stop [run_id]   # stop one run, or every active run if omitted
    cici status          # list recent agent runs
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.environ.get("CICIBYTE_API_URL", "http://127.0.0.1:8765")


def _request(method: str, path: str, base_url: str) -> dict:
    req = urllib.request.Request(f"{base_url}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"Could not reach CiciByte AI backend at {base_url}: {exc}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        sys.exit(1)


def cmd_stop(args: argparse.Namespace) -> None:
    if args.run_id:
        result = _request("POST", f"/api/agent/runs/{args.run_id}/stop", args.base_url)
        print(f"Stopped run {args.run_id}: {result}")
    else:
        result = _request("POST", "/api/agent/stop-all", args.base_url)
        print(f"Stopped {result.get('stopped_count', 0)} active run(s).")


def cmd_status(args: argparse.Namespace) -> None:
    result = _request("GET", "/api/agent/runs", args.base_url)
    runs = result.get("runs", [])
    if not runs:
        print("No agent runs yet.")
        return
    for r in runs:
        marker = "●" if r.get("is_active") else "○"
        print(f"{marker} {r['id'][:8]}  {r['status']:<12}  {r['goal'][:60]}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="cici", description="CiciByte AI command-line client")
    parser.add_argument("--base-url", dest="base_url", default=DEFAULT_BASE_URL)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stop_parser = subparsers.add_parser("stop", help="Stop one agent run, or all active runs if no id given")
    stop_parser.add_argument("run_id", nargs="?", default=None)
    stop_parser.set_defaults(func=cmd_stop)

    status_parser = subparsers.add_parser("status", help="List recent agent runs")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
