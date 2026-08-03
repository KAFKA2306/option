# Finance Option Project

## Overview

This project analyzes the relationship between Bitcoin spot and Binance USDⓈ-M futures prices. Contract metadata is part of the calculation boundary: perpetual premium, funding, and delivery-futures basis are reported as different metrics.

**Latest report:** https://KAFKA2306.github.io/option/

## Contract-aware calculation policy

The collector reads Binance futures exchange information and preserves:

```text
symbol
contractType
status
onboardDate
deliveryDate
underlyingType
```

Unknown or missing contract types fail closed.

### Perpetual contracts

For `PERPETUAL` contracts, the report outputs:

```text
perpetual_premium_pct = (perpetual_price / spot_price - 1) × 100
funding_rate
funding_time
funding_interval_hours
funding_annualized_simple_pct
```

A perpetual contract has no fixed maturity, so `days_to_maturity` and `annualized_basis` remain missing. The system does not assume a fictitious 30-day maturity.

Funding annualization is a separately named simple projection based on the interval observed between historical funding timestamps. It is not presented as delivery-futures basis.

### Delivery contracts

For supported delivery contract types, each observation uses its actual remaining time:

```text
DTE(t) = delivery_datetime - observation_datetime

simple_annualized_basis(t)
  = (futures_price(t) / spot_price(t) - 1)
  × 365 / DTE(t)
  × 100
```

Observations at or after delivery are rejected. The output records `delivery_datetime`, `days_to_maturity`, `annualization_day_count`, and `annualization_method`.

### Volatility annualization

Volatility uses the actual kline interval and a 365-day crypto trading year. Examples:

```text
1m -> 525,600 periods/year
1h -> 8,760 periods/year
1d -> 365 periods/year
1w -> 365 / 7 periods/year
1M -> 12 periods/year
```

The previous fixed `sqrt(252)` assumption is not applied to minute, hourly, weekly, or monthly crypto data.

## Dependencies

- pandas
- numpy
- python-binance
- pyarrow / fastparquet
- matplotlib
- scikit-learn
- seaborn
- jinja2

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Set `BINANCE_API_KEY` and `BINANCE_API_SECRET` when required by your environment.
2. Run the pipeline:

```bash
python src/main.py
```

Public market-data endpoints are used for contract metadata, klines, and funding history. The generated analysis contains the source symbol and contract type so the reported metric can be audited.

## Validation

```bash
python -m unittest discover -s tests -v
```

Regression tests cover:

- perpetual premium without fictitious annualized basis
- delivery contracts with 5-day, 30-day, and 90-day DTE
- rejection at or after delivery
- funding interval inference
- interval-specific volatility annualization
- fail-closed handling of unknown contract types

## Files

- `src/main.py`: pipeline entry point
- `src/data_loader.py`: spot/futures data, contract metadata, and funding history
- `src/analysis.py`: analysis orchestration
- `src/contract_analysis.py`: contract-aware basis and annualization boundary
- `src/advanced_analysis.py`: common statistical analysis and plotting
- `tests/test_contract_analysis.py`: financial calculation regression tests
- `index.html`: generated report
- `output/`: generated data and plots
