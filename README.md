# Finance Option Project

 ## Overview

 This project analyzes the basis between spot and futures prices of Bitcoin (BTC) using data from the Binance API. It calculates the basis, analyzes the data, and provides statistics.

 ## Dependencies

 *   pandas
 *   python-binance
 *   pyarrow

 ## Usage

 1.  Set the environment variables `BINANCE_API_KEY` and `BINANCE_API_SECRET`.
 2.  Run `src/main.py` to collect and analyze data.

 ## Files

 *   `src/main.py`: Main script to run the analysis.
 *   `src/analysis.py`: Contains functions to calculate and analyze the basis between spot and futures prices.
 *   `src/binance_data.py`: Contains functions to retrieve historical data from the Binance API.
 *   `src/utils.py`: Contains utility functions for saving and loading data.
 *   `src/config.py`: Contains configuration settings for the project.