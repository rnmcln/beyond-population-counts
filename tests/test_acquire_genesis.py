import importlib.util
import json
import sys
from pathlib import Path

import pytest
import requests

SCRIPT = Path(__file__).parents[1] / "scripts" / "acquire_genesis.py"
SPEC = importlib.util.spec_from_file_location("acquire_genesis", SCRIPT)
assert SPEC and SPEC.loader
acquire_genesis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquire_genesis)


def test_add_classifying_selections_builds_numbered_parameters() -> None:
    request: dict[str, str] = {}
    acquire_genesis.add_classifying_selections(
        request,
        ["ICD10C=ICD10-I60,ICD10-I61", "GES=GESM,GESW"],
    )
    assert request == {
        "classifyingvariable1": "ICD10C",
        "classifyingkey1": "ICD10-I60,ICD10-I61",
        "classifyingvariable2": "GES",
        "classifyingkey2": "GESM,GESW",
    }


def test_add_classifying_selections_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="expected VARIABLE"):
        acquire_genesis.add_classifying_selections({}, ["ICD10C"])


def test_decode_response_reports_nested_genesis_status() -> None:
    response = requests.Response()
    response.status_code = 200
    response.headers["content-type"] = "application/json"
    response._content = json.dumps(
        {
            "Status": {
                "Code": 98,
                "Content": "Table too large; use job=true",
                "Type": "Error",
            }
        }
    ).encode()
    with pytest.raises(RuntimeError, match="code 98"):
        acquire_genesis.decode_response(response)


def test_parse_args_supports_explicit_uncompressed_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["acquire_genesis.py", "--table", "23131-0002", "--no-compress"],
    )
    assert acquire_genesis.parse_args().compress is False
