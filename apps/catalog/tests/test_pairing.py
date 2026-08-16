"""Multiome pairing , the GEX and ATAC halves of one experiment travel together."""

from __future__ import annotations

import pytest

from apps.catalog.models import MULTIOME_ATAC_PREP, MULTIOME_GEX_PREP, Sample
from apps.catalog.services.pairing import with_multiome_partners


def make(fastq_name: str, batch: str, prep: str, load: str) -> Sample:
    return Sample.objects.create(
        fastq_name=fastq_name,
        batch_name_from_vendor=batch,
        organism_common_name="mouse",
        library_prep_method_name=prep,
        load_name=load,
    )


@pytest.fixture
def pair(db):
    gex = make("NW-MX32013-2", "MTX-32013", MULTIOME_GEX_PREP, "3492_A01")
    atac = make("NW-AT36013-2", "ATX-36013", MULTIOME_ATAC_PREP, "3492_A01")
    return gex, atac


@pytest.mark.django_db
def test_selecting_the_gex_half_pulls_in_the_atac_half(pair):
    gex, atac = pair

    samples, added = with_multiome_partners([gex])

    assert {s.fastq_name for s in samples} == {gex.fastq_name, atac.fastq_name}
    assert [s.fastq_name for s in added] == [atac.fastq_name]


@pytest.mark.django_db
def test_it_works_in_the_other_direction(pair):
    gex, atac = pair

    samples, added = with_multiome_partners([atac])

    assert {s.fastq_name for s in samples} == {gex.fastq_name, atac.fastq_name}
    assert [s.fastq_name for s in added] == [gex.fastq_name]


@pytest.mark.django_db
def test_selecting_both_adds_nothing(pair):
    gex, atac = pair

    samples, added = with_multiome_partners([gex, atac])

    assert len(samples) == 2
    assert added == []


@pytest.mark.django_db
def test_a_non_multiome_sample_has_no_partner(db):
    plain = make("PLAIN-1", "10X120", "10xV4", "3492_A01")

    samples, added = with_multiome_partners([plain])

    assert [s.fastq_name for s in samples] == ["PLAIN-1"]
    assert added == []


@pytest.mark.django_db
def test_a_sample_sharing_a_load_name_is_not_dragged_in(pair):
    """load_name is not unique on its own, so the prep has to match too.

    262 load_names in the real mirror are shared by more than one sample; matching on
    load_name alone would sweep unrelated samples into someone's submission.
    """
    gex, _ = pair
    make("UNRELATED-1", "10X120", "10xV4", "3492_A01")

    samples, added = with_multiome_partners([gex])

    assert "UNRELATED-1" not in {s.fastq_name for s in samples}


@pytest.mark.django_db
def test_a_half_with_no_partner_is_left_alone(db):
    """The ATAC side may not have synced yet; that is not an error here."""
    lonely = make("NW-MX99999-1", "MTX-99999", MULTIOME_GEX_PREP, "9999_Z01")

    samples, added = with_multiome_partners([lonely])

    assert [s.fastq_name for s in samples] == ["NW-MX99999-1"]
    assert added == []


@pytest.mark.django_db
def test_partners_are_found_in_one_query(pair, django_assert_num_queries):
    """One query for the whole selection, not one per sample."""
    gex, _ = pair
    make("NW-MX32013-3", "MTX-32013", MULTIOME_GEX_PREP, "3492_B01")
    make("NW-AT36013-3", "ATX-36013", MULTIOME_ATAC_PREP, "3492_B01")
    selection = list(Sample.objects.filter(library_prep_method_name=MULTIOME_GEX_PREP))

    with django_assert_num_queries(2):  # the candidate lookup + its prefetch
        with_multiome_partners(selection)
