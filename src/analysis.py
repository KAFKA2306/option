import os
import numpy as np
import pandas as pd
from utils import save_data, load_data # align_timestamps is not needed anymore
from config import ANALYSIS_OUTPUT_DIR
# Import the advanced analyzer
from advanced_analysis import BitcoinBasisAnalyzer

def run_advanced_analysis(spot_df, futures_df, interval):
    """Runs the advanced basis analysis using BitcoinBasisAnalyzer."""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')

    if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
        print("Error: Input DataFrames for analysis are invalid.")
        return None, None

    print(f"Running advanced analysis for interval: {interval_str}...")
    try:
        # Initialize the analyzer (calculates basic basis internally)
        analyzer = BitcoinBasisAnalyzer(spot_df, futures_df)

        # Calculate additional metrics
        print("Calculating advanced metrics...")
        analyzer.calculate_annualized_basis() # Use default days_to_maturity=30
        analyzer.calculate_basis_zscore() # Use default window=30
        analyzer.calculate_basis_momentum() # Use default window=14
        analyzer.calculate_volatility_adjusted_basis() # Use default vol_window=30
        analyzer.detect_market_regime() # Use default n_states=3
        # Optional: Calculate signals and position sizing if needed later
        # analyzer.generate_trading_signals()
        # analyzer.calculate_dynamic_position_sizing()

        # Get the resulting DataFrame
        analysis_df = analyzer.basis_df

        if analysis_df is None or analysis_df.empty:
            print("Advanced analysis resulted in an empty DataFrame.")
            return None, None

        # Calculate statistics from the resulting DataFrame
        # Select only numeric columns for describe()
        numeric_cols = analysis_df.select_dtypes(include='number').columns.tolist()
        if not numeric_cols:
             print("Warning: No numeric columns found for statistics calculation.")
             stats_df = pd.DataFrame() # Return empty DataFrame
        else:
             stats_df = analysis_df[numeric_cols].describe().round(5)

        # Save the results
        analysis_filename = f"advanced_basis_data_{interval_str}"
        stats_filename = f"advanced_basis_stats_{interval_str}"

        save_data(analysis_df, "analysis", analysis_filename)
        save_data(stats_df, "analysis", stats_filename)

        print(f"Advanced analysis complete. Data saved for {interval_str}.")

        # Generate and save plots after saving data
        print(f"Generating plots for {interval_str}...")
        try:
            # We need the analyzer object which has the plot method
            analyzer.plot_basis_analysis(interval=interval)
        except Exception as plot_e:
            print(f"Error generating plots for {interval_str}: {plot_e}")

        return stats_df, analysis_df

    except Exception as e:
        print(f"Error during advanced analysis for {interval_str}: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback
        return None, None

# Keep old functions commented out or remove if no longer needed
# def calculate_basis(spot_df, futures_df, interval):
#     ...
#
# def analyze_basis(interval):
#     ...