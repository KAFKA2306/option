# Finance Option Project

## Overview

This project analyzes the basis between spot and futures prices of Bitcoin (BTC) using data from the Binance API. It calculates the basis, analyzes the data, generates plots, and produces an HTML analysis report.

**View the latest analysis report:** [https://KAFKA2306.github.io/option/](https://KAFKA2306.github.io/option/)

## Dependencies

*   pandas
*   python-binance
*   pyarrow
*   matplotlib
*   jinja2

Install dependencies using:
```bash
pip install -r requirements.txt
```

## Usage

1.  Set the environment variables `BINANCE_API_KEY` and `BINANCE_API_SECRET`.
2.  Run `python src/main.py` to collect data, perform analysis, generate plots, and create the `index.html` report in the project root directory.

## Files

*   `src/main.py`: Main script to run the entire pipeline.
*   `src/data_loader.py`: Fetches and saves spot and futures data from Binance.
*   `src/analysis.py`: Calculates basis, performs statistical analysis, and calculates moving averages.
*   `src/plot.py`: Generates various plots based on the analysis data.
*   `src/reportgenerator.py`: Generates the final HTML analysis report (`index.html`).
*   `src/utils.py`: Utility functions for saving and loading data (Parquet format).
*   `src/config.py`: Configuration settings (e.g., directory paths).
*   `index.html`: The generated HTML analysis report (in the project root).
*   `output/`: Directory containing generated data and plots (ignored by Git by default, except for plots which are tracked).