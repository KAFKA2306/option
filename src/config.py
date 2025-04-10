# src/config.py
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
RAW_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "raw")
PROCESSED_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "processed")
ANALYSIS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "analysis")

def create_output_directories():
    os.makedirs(RAW_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSED_OUTPUT_DIR, exist_ok=True)
    os.makedirs(ANALYSIS_OUTPUT_DIR, exist_ok=True)
