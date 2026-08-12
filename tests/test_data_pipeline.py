import sys
from pathlib import Path

import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from data_layer import (
    BAND_FUEL_COST,
    SOLAR_INSTALLMENT,
    assign_band,
    load_and_process_csv,
    simulated_pitch,
)


@pytest.fixture(scope="module")
def df():
    return load_and_process_csv()


def test_rows_exact(df):
    assert len(df) == 50


def test_required_columns(df):
    for col in ["id", "name", "address", "phone", "category", "description", "lat", "lng"]:
        assert col in df.columns


def test_unique_ids(df):
    assert df["id"].is_unique


def test_unique_names(df):
    assert df["name"].str.lower().is_unique


def test_engineered_columns(df):
    assert "assigned_band" in df.columns
    assert "est_monthly_fuel" in df.columns
    assert "generated_pitch" in df.columns


def test_fuel_costs_exact(df):
    for band, cost in BAND_FUEL_COST.items():
        subset = df[df["assigned_band"] == band]
        if len(subset):
            assert (subset["est_monthly_fuel"] == cost).all()


def test_coords_in_kaduna(df):
    assert df["lat"].between(10.0, 11.0).all()
    assert df["lng"].between(7.0, 8.0).all()


def test_no_missing_names(df):
    assert df["name"].notna().all()
    assert df["address"].notna().all()


def test_band_assignment_deterministic(df):
    sample = df.iloc[0]
    row = {"category": sample["category"], "description": sample["description"]}
    assert assign_band(row) == sample["assigned_band"]


def test_simulated_pitch_includes_brand():
    row = pd.Series(
        {
            "name": "Test Pharmacy",
            "phone": "2348000000000",
            "category": "Pharmacy",
            "address": "Kaduna",
            "est_monthly_fuel": 200000,
        }
    )
    pitch = simulated_pitch(row)
    assert "Sol Searching" in pitch
    assert len(pitch) <= 160


def test_simulated_email_pitch_no_phone():
    row = pd.Series(
        {
            "name": "Test Clinic",
            "phone": None,
            "category": "Clinic",
            "address": "Barnawa, Kaduna",
            "est_monthly_fuel": 50000,
        }
    )
    pitch = simulated_pitch(row)
    assert "Sol Searching" in pitch
    assert "Dear" in pitch


def test_solar_installment_constant():
    assert SOLAR_INSTALLMENT == 85000
