"""Compare contract-type semantics produced by Lean with actual Python scenarios."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scenario_core import calculate_scenario  # noqa: E402

SNAPSHOT = json.loads((ROOT / "scenario" / "snapshot.json").read_text(encoding="utf-8"))
DELIVERY_TIME = "2026-08-31T16:00:00+00:00"


def main() -> None:
    run = subprocess.run(
        ["lake", "env", "lean", "--run", "ScenarioCases.lean"],
        cwd=ROOT / "proofs",
        check=True,
        capture_output=True,
        text=True,
    )
    rows = run.stdout.strip().splitlines()
    if len(rows) != 6:
        raise AssertionError(f"Expected six Lean contract rows; got {rows!r}")
    names = set()
    for row in rows:
        contract, perpetual_bit, positive_bit, zero_bit = row.split(",")
        if contract in names or (perpetual_bit, positive_bit, zero_bit) not in {
            ("1", "0", "0"), ("0", "1", "0")
        }:
            raise AssertionError(f"Invalid Lean classification row: {row!r}")
        names.add(contract)
        overrides = {"contract_type": contract, "delivery_time": DELIVERY_TIME}
        result = calculate_scenario(SNAPSHOT, overrides)
        is_perpetual = result["annualization_method"] == "not_applicable_perpetual"
        if is_perpetual != (perpetual_bit == "1"):
            raise AssertionError(f"Python/Lean perpetual classification divergence: {contract}")
        if (result["annualized_basis"] is not None) != (positive_bit == "1"):
            raise AssertionError(f"Python/Lean delivery annualization divergence: {contract}")
        if is_perpetual:
            assert result["days_to_maturity"] is None
        else:
            assert result["days_to_maturity"] == 30.0
            assert result["annualization_method"] == "simple_actual_dte_365"
            assert result["perpetual_premium_pct"] is None
            try:
                calculate_scenario(SNAPSHOT, {
                    "contract_type": contract,
                    "delivery_time": SNAPSHOT["observation_time"],
                })
            except ValueError as exc:
                if "at or after contract delivery" not in str(exc):
                    raise AssertionError(f"Unexpected maturity rejection: {contract}") from exc
            else:
                raise AssertionError(f"Delivery at observation was accepted: {contract}")
    print("PASS: Lean/Python classification, 30-day annualization and zero-day rejection across six types")


if __name__ == "__main__":
    main()
