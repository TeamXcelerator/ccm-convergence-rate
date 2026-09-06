#!/usr/bin/env python3
"""File-level measurement provenance and scientific verdicts.

Owner-authorized CCM audit changes; AI-generated implementation assistance.
These receipts detect stale or changed files, not a malicious party capable of
rewriting both measurement and receipt. They are not compiler attestations,
managed dependency-closure proofs, or mathematical certificates.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def execution_identity(binary: str, repository: str) -> dict[str, Any]:
    root = Path(repository)
    executable = Path(binary)
    if not executable.is_absolute():
        executable = root / executable
    paths = ["Cargo.toml", "Cargo.lock", "src/main.rs", "scripts/reproduce.py", "scripts/scientific_results.py"]
    return {
        "schema_version": 1,
        "binary_sha256": file_digest(executable),
        "source_file_sha256": {path: file_digest(root / path) for path in paths},
        "scope": "file_identity_not_compiler_or_mathematical_attestation",
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def stamp_measurement(path: str, binary: str, repository: str) -> None:
    target = Path(path)
    report = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("measurement is not an object")
    receipt = {
        "schema_version": 1,
        "measurement_sha256": file_digest(target),
        "execution_identity": execution_identity(binary, repository),
        "reference_dataset": report.get("reference_dataset"),
        "root_observable": "relative_error_to_indexed_zeta_reference",
        "source_manifest_binding": "not_exposed_by_this_application_schema",
    }
    atomic_json(Path(str(target) + ".provenance.json"), receipt)


def verify_measurement_provenance(path: str, binary: str, repository: str) -> None:
    target = Path(path)
    receipt = json.loads(Path(str(target) + ".provenance.json").read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 1:
        raise ValueError("unsupported measurement provenance schema")
    if receipt.get("measurement_sha256") != file_digest(target):
        raise ValueError("measurement content no longer matches its receipt")
    if receipt.get("execution_identity") != execution_identity(binary, repository):
        raise ValueError("measurement binary or source/lockfile identity changed")
    report = json.loads(target.read_text(encoding="utf-8"))
    if receipt.get("reference_dataset") != report.get("reference_dataset"):
        raise ValueError("reference-dataset identity differs from measurement receipt")


def qualified_digits(root: dict[str, Any]) -> float | None:
    """Only finite, converged measurements enter fits. Others stay retained."""
    digits = root.get("matching_digits_f64")
    if root.get("status") != "converged" or isinstance(digits, bool):
        return None
    if not isinstance(digits, (int, float)) or not math.isfinite(digits):
        return None
    return float(digits)


def scientific_verdict(verdicts: list[str], *, skipped: bool, execution_succeeded: bool) -> str:
    if not execution_succeeded:
        return "EXECUTION_FAILED"
    if not verdicts:
        return "SKIPPED" if skipped else "INCONCLUSIVE"
    if "INCONCLUSIVE" in verdicts:
        return "INCONCLUSIVE"
    if "FAIL" in verdicts:
        return "FAIL"
    if all(value == "EXPLORATORY" for value in verdicts):
        return "EXPLORATORY"
    if all(value == "PASS" for value in verdicts):
        return "PASS"
    return "INCONCLUSIVE"


def validate_root_window(report: dict[str, Any], first: int, count: int) -> None:
    roots = report.get("roots")
    if not isinstance(roots, list) or len(roots) != count:
        raise ValueError("measurement does not retain the complete requested root window")
    if report.get("zero_count_returned") != count:
        raise ValueError("returned root count differs from retained/requested count")
    if [root.get("reference_index") for root in roots] != list(range(first, first + count)):
        raise ValueError("root ordinals are missing, duplicated, or out of order")
    if any(root.get("status") not in {"converged", "stagnated", "approximate", "failed"} for root in roots):
        raise ValueError("unrecognized root numerical status")
