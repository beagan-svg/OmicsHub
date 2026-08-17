"""A multiome pair aligns as one job, so both halves must have ingested first."""

from __future__ import annotations

import pytest

from apps.sample_catalog.models import (
    MULTIOME_ATAC_PREP,
    MULTIOME_GEX_PREP,
    NOT_COMPLETED,
    Sample,
    Stage,
    StageStatus,
)
from apps.submission_queue.services import planning

pytestmark = pytest.mark.django_db

INGEST_COMPLETE = "INGEST_COMPLETE"


def make(fastq_name, batch, prep, load="3492_A01", ingest=INGEST_COMPLETE, align=NOT_COMPLETED):
    sample = Sample.objects.create(
        fastq_name=fastq_name,
        batch_name_from_vendor=batch,
        organism_common_name="mouse",
        library_prep_method_name=prep,
        load_name=load,
        sample_names=["SAMPLE_1"],
    )
    for stage, value in ((Stage.INGEST, ingest), (Stage.ALIGN, align)):
        if value != NOT_COMPLETED:
            StageStatus.objects.create(sample=sample, stage=stage, status=value, demand_id="d")
    return sample


def plan_for(samples, config, **kwargs):
    reloaded = Sample.objects.filter(pk__in=[s.pk for s in samples]).prefetch_related("stage_statuses")
    return planning.build_plan(samples=list(reloaded), config=config, email="e@x.org", **kwargs)


class TestPairIngestGate:
    def test_both_halves_ingested_lets_the_pair_align(self, config):
        """One alignment job per pair, submitted from the GEX half.

        `tenx-arc` is given `--load-names`, and OCS pulls the ATAC half in from that, so
        the pair runs as a single job. The ATAC half is deliberately absent from every MTX
        alignment command config , it is a prerequisite, not a submission.

        So it is neither an entry nor a skip. It used to be reported as
        `library_prep_unconfigured`, which is true of the config and misleading about the
        submission: it read as a sample dropped for a configuration fault, when in fact it
        is going in, through its pair.
        """
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP)
        atac = make("ATAC-1", "ATX-36013", MULTIOME_ATAC_PREP)

        plan = plan_for([gex, atac], config)

        assert [(e.sample.fastq_name, e.stage) for e in plan.entries] == [("GEX-1", Stage.ALIGN)]
        assert [s.fastq_name for s in plan.covered_by_pair] == ["ATAC-1"]
        assert not [skip for skip in plan.skipped if skip.sample.fastq_name == "ATAC-1"]

    def test_a_half_waits_when_its_partner_has_not_ingested(self, config):
        """The GEX half is ready on its own, but arc has nothing to align against."""
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP)
        atac = make("ATAC-1", "ATX-36013", MULTIOME_ATAC_PREP, ingest=NOT_COMPLETED)

        plan = plan_for([gex, atac], config)

        assert not plan.entries
        blocked = {skip.sample.fastq_name: skip for skip in plan.skipped}
        assert blocked["GEX-1"].reason == planning.SkipReason.PAIR_INGEST_INCOMPLETE
        assert "ATAC-1" in blocked["GEX-1"].detail
        # The ATAC half is held back by its own ingest, which is a different reason.
        assert blocked["ATAC-1"].reason == planning.SkipReason.INGEST_INCOMPLETE

    def test_a_half_with_no_partner_at_all_is_blocked(self, config):
        """Both halves must exist; aligning one alone would produce a broken run."""
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP)

        plan = plan_for([gex], config)

        assert not plan.entries
        assert plan.skipped[0].reason == planning.SkipReason.PAIR_MISSING
        assert MULTIOME_ATAC_PREP in plan.skipped[0].detail

    def test_pairs_are_matched_on_load_name(self, config):
        """Same preps, different loads , these are two experiments, not one pair."""
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP, load="3492_A01")
        other = make("ATAC-9", "ATX-36013", MULTIOME_ATAC_PREP, load="9999_Z09")

        plan = plan_for([gex, other], config)

        reasons = {skip.sample.fastq_name: skip.reason for skip in plan.skipped}
        assert reasons["GEX-1"] == planning.SkipReason.PAIR_MISSING
        assert reasons["ATAC-9"] == planning.SkipReason.PAIR_MISSING

    def test_an_atac_half_with_no_partner_is_reported_apart_from_the_skips(self, config):
        """The one thing worth saying about a pairless ATAC half is that it has no pair.

        Everything else about it is decided by a GEX half that is not here, so it is kept
        out of "Not Being Submitted" , where it would sit beside genuine configuration
        faults , and reported as its own note.
        """
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP, load="3492_A01")
        lone_atac = make("ATAC-9", "ATX-36013", MULTIOME_ATAC_PREP, load="9999_Z09")

        plan = plan_for([gex, lone_atac], config)

        assert [skip.sample.fastq_name for skip in plan.unpaired_multiome] == ["ATAC-9"]
        reported = [skip.sample.fastq_name for skip in plan.reportable_skips]
        assert "ATAC-9" not in reported
        # The GEX half missing its partner is a different matter: the user chose that one,
        # and it stays in the table.
        assert "GEX-1" in reported

    def test_a_non_multiome_sample_is_unaffected(self, config):
        """The gate must not touch the 99% of the mirror that has no pair."""
        plain = make("PLAIN-1", "10X120", "10xV4", load="3492_A01")

        plan = plan_for([plain], config)

        assert [entry.sample.fastq_name for entry in plan.entries] == ["PLAIN-1"]

    def test_post_alignment_does_not_wait_on_the_partner(self, config):
        """Once aligned, the halves have already been processed together."""
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP, align="COMPLETED")

        plan = plan_for([gex], config)

        assert [entry.stage for entry in plan.entries] == [Stage.POST_ALIGN]

    def test_forcing_alignment_still_respects_the_pair(self, config):
        """Force overrides "already complete", not "there is nothing to align with"."""
        gex = make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP, align="COMPLETED")

        plan = plan_for([gex], config, force=Stage.ALIGN)

        assert not plan.entries
        assert plan.skipped[0].reason == planning.SkipReason.PAIR_MISSING


class TestSelectionExpansion:
    def test_the_api_expands_a_selection_to_whole_pairs(self, client, user, config):
        """Queueing half a pair over the API has the same guard as the dashboard."""
        from apps.workflow_engine.models import WorkflowConfig

        WorkflowConfig.objects.create(name="c.jsonc", raw="{}", data=config, uploaded_by=user, is_active=True)
        make("GEX-1", "MTX-32013", MULTIOME_GEX_PREP)
        make("ATAC-1", "ATX-36013", MULTIOME_ATAC_PREP)
        client.force_login(user)

        response = client.post(
            "/api/queue/plan/", {"fastq_names": ["ATAC-1"]}, content_type="application/json"
        )

        # Asked about the ATAC half alone; the GEX half it pairs with is what actually runs,
        # so the expansion has to happen or this plan would be empty.
        body = response.json()
        assert [entry["fastq_name"] for entry in body["entries"]] == ["GEX-1"]
