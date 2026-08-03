import os

import numpy as np
import pandas as pd

from config import ANALYSIS_OUTPUT_DIR
from contract_analysis import ContractAwareBitcoinBasisAnalyzer
from utils import load_data, save_data


def run_advanced_analysis(spot_df, futures_df, interval):
    """Run contract-aware basis analysis for one kline interval."""
    interval_str = (
        interval.replace("m", "min")
        .replace("h", "hour")
        .replace("d", "day")
        .replace("w", "week")
    )

    if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
        print("Error: Input DataFrames for analysis are invalid.")
        return None, None

    print(f"Running contract-aware advanced analysis for interval: {interval_str}...")
    try:
        analyzer = ContractAwareBitcoinBasisAnalyzer(
            spot_df,
            futures_df,
            interval=interval,
        )

        print("Calculating contract-aware metrics...")
        analyzer.calculate_annualized_basis()
        analyzer.calculate_basis_zscore()
        analyzer.calculate_basis_momentum()
        analyzer.calculate_volatility_adjusted_basis()
        analyzer.detect_market_regime()

        analysis_df = analyzer.basis_df
        if analysis_df is None or analysis_df.empty:
            print("Advanced analysis resulted in an empty DataFrame.")
            return None, None

        numeric_cols = analysis_df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            print("Warning: No numeric columns found for statistics calculation.")
            stats_df = pd.DataFrame()
        else:
            stats_df = analysis_df[numeric_cols].describe().round(5)

        analysis_filename = f"advanced_basis_data_{interval_str}"
        stats_filename = f"advanced_basis_stats_{interval_str}"
        save_data(analysis_df, "analysis", analysis_filename)
        save_data(stats_df, "analysis", stats_filename)

        print(f"Advanced analysis complete. Data saved for {interval_str}.")
        print(f"Contract type: {analyzer.contract_metadata.contract_type}")
        print(f"Annualization method: {analysis_df['annualization_method'].iloc[-1]}")

        try:
            analyzer.plot_basis_analysis(interval=interval)
        except Exception as plot_error:
            print(f"Error generating plots for {interval_str}: {plot_error}")

        return stats_df, analysis_df
    except Exception as exc:
        print(f"Error during advanced analysis for {interval_str}: {exc}")
        import traceback

        traceback.print_exc()
        return None, None
