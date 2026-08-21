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
5. Run the smallest relevant checks and verify the exact reviewed revision before merge.
6. Stop at the fixed point; do not add a strategy, signal or forecast solely because data are available.

## Merge and release are separate

### PR merge conditions

A PR may merge when the repository-local derivatives contract is correct on the exact head revision: instrument/unit semantics are preserved, deterministic transforms/tests pass, generated artifacts are reproducible where affected, and no unresolved review or correctness blocker remains.

Fresh exchange API data, future funding/OI observations, public deployment, or post-merge market availability is **not** a merge condition unless the PR specifically changes the release/live-collection mechanism and that mechanism must be validated before merge.

### Product/data release conditions

Release is a separate post-merge decision. Treat derivatives data/views as released only after the merged `main` revision is read back and the release surfaces in scope are actually verified, including fresh live observations where required, published artifacts/API or UI, deployment identity, and rollback/rebuild path where applicable.

A merged PR does not prove live market release. A live-source or deployment blocker may block release without invalidating a correctly merged repository change. Report merge and release independently.

## Boundaries

- Do not infer missing trades, liquidations, implied prices, funding history or open interest.
- Do not convert venue-specific fields across contracts unless the unit/contract definitions are proven comparable.
- Do not execute orders, trades, transfers, option exercises or account changes.
- Unobserved live data, CI, deployment or trading outcomes remain unverified.

## Completion report

Report verified market evidence/capability Before -> After, canonical artifact/source, Issue/PR/commit/check evidence, then report `merged` and `released` separately with direct evidence for each. Include duplicate/manual work removed and the remaining blocker.