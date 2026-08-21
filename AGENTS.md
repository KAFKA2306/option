# Repository Agent Contract

## Mission

Own Bitcoin derivatives evidence and risk analysis for this repository: spot/futures/perpetual relationships, funding, basis, open interest and option/futures contract observations where supported by current canonical sources. Keep market observations separate from strategies, forecasts and model scenarios.

## Canonical authority

- Prefer exchange/venue official APIs or documentation for contract identity and market fields when available.
- Preserve instrument identity, venue, timestamp/as-of, units/currency, contract semantics, source URL and retrieval/provenance fields required by the owning dataset.
- Do not duplicate Bitcoin network evidence owned by `btc_dashboard` or corporate treasury facts owned by `mstr`; consume versioned artifacts when cross-domain context is required.

## Autonomous execution

1. Inspect current `main`, README, open Issues/PRs, canonical market artifacts, workflows/tests and public outputs.
2. Continue one canonical workline for the same outcome before creating another collector, schema, branch or Issue.
3. Prefer verified derivatives observations, contract-semantic corrections, reproducible basis/funding/OI views, real data-quality blockers, then simplification.
4. Keep observed market data, deterministic derived metrics, assumptions and model outputs explicitly separate.
5. Run the smallest relevant checks and verify reviewed/merged/public state when applicable.
6. Stop at the fixed point; do not add a strategy, signal or forecast solely because data are available.

## Boundaries

- Do not infer missing trades, liquidations, implied prices, funding history or open interest.
- Do not convert venue-specific fields across contracts unless the unit/contract definitions are proven comparable.
- Do not execute orders, trades, transfers, option exercises or account changes.
- Unobserved live data, CI, deployment or trading outcomes remain unverified.

## Completion report

Report verified market evidence/capability Before -> After, canonical artifact/source, Issue/PR/commit/check/public evidence when applicable, duplicate/manual work removed, and the remaining blocker.