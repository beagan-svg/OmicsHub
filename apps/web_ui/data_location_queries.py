"""Build the Data Locations rows from mirrored stage and GFS records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.ocs_integration import dynamodb
from apps.sample_catalog.models import Sample, Stage
from apps.web_ui.columns import LOCATION_COLUMNS, LOCATION_STAGES


def stage_rows(samples: Iterable[Sample]) -> list[dict[str, Any]]:
    """Build one row for each fastq sample and tracked OCS stage."""
    samples = list(samples)
    file_store_ids = {
        record.file_store_id
        for sample in samples
        for record in sample.stage_statuses.all()
        if record.file_store_id
    }
    file_stores = dynamodb.get_file_stores(sorted(file_store_ids))

    rows = []
    for sample in samples:
        statuses = {record.stage: record for record in sample.stage_statuses.all()}
        for stage in LOCATION_STAGES:
            record = statuses.get(stage.value)
            file_store_id = record.file_store_id if record else ""
            file_store = file_stores.get(file_store_id, {})
            rows.append(
                {
                    "sample_id": sample.pk,
                    "show_selector": stage == Stage.INGEST,
                    "fastq_name": sample.fastq_name,
                    "studies": sample.studies,
                    "load_name": sample.load_name,
                    "batch_name_from_vendor": sample.batch_name_from_vendor,
                    "modality": sample.modality,
                    "organism_common_name": sample.organism_common_name,
                    "library_prep_method_name": sample.library_prep_method_name,
                    "column_values": {
                        column.key: getattr(sample, column.key)
                        for column in LOCATION_COLUMNS
                        if column.key not in {"stage", "status"}
                    },
                    "stage": stage,
                    "status": record.status if record else "NOT COMPLETED",
                    "file_store_id": file_store_id,
                    "s3_uri": str(file_store.get("s3_uri") or ""),
                }
            )
    return rows
