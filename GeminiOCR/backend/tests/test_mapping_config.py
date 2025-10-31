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


def test_multisource_requires_rule_or_default_internal_key():
    # No internal_join_key and no attachment_sources -> invalid
    with pytest.raises(ValueError):
        normalise_mapping_config(
            MappingItemType.MULTI_SOURCE,
            {
                "master_csv_path": "/drive/master.csv",
                "external_join_keys": ["order_id"],
                # missing internal_join_key, and empty sources
                "attachment_sources": [],
            },
        )


def test_multisource_ok_with_attachment_rules_only():
    result = normalise_mapping_config(
        MappingItemType.MULTI_SOURCE,
        {
            "master_csv_path": "/drive/master.csv",
            "external_join_keys": ["order_id"],
            # no default internal key, but has per-attachment join key
            "attachment_sources": [
                {"kind": "onedrive", "path": "/attachments", "filename_contains": "INV-", "join_key": "invoice_no"}
            ],
        },
    )
    assert result["item_type"] == "multi_source"
    assert not result.get("internal_join_key")
    assert len(result["attachment_sources"]) == 1
    assert result["attachment_sources"][0]["join_key"] == "invoice_no"


def test_multisource_ok_with_default_internal_no_rules():
    result = normalise_mapping_config(
        MappingItemType.MULTI_SOURCE,
        {
            "master_csv_path": "/drive/master.csv",
            "external_join_keys": ["order_id"],
            "internal_join_key": "invoice_no",
            "attachment_sources": [],
        },
    )
    assert result["internal_join_key"] == "invoice_no"
    assert result["attachment_sources"] == []
