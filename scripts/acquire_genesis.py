#!/usr/bin/env python3
"""Retrieve an official GENESIS table file without exposing credentials."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

API_URL = "https://genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
SELECTION_PATTERN = re.compile(r"^([A-Za-z0-9]{1,6})=([^=]+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", required=True, help="Official table code, e.g. 23131-0002")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--format", choices=["ffcsv", "csv", "datencsv", "xlsx"], default="ffcsv")
    parser.add_argument("--language", choices=["de", "en"], default="de")
    parser.add_argument(
        "--compress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Suppress empty GENESIS rows and columns (default: true). Use "
            "--no-compress when explicit structural-zero cells are analytically required."
        ),
    )
    parser.add_argument(
        "--classifying-selection",
        action="append",
        default=[],
        metavar="VARIABLE=KEY[,KEY...]",
        help="Limit one subject dimension; may be supplied up to five times",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/genesis"))
    parser.add_argument(
        "--dry-run", action="store_true", help="Print non-secret request metadata only"
    )
    return parser.parse_args()


def add_classifying_selections(request_data: dict[str, str], selections: list[str]) -> None:
    """Add validated GENESIS subject-variable selections to request parameters."""

    if len(selections) > 5:
        raise ValueError("GENESIS accepts at most five classifying selections")
    for index, selection in enumerate(selections, start=1):
        match = SELECTION_PATTERN.fullmatch(selection.strip())
        if not match:
            raise ValueError(
                f"Invalid classifying selection {selection!r}; expected VARIABLE=KEY[,KEY...]"
            )
        variable, keys = match.groups()
        key_list = keys.split(",")
        if any(not key or len(key) > 15 for key in key_list):
            raise ValueError(f"Invalid GENESIS selection keys in {selection!r}")
        request_data[f"classifyingvariable{index}"] = variable
        request_data[f"classifyingkey{index}"] = keys


def credentials() -> tuple[str, str]:
    token = os.getenv("DESTATIS_GENESIS_TOKEN", "").strip()
    if token:
        return token, ""
    username = os.getenv("DESTATIS_GENESIS_USERNAME", "").strip()
    password = os.getenv("DESTATIS_GENESIS_PASSWORD", "")
    if username and password:
        return username, password
    raise RuntimeError(
        "GENESIS credentials are missing. Set DESTATIS_GENESIS_TOKEN to a free personal "
        "token, or set DESTATIS_GENESIS_USERNAME and DESTATIS_GENESIS_PASSWORD."
    )


def decode_response(response: requests.Response) -> tuple[bytes, str, dict[str, Any] | None]:
    """Decode either a binary response or the API's JSON/base64 envelope."""

    content_type = response.headers.get("content-type", "").lower()
    raw = response.content
    if "json" not in content_type and not raw.lstrip().startswith(b"{"):
        extension = "zip" if raw.startswith(b"PK") else "bin"
        return raw, extension, None

    envelope = response.json()
    status = envelope.get("Status", envelope.get("status", {}))
    code = status.get("Code", status.get("code", envelope.get("Code", 0)))
    if str(code) not in {"0", "None"}:
        message = status.get(
            "Content",
            status.get(
                "content",
                envelope.get("Content", envelope.get("content", "Unknown GENESIS error")),
            ),
        )
        raise RuntimeError(f"GENESIS rejected the request (code {code}): {message}")
    encoded = envelope.get("Object", envelope.get("object"))
    if not encoded:
        raise RuntimeError("GENESIS returned JSON without a downloadable Object payload")
    payload = base64.b64decode(encoded)
    extension = "zip" if payload.startswith(b"PK") else "bin"
    return payload, extension, envelope


def main() -> int:
    args = parse_args()
    request_data: dict[str, str] = {
        "name": args.table,
        "area": "all",
        "compress": str(args.compress).lower(),
        "format": args.format,
        "language": args.language,
    }
    if args.start_year is not None:
        request_data["startyear"] = str(args.start_year)
    if args.end_year is not None:
        request_data["endyear"] = str(args.end_year)
    add_classifying_selections(request_data, args.classifying_selection)

    if args.dry_run:
        print(json.dumps({"url": API_URL, "parameters": request_data}, indent=2))
        return 0

    username, password = credentials()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "username": username,
        "password": password,
    }
    response = requests.post(API_URL, headers=headers, data=request_data, timeout=180)
    response.raise_for_status()
    payload, extension, envelope = decode_response(response)

    retrieved = datetime.now(UTC)
    destination = args.output_dir / args.table
    destination.mkdir(parents=True, exist_ok=True)
    first_year = args.start_year or "first"
    last_year = args.end_year or "latest"
    compression_label = "compressed" if args.compress else "uncompressed"
    stem = f"{retrieved:%Y-%m-%d}_{args.table}_{first_year}-{last_year}_{compression_label}"
    data_path = destination / f"{stem}.{extension}"
    data_path.write_bytes(payload)

    manifest = {
        "source": "Statistisches Bundesamt (Destatis), GENESIS-Online",
        "url": API_URL,
        "table": args.table,
        "parameters": request_data,
        "retrieved_at_utc": retrieved.isoformat(),
        "file": data_path.name,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "api_content": envelope.get("Content") if envelope else None,
        "credentials_recorded": False,
    }
    manifest_path = destination / f"{stem}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(data_path)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (requests.RequestException, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
