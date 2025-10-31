"""Resolve mapping configuration defaults for order items."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from db.models import (
    CompanyDocMappingDefault,
    MappingTemplate,
    OrderItemType,
)
from utils.mapping_config import (
    MappingItemType,
    ResolvedMappingConfig,
    merge_mapping_configs,
    normalise_mapping_config,
)


class MappingConfigResolver:
    """Determine effective mapping configuration for an order item."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_for_item(
        self,
        *,
        company_id: int,
        doc_type_id: int,
        item_type: OrderItemType,
        current_config: Optional[dict],
    ) -> Optional[ResolvedMappingConfig]:
        """Resolve defaults and return merged & validated mapping config."""

        mapping_item_type = MappingItemType(item_type.value)

        default_record = (
            self.db.query(CompanyDocMappingDefault)
            .filter(
                CompanyDocMappingDefault.company_id == company_id,
                CompanyDocMappingDefault.doc_type_id == doc_type_id,
                CompanyDocMappingDefault.item_type == item_type,
            )
            .first()
        )

        template_config = None
        applied_template_id = None
        source = "inheritance"

        if default_record:
            if default_record.template:
                template_config = default_record.template.config or {}
                applied_template_id = default_record.template.template_id
                source = "template-default"
            if default_record.config_override:
                template_config = merge_mapping_configs(
                    template_config, default_record.config_override
                )
                source = f"{source}+override" if template_config else "override"
        else:
            # No explicit default record; fall back to best matching template
            template = self._resolve_template(
                company_id=company_id,
                doc_type_id=doc_type_id,
                item_type=item_type,
            )
            if template:
                template_config = template.config or {}
                applied_template_id = template.template_id
                source = "template"

        if template_config is None and not current_config:
            return None

        merged = merge_mapping_configs(template_config, current_config)
        normalised = normalise_mapping_config(mapping_item_type, merged)

        return ResolvedMappingConfig(
            config=normalised,
            template_id=applied_template_id,
            source=source,
        )

    def _resolve_template(
        self,
        *,
        company_id: int,
        doc_type_id: int,
        item_type: OrderItemType,
    ) -> Optional[MappingTemplate]:
        """Find the most specific template respecting priority and scope."""

        templates = (
            self.db.query(MappingTemplate)
            .filter(MappingTemplate.item_type == item_type)
            .order_by(MappingTemplate.priority.asc(), MappingTemplate.template_id.asc())
            .all()
        )

        best_match: Optional[MappingTemplate] = None
        best_score = -1

        for template in templates:
            score = 0
            if template.company_id is None or template.company_id == company_id:
                if template.company_id == company_id:
                    score += 2
                else:
                    score += 1
            else:
                continue

            if template.doc_type_id is None or template.doc_type_id == doc_type_id:
                if template.doc_type_id == doc_type_id:
                    score += 2
                else:
                    score += 1
            else:
                continue

            if score > best_score:
                best_score = score
                best_match = template

        return best_match
