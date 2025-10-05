"""Unit tests for the SpecialCsvGenerator."""

from __future__ import annotations

import pandas as pd
import pytest

from utils.expression_engine import ExpressionEngine
from utils.special_csv_generator import SpecialCsvGenerator


@pytest.fixture()
def generator() -> SpecialCsvGenerator:
    return SpecialCsvGenerator(ExpressionEngine())


@pytest.fixture()
def sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "PHONE": "123 456 789",
                "DATE": "2024-01-01",
                "BASE_FEE": 10,
                "DATA_CHARGE": 5,
                "VOICE_CHARGE": 2,
                "ADDRESS": "123 Main St",
                "CITY": "Metropolis",
                "POSTAL_CODE": "90210",
            },
            {
                "PHONE": None,
                "DATE": "2024-02-15",
                "BASE_FEE": 20,
                "DATA_CHARGE": 0,
                "VOICE_CHARGE": 0,
                "ADDRESS": "456 Side Ave",
                "CITY": "Gotham",
                "POSTAL_CODE": "10001",
            },
        ]
    )


@pytest.fixture()
def template_config() -> dict:
    return {
        "template_name": "Telecom Template",
        "version": "2.0",
        "column_order": [
            "Invoice_Number",
            "Invoice_Date",
            "Total_Monthly_Charge",
            "Clean_Phone_Number",
            "Account_Type",
            "Full_Billing_Address",
        ],
        "column_definitions": {
            "Invoice_Number": {
                "type": "source",
                "source_column": "PHONE",
                "default_value": "",
            },
            "Invoice_Date": {
                "type": "source",
                "source_column": "DATE",
                "default_value": "",
            },
            "Total_Monthly_Charge": {
                "type": "computed",
                "expression": "{BASE_FEE} + {DATA_CHARGE} + {VOICE_CHARGE}",
                "default_value": 0,
            },
            "Clean_Phone_Number": {
                "type": "computed",
                "expression": "replace({PHONE}, ' ', '')",
                "default_value": "",
            },
            "Account_Type": {
                "type": "constant",
                "value": "TELECOM",
                "default_value": "TELECOM",
            },
            "Full_Billing_Address": {
                "type": "computed",
                "expression": "concat({ADDRESS}, ', ', {CITY}, ' ', {POSTAL_CODE})",
                "default_value": "",
            },
        },
    }


def test_generate_special_csv_applies_template_rules(
    generator: SpecialCsvGenerator,
    sample_dataframe: pd.DataFrame,
    template_config: dict,
) -> None:
    result = generator.generate_special_csv(sample_dataframe, template_config)

    assert list(result.columns) == template_config["column_order"]

    # Row 0 assertions
    assert result.loc[0, "Invoice_Number"] == "123 456 789"
    assert result.loc[0, "Clean_Phone_Number"] == "123456789"
    assert result.loc[0, "Total_Monthly_Charge"] == 17
    assert result.loc[0, "Account_Type"] == "TELECOM"
    assert (
        result.loc[0, "Full_Billing_Address"]
        == "123 Main St, Metropolis 90210"
    )

    # Row 1 assertions (includes missing PHONE)
    assert result.loc[1, "Invoice_Number"] == ""
    assert result.loc[1, "Clean_Phone_Number"] == ""
    assert result.loc[1, "Total_Monthly_Charge"] == 20


def test_generate_special_csv_requires_all_columns(
    generator: SpecialCsvGenerator,
    sample_dataframe: pd.DataFrame,
    template_config: dict,
) -> None:
    incomplete_df = sample_dataframe.drop(columns=["VOICE_CHARGE"])

    with pytest.raises(ValueError) as exc:
        generator.generate_special_csv(incomplete_df, template_config)

    assert "Missing required columns" in str(exc.value)
