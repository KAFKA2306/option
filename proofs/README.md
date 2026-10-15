# Lean 4 futures semantics

The Lean proofs establish that the six supported futures contract types are
partitioned into mutually exclusive perpetual and delivery classes, and that
delivery-basis annualization is permitted **only** for a delivery instrument
with strictly positive time to maturity.

The executable Lean matrix is cross-checked against the production
`calculate_scenario` function for all six labels. The bridge checks
perpetual fields, simple 30-day delivery annualization, and rejection of
delivery at the observation timestamp.

This does **not** prove IEEE-754 arithmetic, actual exchange metadata,
volatility estimation, the browser/Pyodide integration, or data provenance.
Keep the existing contract and browser checks.

```sh
cd proofs && lake build && cd ..
python scripts/check_lean_scenario_bridge.py
```
