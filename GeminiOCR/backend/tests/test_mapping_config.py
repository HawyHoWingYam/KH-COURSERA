from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.mapping_config import (
    MappingItemType,
    normalise_mapping_config,
    normalise_mapping_override,
)


def test_normalise_mapping_override_allows_partial_override():
    template = normalise_mapping_config(
        MappingItemType.SINGLE_SOURCE,
        {
            "master_csv_path": "/drive/master.csv",
            "external_join_keys": ["order_id"],
            "column_aliases": {"Invoice": "invoice_id"},
        },
    )

    override = {"column_aliases": {"Invoice": "invoice_number"}}

    result = normalise_mapping_override(
        MappingItemType.SINGLE_SOURCE,
        override,
        template_config=template,
    )

    assert result == {"column_aliases": {"Invoice": "invoice_number"}}


def test_normalise_mapping_override_can_remove_fields():
    template = normalise_mapping_config(
        MappingItemType.SINGLE_SOURCE,
        {
            "master_csv_path": "/drive/master.csv",
            "external_join_keys": ["order_id"],
            "notes": "Existing note",
        },
    )

    override = {"notes": None}

    result = normalise_mapping_override(
        MappingItemType.SINGLE_SOURCE,
        override,
        template_config=template,
    )

    assert result == {"notes": None}


def test_normalise_mapping_override_requires_complete_payload_without_template():
    with pytest.raises(ValueError):
        normalise_mapping_override(
            MappingItemType.SINGLE_SOURCE,
            {"column_aliases": {"Invoice": "invoice_id"}},
            template_config=None,
        )
