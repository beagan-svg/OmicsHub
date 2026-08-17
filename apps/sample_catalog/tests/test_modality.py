"""Batch prefix and modality, which the database computes rather than the sync.

These run against real inserts on purpose: the whole point of a generated column is that
Postgres derives the value, so a test that stubbed it would be testing nothing.
"""

from __future__ import annotations

import pytest

from apps.sample_catalog.models import (
    MULTIOME_ATAC_PREP,
    MULTIOME_GEX_PREP,
    BatchPrefix,
    Modality,
    Sample,
)


def make(fastq_name: str, batch: str, prep: str = "10xV4", load: str = "") -> Sample:
    return Sample.objects.create(
        fastq_name=fastq_name,
        batch_name_from_vendor=batch,
        organism_common_name="mouse",
        library_prep_method_name=prep,
        load_name=load,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("batch", "prefix", "modality"),
    [
        ("MTX-32013", BatchPrefix.MTX, Modality.MTX),
        ("RFX-1001", BatchPrefix.RFX, Modality.RFX),
        ("RTX-34056", BatchPrefix.RTX, Modality.RTX),
        # The ATAC half of a multiome pair: its own family, but it runs as MTX.
        ("ATX-36013", BatchPrefix.ATX, Modality.MTX),
        # The shape most of the mirror actually has. There is no recognised prefix.
        ("10X120", BatchPrefix.RTX, Modality.RTX),
        ("10X172-4", BatchPrefix.RTX, Modality.RTX),
    ],
)
def test_prefix_and_modality_are_derived(batch, prefix, modality):
    sample = make(f"fq-{batch}", batch)
    sample.refresh_from_db()

    assert sample.batch_prefix == prefix
    assert sample.modality == modality


@pytest.mark.django_db
def test_no_sample_is_ever_unknown():
    """The bug this replaced: an unrecognised prefix rendered as an empty Workflow cell."""
    for i, batch in enumerate(["10X120", "ZZZ-1", "", "weird name", "MTX", "atx-1"]):
        make(f"fq-{i}", batch)

    assert Sample.objects.filter(modality="").count() == 0
    assert Sample.objects.filter(modality__isnull=True).count() == 0
    assert set(Sample.objects.values_list("modality", flat=True)) <= set(Modality.values)


@pytest.mark.django_db
def test_lowercase_prefix_falls_through_to_rtx():
    """Documents a real limit: the derivation is case-sensitive.

    Postgres will not accept `upper()` inside a generated column , it is collation
    dependent, so the expression is not immutable. Every vendor batch name OCS has ever
    sent is uppercase, so this is a recorded assumption rather than a live problem; if a
    lowercase prefix ever appears it classifies as RTX instead of failing loudly.
    """
    sample = make("fq-lower", "mtx-32013")
    sample.refresh_from_db()

    assert sample.batch_prefix == BatchPrefix.RTX


@pytest.mark.django_db
def test_modality_follows_a_renamed_batch():
    """A generated column cannot go stale, which is the reason for using one."""
    sample = make("fq-rename", "10X120")
    sample.refresh_from_db()
    assert sample.modality == Modality.RTX

    sample.batch_name_from_vendor = "MTX-32013"
    sample.save(update_fields=["batch_name_from_vendor"])
    sample.refresh_from_db()

    assert sample.modality == Modality.MTX
    assert sample.batch_prefix == BatchPrefix.MTX


@pytest.mark.django_db
def test_modality_is_filterable_in_sql():
    """The reason this is a column and not a Python property."""
    make("fq-a", "MTX-1")
    make("fq-b", "ATX-1")
    make("fq-c", "10X999")

    assert Sample.objects.filter(modality=Modality.MTX).count() == 2
    assert Sample.objects.filter(batch_prefix=BatchPrefix.ATX).count() == 1
    assert Sample.objects.filter(batch_prefix=BatchPrefix.MTX).count() == 1


@pytest.mark.django_db
def test_multiome_partner_prep():
    gex = make("fq-gex", "MTX-32013", prep=MULTIOME_GEX_PREP, load="3492_A01")
    atac = make("fq-atac", "ATX-36013", prep=MULTIOME_ATAC_PREP, load="3492_A01")
    plain = make("fq-plain", "10X120", prep="10xV4", load="3492_A01")

    assert gex.multiome_partner_prep == MULTIOME_ATAC_PREP
    assert atac.multiome_partner_prep == MULTIOME_GEX_PREP
    assert plain.multiome_partner_prep is None


@pytest.mark.django_db
def test_prefix_mapping_matches_the_generated_columns():
    """Pins PREFIX_MODALITY to the SQL, which spells the same rule out separately.

    The generated columns cannot be built from the dict , altering a GeneratedField means
    dropping and re-adding the column , so the two are kept in step by running every entry
    through the database.
    """
    from apps.sample_catalog.models import FALLBACK_MODALITY, FALLBACK_PREFIX, PREFIX_MODALITY

    for prefix, expected_modality in PREFIX_MODALITY.items():
        sample = make(f"fq-{prefix}", f"{prefix}-1")
        sample.refresh_from_db()
        assert sample.batch_prefix == prefix
        assert sample.modality == expected_modality

    fallback = make("fq-fallback", "10X999")
    fallback.refresh_from_db()
    assert fallback.batch_prefix == FALLBACK_PREFIX
    assert fallback.modality == FALLBACK_MODALITY


def test_sync_scope_includes_atx_whenever_mtx_is_configured():
    """The bug this guards: scoping the sync by workflow name never fetches ATX, and the
    out-of-scope prune then deletes any ATX samples already mirrored."""
    from apps.sample_catalog.models import prefixes_for_workflows

    assert prefixes_for_workflows({"MTX", "RFX", "RTX"}) == {"MTX", "ATX", "RFX", "RTX"}
    # ATX rides on MTX, so it is only in scope when MTX is.
    assert prefixes_for_workflows({"MTX"}) == {"MTX", "ATX"}
    assert prefixes_for_workflows({"RTX"}) == {"RTX"}
    assert prefixes_for_workflows({"RFX"}) == {"RFX"}
