"""Stage decisions: which stage, if any, runs for a sample right now."""

from __future__ import annotations

import pytest

from apps.catalog.models import NOT_COMPLETED, Stage
from apps.queueing.services.planning import SkipReason, build_plan

pytestmark = pytest.mark.django_db

EMAIL = "bicore@alleninstitute.org"


def plan_for(sample, config, **kwargs):
    return build_plan(samples=[sample], config=config, email=EMAIL, **kwargs)


class TestAlignment:
    def test_runs_once_ingest_is_complete(self, config, make_sample):
        plan = plan_for(make_sample(ingest="INGEST_COMPLETE"), config)

        assert [entry.stage for entry in plan.entries] == [Stage.ALIGN]

    def test_waits_while_ingest_is_incomplete(self, config, make_sample):
        plan = plan_for(make_sample(ingest=NOT_COMPLETED), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.INGEST_INCOMPLETE

    def test_not_resubmitted_while_in_progress(self, config, make_sample):
        plan = plan_for(make_sample(align="IN_PROGRESS"), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.ALIGNMENT_IN_PROGRESS

    def test_archived_counts_as_complete(self, config, make_sample):
        """status_mappings lists ARCHIVED alongside COMPLETED, so alignment is done."""
        plan = plan_for(make_sample(align="ARCHIVED"), config)

        assert [entry.stage for entry in plan.entries] == [Stage.POST_ALIGN]

    def test_failed_alignment_is_retried(self, config, make_sample):
        """FAILED is in no completion list, so the stage is due to run again."""
        plan = plan_for(make_sample(align="FAILED"), config)

        assert [entry.stage for entry in plan.entries] == [Stage.ALIGN]

    def test_force_overrides_a_completed_alignment(self, config, make_sample):
        plan = plan_for(make_sample(align="COMPLETED", postalign="COMPLETED"), config, force=Stage.ALIGN)

        assert [entry.stage for entry in plan.entries] == [Stage.ALIGN]

    def test_force_overrides_an_in_progress_alignment(self, config, make_sample):
        plan = plan_for(make_sample(align="IN_PROGRESS"), config, force=Stage.ALIGN)

        assert [entry.stage for entry in plan.entries] == [Stage.ALIGN]


class TestPostAlignment:
    def test_runs_once_alignment_is_complete(self, config, make_sample):
        plan = plan_for(make_sample(align="COMPLETED"), config)

        assert [entry.stage for entry in plan.entries] == [Stage.POST_ALIGN]

    def test_never_in_the_same_pass_as_its_alignment(self, config, make_sample):
        """Alignment output does not exist yet, so only alignment is planned."""
        plan = plan_for(make_sample(align=NOT_COMPLETED), config)

        assert [entry.stage for entry in plan.entries] == [Stage.ALIGN]

    def test_not_resubmitted_while_in_progress(self, config, make_sample):
        plan = plan_for(make_sample(align="COMPLETED", postalign="IN_PROGRESS"), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.POST_ALIGNMENT_IN_PROGRESS

    def test_nothing_to_do_when_both_stages_are_complete(self, config, make_sample):
        plan = plan_for(make_sample(align="COMPLETED", postalign="COMPLETED"), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.ALREADY_COMPLETE

    def test_force_does_not_bypass_the_alignment_prerequisite(self, config, make_sample):
        """Forcing QC on an unaligned sample does nothing at all.

        There is no alignment output to run QC over, and the user asked for QC , planning
        the alignment instead would queue a job they did not ask for, on a page whose
        whole point is that nothing runs unseen.
        """
        plan = plan_for(make_sample(align=NOT_COMPLETED), config, force=Stage.POST_ALIGN)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.ALIGNMENT_INCOMPLETE
        assert "no output to run QC over" in plan.skipped[0].detail

    def test_force_overrides_a_completed_post_alignment(self, config, make_sample):
        plan = plan_for(make_sample(align="COMPLETED", postalign="COMPLETED"), config, force=Stage.POST_ALIGN)

        assert [entry.stage for entry in plan.entries] == [Stage.POST_ALIGN]


class TestModality:
    def test_inferred_from_the_batch_name(self, config, make_sample):
        plan = plan_for(make_sample(batch_name_from_vendor="MTX-22068"), config)

        assert plan.entries[0].modality == "MTX"
        assert plan.entries[0].modality_source == "inferred"

    def test_an_unrecognised_prefix_is_rtx_rather_than_unknown(self, config, make_sample):
        """Most of the mirror has a bare 10X* batch name; none of it is an error case."""
        sample = make_sample(batch_name_from_vendor="ZZZ-1", library_prep_method_name="10xV4")

        plan = plan_for(sample, config)

        assert plan.entries[0].modality == "RTX"
        assert not plan.needs_modality

    def test_atx_plans_as_mtx(self, config, make_sample):
        """The ATAC half of a multiome pair runs the MTX workflow."""
        plan = plan_for(make_sample(batch_name_from_vendor="ATX-36013"), config)

        assert plan.entries[0].modality == "MTX"

    def test_a_modality_the_config_cannot_run_is_flagged(self, config, make_sample):
        """What "needs modality" now means: known modality, no workflow for it."""
        without_rtx = {**config, "workflows": {k: v for k, v in config["workflows"].items() if k != "RTX"}}

        plan = plan_for(make_sample(batch_name_from_vendor="10X120"), without_rtx)

        assert not plan.entries
        assert [skip.sample.fastq_name for skip in plan.needs_modality] == ["NY-MX22068-2"]
        assert "no RTX workflow" in plan.needs_modality[0].detail

    def test_a_confirmed_modality_is_used_instead(self, config, make_sample):
        plan = plan_for(make_sample(batch_name_from_vendor="ZZZ-1"), config, modality="MTX")

        assert plan.entries[0].modality == "MTX"
        assert plan.entries[0].modality_source == "user_confirmed"
        assert not plan.needs_modality


class TestUnconfiguredLibraryPrep:
    def test_reported_rather_than_submitted(self, config, make_sample):
        """A prep no command config lists means the stage does not run for this sample."""
        plan = plan_for(make_sample(library_prep_method_name="10xNotConfigured"), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.LIBRARY_PREP_UNCONFIGURED

    def test_organism_gap_is_reported_against_the_sample(self, config, make_sample):
        config["workflows"]["MTX"]["alignment_command_configs"][0]["match"]["organisms"] = ["human"]

        plan = plan_for(make_sample(organism_common_name="mouse"), config)

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.LIBRARY_PREP_UNCONFIGURED


def test_plans_each_sample_independently(config, make_sample):
    ready = make_sample("READY-1")
    aligned = make_sample("ALIGNED-1", align="COMPLETED")
    waiting = make_sample("WAITING-1", ingest=NOT_COMPLETED)

    plan = build_plan(samples=[ready, aligned, waiting], config=config, email=EMAIL)

    assert {(entry.sample.fastq_name, entry.stage) for entry in plan.entries} == {
        ("READY-1", Stage.ALIGN),
        ("ALIGNED-1", Stage.POST_ALIGN),
    }
    assert [skip.sample.fastq_name for skip in plan.skipped] == ["WAITING-1"]


class TestPostAlignmentNeedsNoReference:
    """Post-QC runs over alignment output, so it names no genome and needs no reference."""

    def test_an_organism_with_no_reference_can_still_run_post_qc(self, config, make_sample):
        # ferret appears in no `references` entry. The MTX post-QC command never substitutes
        # {reference_name}, so it has no business failing on one.
        sample = make_sample("FERRET-1", ingest="COMPLETED", align="COMPLETED")
        sample.organism_common_name = "ferret"
        sample.library_prep_method_name = "10xRSeq_Mult"
        sample.batch_name_from_vendor = "MTX-1"
        sample.save()

        plan = build_plan(samples=[sample], config=config, email="a@b.org")

        assert [entry.stage for entry in plan.entries] == [Stage.POST_ALIGN]
        assert "ferret" not in plan.entries[0].command
        assert plan.entries[0].placeholders["reference_name"] == ""

    def test_alignment_for_the_same_organism_still_reports_the_missing_reference(self, config, make_sample):
        """Alignment does substitute {reference_name}, so the gap must still be reported ,
        as a skipped sample naming the entry to add, not as an exception that takes the
        whole plan down with it."""
        sample = make_sample("FERRET-2", ingest="COMPLETED")
        sample.organism_common_name = "ferret"
        sample.library_prep_method_name = "10xRSeq_Mult"
        sample.batch_name_from_vendor = "MTX-1"
        sample.save()

        plan = build_plan(samples=[sample], config=config, email="a@b.org")

        assert plan.entries == []
        assert [skip.reason for skip in plan.skipped] == [SkipReason.CONFIG_INCOMPLETE]
        assert "ferret" in plan.skipped[0].detail

    def test_one_unconfigured_sample_does_not_sink_the_rest_of_the_plan(self, config, make_sample):
        good = make_sample("MOUSE-1", ingest="COMPLETED")
        good.organism_common_name = "mouse"
        good.library_prep_method_name = "10xRSeq_Mult"
        good.batch_name_from_vendor = "MTX-1"
        good.save()

        bad = make_sample("FERRET-3", ingest="COMPLETED")
        bad.organism_common_name = "ferret"
        bad.library_prep_method_name = "10xRSeq_Mult"
        bad.batch_name_from_vendor = "MTX-1"
        bad.save()

        plan = build_plan(samples=[good, bad], config=config, email="a@b.org")

        assert [entry.sample.fastq_name for entry in plan.entries] == ["MOUSE-1"]
        assert [skip.sample.fastq_name for skip in plan.skipped] == ["FERRET-3"]


FLEX_TEMPLATE = {
    "name": "10xV4_FX4",
    "match": {"library_preps": ["10xV4_FX4"]},
    "command": ["ocs", "fastqs", "align", "tenx-rnaseq-multi"],
    "arguments": [
        {"flag": "--reference-names", "value": "{reference_name}"},
        {"flag": "--cellflex-probe-set-name", "value": "{probe_set}"},
    ],
    "spacing": 180,
}


class TestEmptyPlaceholdersAreRefused:
    """Choosing a template supplies its flags, not the values looked up by library prep."""

    @pytest.fixture
    def config_with_flex(self, config):
        config["workflows"]["RTX"]["alignment_command_configs"].append(FLEX_TEMPLATE)
        return config

    @pytest.fixture
    def unlisted_prep_sample(self, make_sample):
        return make_sample(
            "NEW-1",
            batch_name_from_vendor="RTX-900",
            library_prep_method_name="10xV5_NEW",
            organism_common_name="mouse",
        )

    def test_a_flag_is_never_submitted_with_an_empty_value(self, config_with_flex, unlisted_prep_sample):
        """`--cellflex-probe-set-name ''` was previously queued and sent to OCS."""
        plan = build_plan(
            samples=[unlisted_prep_sample],
            config=config_with_flex,
            email=EMAIL,
            command_config_choices={(Stage.ALIGN, "10xV5_NEW"): "10xV4_FX4"},
        )

        assert plan.entries == []
        skip = plan.skipped[0]
        assert skip.reason == SkipReason.MISSING_VALUE
        assert skip.missing_fields == ("probe_set",)
        assert "probe_set" in skip.detail

    def test_the_modal_is_told_which_value_to_ask_for(self, config_with_flex, unlisted_prep_sample):
        plan = build_plan(
            samples=[unlisted_prep_sample],
            config=config_with_flex,
            email=EMAIL,
            command_config_choices={(Stage.ALIGN, "10xV5_NEW"): "10xV4_FX4"},
        )

        assert [(g["field"], g["command_config_name"]) for g in plan.needs_values] == [
            ("probe_set", "10xV4_FX4")
        ]

    def test_supplying_the_value_unblocks_the_sample(self, config_with_flex, unlisted_prep_sample):
        plan = build_plan(
            samples=[unlisted_prep_sample],
            config=config_with_flex,
            email=EMAIL,
            command_config_choices={(Stage.ALIGN, "10xV5_NEW"): "10xV4_FX4"},
            sample_overrides={"NEW-1": {"probe_set": "mouse_custom_probe_set"}},
        )

        assert plan.skipped == []
        assert "--cellflex-probe-set-name mouse_custom_probe_set" in plan.entries[0].command

    def test_a_hand_written_command_is_still_the_last_word(self, config_with_flex, unlisted_prep_sample):
        """The raw editor is the final escape hatch, and its author has read the command."""
        plan = build_plan(
            samples=[unlisted_prep_sample],
            config=config_with_flex,
            email=EMAIL,
            command_config_choices={(Stage.ALIGN, "10xV5_NEW"): "10xV4_FX4"},
            sample_overrides={"NEW-1": {"command": "ocs fastqs align tenx-rnaseq-multi --whatever"}},
        )

        assert plan.skipped == []
        assert plan.entries[0].command == "ocs fastqs align tenx-rnaseq-multi --whatever"
        assert plan.entries[0].edited is True

    def test_a_listed_prep_is_unaffected(self, config_with_flex, make_sample):
        """The guard must not fire for a sample the config fully describes."""
        sample = make_sample(
            "OK-1",
            batch_name_from_vendor="RTX-900",
            library_prep_method_name="10xV4",
            organism_common_name="mouse",
        )

        plan = build_plan(samples=[sample], config=config_with_flex, email=EMAIL)

        assert plan.skipped == []
        assert plan.entries[0].command_config_name == "standard"


class TestAnEditedCommand:
    def test_an_unreadable_edit_holds_back_only_that_sample(self, config, make_sample):
        """An unbalanced quote used to raise out of build_plan, so one sample's typo took
        down the plan for the whole selection."""
        sample = make_sample("EDITED-1")

        plan = build_plan(
            samples=[sample],
            config=config,
            email=EMAIL,
            sample_overrides={"EDITED-1": {"command": 'ocs fastqs align --reference "GRCh38'}},
        )

        assert not plan.entries
        assert plan.skipped[0].reason == SkipReason.MISSING_VALUE
        assert "could not be read" in plan.skipped[0].detail

    def test_a_quoted_value_stays_one_argument(self, config, make_sample):
        sample = make_sample("EDITED-2")

        plan = build_plan(
            samples=[sample],
            config=config,
            email=EMAIL,
            sample_overrides={"EDITED-2": {"command": 'ocs fastqs align --reference "two words"'}},
        )

        assert plan.entries[0].command_args[-1] == "two words"
