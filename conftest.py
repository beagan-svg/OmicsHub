"""Create fixtures shared by every app's tests.

The `config` fixture mirrors the shape of a real uploaded workflow config, trimmed to the
parts a test needs to exercise.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.catalog.models import NOT_COMPLETED, Sample, Stage, StageStatus
from apps.workflows.models import WorkflowConfig

EMAIL = "bicore@alleninstitute.org"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear process-wide cache values between tests.

    Django rolls the database back between tests; nothing rolls the cache back. Two things
live there now: the submission worker's capacity hold and the timestamp of the last
stage-status sweep. Both are read as "has this already happened", so a value left
    by one test silently changes the answer for the next. That is exactly the kind of
    order-dependent failure that only appears when someone runs a subset.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def config() -> dict:
    return {
        "references": {
            "mouse": {"MTX": "mouse_mtx_ref", "RTX": "mouse_rtx_ref"},
            "human": {"all": "human_all_ref"},
            "rat": {"RFX": {"library_preps": {"10xFXv2": "rat_fxv2_ref"}}},
        },
        "probe_sets_by_organism": {
            "mouse": {"10xV4_FX16": "mouse_probe_set"},
            "human": "human_probe_set",
        },
        "chemistry_by_library_prep": {"10xRSeq_Mult": "ARC-v1", "10xV4": "SC3Pv4"},
        "workflows": {
            "MTX": {
                "alignment_command_configs": [
                    {
                        "name": "default",
                        "match": {"library_preps": ["10xMultX_GEX", "10xRSeq_Mult"]},
                        "command": ["ocs", "fastqs", "align", "tenx-arc"],
                        "arguments": [
                            {"flag": "--reference-names", "value": "{reference_name}"},
                            {"flag": "--load-names", "value": "{load_name}"},
                            {"flag": "--notify", "value": "{email}"},
                        ],
                        "spacing": 180,
                    }
                ],
                "post_alignment_command_configs": [
                    {
                        "name": "default",
                        "match": {"library_preps": ["10xMultX_GEX", "10xRSeq_Mult"]},
                        "command": ["ocs", "fastqs", "postalign", "tenx-arc"],
                        "arguments": [
                            {"flag": "--asset-name", "value": "10x_multiome_qc"},
                            {"flag": "--load-names", "value": "{load_name}"},
                        ],
                        "spacing": 60,
                    }
                ],
            },
            "RTX": {
                "alignment_command_configs": [
                    {
                        "name": "standard",
                        "match": {"library_preps": ["10xV4"]},
                        "command": ["ocs", "fastqs", "align", "tenx-rnaseq"],
                        "arguments": [
                            {"flag": "--reference-names", "value": "{reference_name}"},
                            {"flag": "--{input_name_flag}", "value": "{input_name}"},
                            {"flag": "--cellranger-addopts", "value": "--chemistry {chemistry}"},
                        ],
                        "spacing": 180,
                    }
                ],
                "post_alignment_command_configs": [],
            },
        },
        "job_settings": {"limit": 100, "poll_interval_hours": 1},
        "status_mappings": {
            "ingest_complete": ["INGEST_COMPLETE", "COMPLETED", "ARCHIVED"],
            "alignment_complete": ["COMPLETED", "ARCHIVED"],
            "post_alignment_complete": ["COMPLETED", "ARCHIVED"],
        },
    }


@pytest.fixture
def make_sample(db):
    """Create a Sample with the given per-stage OCS statuses.

    A stage left at NOT COMPLETED gets no StageStatus row, which is exactly how a sample
    OCS has never run that stage for looks.
    """

    def _make(
        fastq_name: str = "NY-MX22068-2",
        *,
        batch_name_from_vendor: str = "MTX-22068",
        load_name: str = "LOAD_1",
        library_prep_method_name: str = "10xRSeq_Mult",
        organism_common_name: str = "mouse",
        ingest: str = "INGEST_COMPLETE",
        align: str = NOT_COMPLETED,
        postalign: str = NOT_COMPLETED,
    ) -> Sample:
        sample = Sample.objects.create(
            fastq_name=fastq_name,
            batch_name_from_vendor=batch_name_from_vendor,
            load_name=load_name,
            library_prep_method_name=library_prep_method_name,
            organism_common_name=organism_common_name,
            sample_names=["SAMPLE_1"],
            studies=["StudyA"],
        )
        for stage, status in (
            (Stage.INGEST, ingest),
            (Stage.ALIGN, align),
            (Stage.POST_ALIGN, postalign),
        ):
            if status != NOT_COMPLETED:
                StageStatus.objects.create(
                    sample=sample,
                    stage=stage,
                    status=status,
                    demand_id=f"demand-{stage}",
                )
        return sample

    return _make


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="analyst", email=EMAIL, password="password")


@pytest.fixture
def active_config(config, user):
    """Return the uploaded manifest used for planning submissions."""
    return WorkflowConfig.objects.create(
        name="config.jsonc", raw="{}", data=config, uploaded_by=user, is_active=True
    )


@pytest.fixture
def logged_in(client, user):
    client.force_login(user)
    return client
