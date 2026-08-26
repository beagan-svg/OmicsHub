"""Syncing the local mirror from the OCS tables."""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.cache import cache

from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import NOT_COMPLETED, Sample, Stage, StageStatus
from apps.sample_catalog.tests.conftest import when
from apps.submission_queue.models import QueueEntry

pytestmark = pytest.mark.django_db


METADATA = {
    "fastq_name": "NY-MX22068-2",
    "batch_name_from_vendor": "MTX-22068",
    "load_name": "LOAD_1",
    "library_prep_method_name": "10xRSeq_Mult",
    "organism_common_name": "mouse",
    "sample_names": ["SAMPLE_1"],
    "studies": ["StudyA"],
}


@pytest.fixture
def ocs(monkeypatch):
    """Stand in for the OCS tables."""

    class FakeOCS:
        def __init__(self):
            self.metadata = [METADATA]
            self.history = {}
            self.demands = {}

        def get_metadata_by_batch(self, batch_name_from_vendor):
            return self.metadata

        def get_metadata_by_fastq_names(self, fastq_names):
            return [entry for entry in self.metadata if entry["fastq_name"] in fastq_names]

        def get_history(self, fastq_name):
            return self.history.get(fastq_name, [])

        def get_demands(self, demand_ids):
            # Ids with no entry are absent from the result, as BatchGetItem leaves them.
            return {
                demand_id: self.demands[demand_id] for demand_id in demand_ids if demand_id in self.demands
            }

    fake = FakeOCS()
    for name in ("get_metadata_by_batch", "get_metadata_by_fastq_names", "get_history", "get_demands"):
        monkeypatch.setattr(sync.dynamodb, name, getattr(fake, name))
    return fake


def test_creates_samples_from_batch_metadata(ocs):
    samples = sync.sync_batch("MTX-22068")

    assert [sample.fastq_name for sample in samples] == ["NY-MX22068-2"]
    assert Sample.objects.get().organism_common_name == "mouse"


def test_syncing_twice_updates_rather_than_duplicates(ocs):
    sync.sync_batch("MTX-22068")
    ocs.metadata[0]["load_name"] = "LOAD_2"

    sync.sync_batch("MTX-22068")

    assert Sample.objects.count() == 1
    assert Sample.objects.get().load_name == "LOAD_2"


def test_a_sample_with_no_history_has_no_stage_status(ocs):
    sync.sync_batch("MTX-22068")

    sample = Sample.objects.get()
    assert not sample.stage_statuses.exists()
    assert sample.stage_status(Stage.ALIGN) == NOT_COMPLETED


def test_stage_status_joins_history_to_the_demand_registry(ocs):
    ocs.history["NY-MX22068-2"] = [
        {"demand_type": "ingest", "demand_id": "d-1", "last_update_time": "2026-01-01T00:00:00Z"}
    ]
    ocs.demands["d-1"] = {"status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}

    sync.sync_batch("MTX-22068")

    status = StageStatus.objects.get()
    assert (status.stage, status.status, status.demand_id) == (Stage.INGEST, "COMPLETED", "d-1")


def test_post_alignment_demand_joins_through_alignment_file_store_id(swept):
    file_store_id = "a" * 40
    sample = Sample.objects.create(fastq_name="NY-MX22068-2", **sync.sample_fields(METADATA))
    alignment_demand = {
        "demand_id": "alignment-demand",
        "demand_type": "align",
        "status": "COMPLETED",
        "last_update_time": when(2),
    }
    post_alignment_demand = {
        "demand_id": "post-alignment-demand",
        "demand_type": "post-align",
        "status": "FAILED",
        "last_update_time": when(1),
        "request": {
            "execution_parameters": {
                "params": {f"FASTQ_ALIGN_RESULT_{file_store_id.upper()}": "alignment-output"}
            }
        },
    }

    swept(
        [
            {
                "fastq_name": sample.fastq_name,
                "demand_type_and_id": "align#alignment-demand",
                "last_update_time": when(2),
                "input_output_gfs_pairs": [{"outputs": [f"gfs://{file_store_id}"]}],
            }
        ],
        [alignment_demand, post_alignment_demand],
    )

    status = StageStatus.objects.get(sample=sample, stage=Stage.POST_ALIGN)
    assert (status.status, status.demand_id) == ("FAILED", "post-alignment-demand")


def test_the_newest_demand_wins_for_a_stage(ocs):
    """A retried stage has several demands; only the most recent describes it."""
    ocs.history["NY-MX22068-2"] = [
        {"demand_type": "align", "demand_id": "old", "last_update_time": "2026-01-01T00:00:00Z"},
        {"demand_type": "align", "demand_id": "new", "last_update_time": "2026-02-01T00:00:00Z"},
    ]
    ocs.demands = {
        "old": {"status": "FAILED", "last_update_time": "2026-01-01T00:00:00Z"},
        "new": {"status": "COMPLETED", "last_update_time": "2026-02-01T00:00:00Z"},
    }

    sync.sync_batch("MTX-22068")

    status = StageStatus.objects.get(stage=Stage.ALIGN)
    assert (status.demand_id, status.status) == ("new", "COMPLETED")


def test_each_stage_is_tracked_separately(ocs):
    ocs.history["NY-MX22068-2"] = [
        {"demand_type": "ingest", "demand_id": "i", "last_update_time": when(30)},
        {"demand_type": "align", "demand_id": "a", "last_update_time": when(20)},
        {"demand_type": "post-align", "demand_id": "p", "last_update_time": when(1)},
    ]
    ocs.demands = {
        "i": {"status": "COMPLETED", "last_update_time": when(30)},
        "a": {"status": "COMPLETED", "last_update_time": when(20)},
        "p": {"status": "IN_PROGRESS", "last_update_time": when(1)},
    }

    sync.sync_batch("MTX-22068")

    sample = Sample.objects.get()
    assert sample.stage_status(Stage.INGEST) == "COMPLETED"
    assert sample.stage_status(Stage.ALIGN) == "COMPLETED"
    assert sample.stage_status(Stage.POST_ALIGN) == "IN_PROGRESS"


def test_resyncing_updates_a_changed_status(ocs):
    ocs.history["NY-MX22068-2"] = [{"demand_type": "align", "demand_id": "a", "last_update_time": when(1)}]
    ocs.demands["a"] = {"status": "IN_PROGRESS", "last_update_time": when(1)}
    sync.sync_batch("MTX-22068")

    ocs.demands["a"] = {"status": "COMPLETED", "last_update_time": when(0)}
    sync.sync_batch("MTX-22068")

    assert StageStatus.objects.get(stage=Stage.ALIGN).status == "COMPLETED"


class TestAbandonedDemands:
    """A demand OCS started and never closed must not read as work in flight.

    Drawn from SQ_AT0049-1 in prod: an alignment stuck at IN_PROGRESS since March 2024,
    two months *after* the alignment that actually produced its output completed. Taking
    the registry at its word showed the sample as running, and the planner skipped it as
    already-in-flight, so it could never be submitted again.
    """

    def test_a_finished_demand_beats_a_stale_unfinished_one(self, ocs):
        ocs.history["NY-MX22068-2"] = [
            {"demand_type": "align", "demand_id": "done", "last_update_time": when(900)},
            {"demand_type": "align", "demand_id": "stuck", "last_update_time": when(850)},
        ]
        ocs.demands = {
            "done": {"status": "COMPLETED", "last_update_time": when(900)},
            # Newer, and so would win on recency alone.
            "stuck": {"status": "IN_PROGRESS", "last_update_time": when(850)},
        }

        sync.sync_batch("MTX-22068")

        status = StageStatus.objects.get(stage=Stage.ALIGN)
        assert (status.demand_id, status.status) == ("done", "COMPLETED")

    def test_a_stale_unfinished_demand_alone_reads_as_abandoned(self, ocs):
        ocs.history["NY-MX22068-2"] = [
            {"demand_type": "align", "demand_id": "stuck", "last_update_time": when(850)}
        ]
        ocs.demands["stuck"] = {"status": "IN_PROGRESS", "last_update_time": when(850)}

        sync.sync_batch("MTX-22068")

        assert StageStatus.objects.get(stage=Stage.ALIGN).status == sync.ABANDONED

    def test_a_job_that_really_is_running_still_reads_as_in_progress(self, ocs):
        """The rule must not touch live work , an alignment takes hours, not a fortnight."""
        ocs.history["NY-MX22068-2"] = [
            {"demand_type": "align", "demand_id": "running", "last_update_time": when(0.1)}
        ]
        ocs.demands["running"] = {"status": "IN_PROGRESS", "last_update_time": when(0.1)}

        sync.sync_batch("MTX-22068")

        assert StageStatus.objects.get(stage=Stage.ALIGN).status == "IN_PROGRESS"

    def test_history_naming_a_demand_the_registry_has_dropped_is_skipped(self, ocs):
        """History outlives the registry, and a missing demand used to raise KeyError."""
        ocs.history["NY-MX22068-2"] = [
            {"demand_type": "align", "demand_id": "gone", "last_update_time": when(400)},
            {"demand_type": "ingest", "demand_id": "kept", "last_update_time": when(400)},
        ]
        ocs.demands["kept"] = {"status": "COMPLETED", "last_update_time": when(400)}

        sync.sync_batch("MTX-22068")

        assert [(s.stage, s.status) for s in StageStatus.objects.all()] == [(Stage.INGEST, "COMPLETED")]


class TestMirrorScope:
    """The mirror holds only batches this app has a workflow for."""

    @pytest.fixture
    def scanned(self, monkeypatch):
        def _scan(entries, prefixes=frozenset({"MTX", "RTX"})):
            monkeypatch.setattr(sync.dynamodb, "scan_metadata", lambda batch_prefixes=None: iter([entries]))
            return sync.sync_all_samples(batch_prefixes=prefixes)

        return _scan

    def test_keeps_batches_with_a_configured_workflow(self, scanned):
        result = scanned([{**METADATA, "fastq_name": "KEEP-1", "batch_name_from_vendor": "MTX-1"}])

        assert result["mirrored"] == 1
        assert Sample.objects.get().fastq_name == "KEEP-1"

    def test_drops_batches_without_one(self, scanned):
        """RSC samples have no OCS ingest, so this app could never submit them."""
        result = scanned([{**METADATA, "fastq_name": "RSC-1", "batch_name_from_vendor": "RSC-301"}])

        assert result["mirrored"] == 0
        assert result["skipped"] == 1
        assert not Sample.objects.exists()

    def test_an_entry_missing_a_key_attribute_is_skipped_rather_than_fatal(self, scanned):
        """DynamoDB items are schemaless. One entry without the attribute the scope is
        judged by used to raise KeyError and abandon the rest of the mirror mid-page."""
        result = scanned(
            [
                {"fastq_name": "NO-BATCH"},
                {**METADATA, "batch_name_from_vendor": "MTX-1", "fastq_name": None},
                {**METADATA, "fastq_name": "KEEP-1", "batch_name_from_vendor": "MTX-1"},
            ]
        )

        assert result["mirrored"] == 1
        assert Sample.objects.get().fastq_name == "KEEP-1"

    def test_over_long_vendor_text_does_not_lose_the_batch(self, scanned):
        """bulk_create skips validation, so an over-long string reached Postgres as a
        DataError that took the whole 500-row batch down with it."""
        result = scanned(
            [
                {
                    **METADATA,
                    "fastq_name": "LONG-1",
                    "batch_name_from_vendor": "MTX-1",
                    "library_prep_name": "x" * 400,
                }
            ]
        )

        assert result["mirrored"] == 1
        assert Sample.objects.get().library_prep_name == "x" * 255

    def test_pruning_with_nothing_in_scope_is_refused(self):
        """The highest-consequence line in the app: an empty scope excludes nothing, so
        without this the prune would delete every mirrored sample."""
        with pytest.raises(ValueError):
            sync._prune_out_of_scope(set())

    def test_prunes_samples_that_fell_out_of_scope(self, scanned, make_sample):
        """Narrowing the config must not leave unusable rows in the dashboard."""
        make_sample("OLD-1", batch_name_from_vendor="RSC-301")

        result = scanned([{**METADATA, "fastq_name": "KEEP-1", "batch_name_from_vendor": "MTX-1"}])

        assert result["pruned"] == 1
        assert not Sample.objects.filter(fastq_name="OLD-1").exists()

    def test_a_sample_with_queue_history_is_never_pruned(self, scanned, make_sample, user):
        """Its queue entry is the only record the job was ever submitted."""

        sample = make_sample("SUBMITTED-1", batch_name_from_vendor="RSC-301")
        QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=user,
            modality="MTX",
            modality_source="inferred",
            notify_email="a@b.org",
            command_args=["ocs"],
            command="ocs",
            spacing=1,
        )

        result = scanned([])

        assert result["pruned"] == 0
        assert Sample.objects.filter(fastq_name="SUBMITTED-1").exists()


class TestFullSweep:
    """The scheduled refresh that keeps the dashboard current for the whole catalogue."""

    def test_writes_status_for_a_sample_it_has_never_seen_before(self, swept, make_sample):
        """The old per-sample refresh could update a running job but never discover one."""
        sample = make_sample("NEW-1")

        swept(
            history=[
                {
                    "fastq_name": "NEW-1",
                    "demand_type_and_id": "align#d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                }
            ],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert sample.stage_status(Stage.ALIGN) == "COMPLETED"

    def test_reconciles_an_omics_hub_submission_after_ocs_failure(self, swept, make_sample, user):
        sample = make_sample("SUBMITTED-1")
        demand = {"demand_id": "d-1", "status": "IN_PROGRESS", "last_update_time": when(1)}

        swept(
            history=[
                {
                    "fastq_name": "SUBMITTED-1",
                    "demand_type_and_id": "align#d-1",
                    "last_update_time": when(1),
                }
            ],
            demands=[demand],
        )
        entry = QueueEntry.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            requested_by=user,
            modality="MTX",
            modality_source=QueueEntry.ModalitySource.INFERRED,
            notify_email="a@b.org",
            command_args=["ocs"],
            command="ocs",
            spacing=1,
            status=QueueEntry.Status.SUBMITTED,
            demand_id="d-1",
        )

        demand["status"] = "FAILED"
        demand["message"] = "Workflow failed in OCS."
        result = swept(
            history=[
                {
                    "fastq_name": "SUBMITTED-1",
                    "demand_type_and_id": "align#d-1",
                    "last_update_time": when(0),
                }
            ],
            demands=[demand],
        )

        entry.refresh_from_db()
        assert entry.status == QueueEntry.Status.FAILED
        assert entry.error_message == "Workflow failed in OCS."
        assert result["reconciled"] == 1

    def test_the_newest_demand_per_stage_wins(self, swept, make_sample):
        sample = make_sample("RETRIED-1")

        swept(
            history=[
                {
                    "fastq_name": "RETRIED-1",
                    "demand_type_and_id": "align#old",
                    "last_update_time": "2026-01-01T00:00:00Z",
                },
                {
                    "fastq_name": "RETRIED-1",
                    "demand_type_and_id": "align#new",
                    "last_update_time": "2026-02-01T00:00:00Z",
                },
            ],
            demands=[
                {"demand_id": "old", "status": "FAILED", "last_update_time": "2026-01-01T00:00:00Z"},
                {"demand_id": "new", "status": "COMPLETED", "last_update_time": "2026-02-01T00:00:00Z"},
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "COMPLETED"

    def test_untracked_demand_types_are_ignored(self, swept, make_sample):
        """OCS records transfers too; the dashboard has no column for them."""
        sample = make_sample("MOVED-1", ingest=NOT_COMPLETED)

        result = swept(
            history=[
                {
                    "fastq_name": "MOVED-1",
                    "demand_type_and_id": "transfer#d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                }
            ],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert result["statuses"] == 0
        assert not sample.stage_statuses.exists()

    def test_the_export_stage_is_tracked(self, swept, make_sample):
        """BKP Codex export is the fourth stage. It is never submitted from here, but OCS
        records it as a demand type like any other, so it arrives on the same sweep."""
        sample = make_sample("EXPORTED-1", ingest=NOT_COMPLETED)

        result = swept(
            history=[
                {
                    "fastq_name": "EXPORTED-1",
                    "demand_type_and_id": "export#d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                    "input_output_gfs_pairs": [{"outputs": ["gfs://" + "a" * 40 + "/out"]}],
                }
            ],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert result["statuses"] == 1
        assert sample.stage_status(Stage.EXPORT) == "COMPLETED"
        assert sample.stage_demand_id(Stage.EXPORT) == "d-1"

    def test_discovers_a_sample_not_yet_in_the_mirror(self, swept, ocs):
        """History for an unmirrored sample means OCS started work on it, so it
        appears on this sweep rather than waiting for the nightly metadata pass."""
        ocs.metadata = [{**METADATA, "fastq_name": "BRAND-NEW", "batch_name_from_vendor": "MTX-9"}]

        result = swept(
            history=[
                {
                    "fastq_name": "BRAND-NEW",
                    "demand_type_and_id": "ingest#d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                }
            ],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert result["discovered"] == 1
        assert Sample.objects.get(fastq_name="BRAND-NEW").stage_status(Stage.INGEST) == "COMPLETED"

    def test_does_not_discover_batches_outside_the_configured_workflows(self, swept, ocs):
        ocs.metadata = [{**METADATA, "fastq_name": "ATX-1", "batch_name_from_vendor": "ATX-500"}]

        result = swept(
            history=[
                {
                    "fastq_name": "ATX-1",
                    "demand_type_and_id": "ingest#d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                }
            ],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert result["discovered"] == 0
        assert result["out_of_scope"] == 1
        assert not Sample.objects.exists()

    def test_a_demand_missing_from_the_registry_is_not_guessed_at(self, swept, make_sample):
        """History says the demand ran; without its registry row the outcome is unknown."""
        sample = make_sample("OLD-1", ingest=NOT_COMPLETED)

        result = swept(
            history=[
                {
                    "fastq_name": "OLD-1",
                    "demand_type_and_id": "align#aged-out",
                    "last_update_time": "2020-01-01T00:00:00Z",
                }
            ],
            demands=[],
        )

        assert result["statuses"] == 0
        assert not sample.stage_statuses.exists()

    def test_an_in_flight_alignment_is_visible_before_it_finishes(self, swept, make_sample):
        """The whole point: a running demand has no history row, so the registry is the
        only place it exists."""
        sample = make_sample("RUNNING-NOW", ingest=NOT_COMPLETED)

        swept(
            history=[],
            demands=[
                {
                    "demand_id": "d-live",
                    "demand_type": "align",
                    "status": "IN_PROGRESS",
                    "last_update_time": when(0.1),
                    "request": {
                        "execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=RUNNING-NOW"}}
                    },
                }
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "IN_PROGRESS"

    def test_a_failed_alignment_is_visible(self, swept, make_sample):
        """Failures never write history either, so they were invisible before."""
        sample = make_sample("BROKEN-1", ingest=NOT_COMPLETED)

        swept(
            history=[],
            demands=[
                {
                    "demand_id": "d-bad",
                    "demand_type": "align",
                    "status": "FAILED",
                    "last_update_time": "2026-01-01T00:00:00Z",
                    "request": {"execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=BROKEN-1"}}},
                }
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "FAILED"

    def test_the_newer_of_history_and_registry_wins(self, swept, make_sample):
        """A retry after a failure must not be masked by the older completed run."""
        sample = make_sample("RETRIED-2", ingest=NOT_COMPLETED)

        swept(
            history=[
                {
                    "fastq_name": "RETRIED-2",
                    "demand_type_and_id": "align#done",
                    "last_update_time": when(30),
                }
            ],
            demands=[
                {
                    "demand_id": "done",
                    "demand_type": "align",
                    "status": "COMPLETED",
                    "last_update_time": when(30),
                },
                {
                    "demand_id": "rerun",
                    "demand_type": "align",
                    "status": "IN_PROGRESS",
                    "last_update_time": when(0.1),
                    "request": {"execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=RETRIED-2"}}},
                },
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "IN_PROGRESS"

    def test_re_running_updates_rather_than_duplicating(self, swept, make_sample):
        sample = make_sample("RUNNING-1", ingest=NOT_COMPLETED)
        history = [
            {"fastq_name": "RUNNING-1", "demand_type_and_id": "align#d-1", "last_update_time": when(1)}
        ]
        swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "IN_PROGRESS", "last_update_time": when(1)}],
        )

        swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": when(0)}],
        )

        assert sample.stage_statuses.count() == 1
        assert sample.stage_status(Stage.ALIGN) == "COMPLETED"

    def test_an_abandoned_demand_does_not_mask_the_run_that_completed(self, swept, make_sample):
        """The prod case: a registry demand stuck at IN_PROGRESS since 2024, newer than the
        history-backed alignment that actually produced the sample's output."""
        sample = make_sample("SQ_AT0049-1", ingest=NOT_COMPLETED)

        swept(
            history=[
                {
                    "fastq_name": "SQ_AT0049-1",
                    "demand_type_and_id": "align#done",
                    "last_update_time": when(900),
                }
            ],
            demands=[
                {
                    "demand_id": "done",
                    "demand_type": "align",
                    "status": "COMPLETED",
                    "last_update_time": when(900),
                },
                {
                    "demand_id": "stuck",
                    "demand_type": "align",
                    "status": "IN_PROGRESS",
                    "last_update_time": when(850),
                    "request": {
                        "execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=SQ_AT0049-1"}}
                    },
                },
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "COMPLETED"

    def test_the_sweep_stamps_synced_at_on_rows_it_updates(self, swept, make_sample):
        """auto_now only fires on the INSERT half of an upsert, so a row updated by every
        sweep kept its first timestamp , and the dashboard's freshness clock aged forever."""
        sample = make_sample("RUNNING-2", ingest=NOT_COMPLETED)
        history = [
            {"fastq_name": "RUNNING-2", "demand_type_and_id": "align#d-1", "last_update_time": when(2)}
        ]
        swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "IN_PROGRESS", "last_update_time": when(2)}],
        )
        first = sample.stage_statuses.get().synced_at

        swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": when(1)}],
        )

        assert sample.stage_statuses.get().synced_at > first


def test_sync_by_fastq_names_only_touches_those_samples(ocs):
    ocs.metadata.append({**METADATA, "fastq_name": "OTHER-1"})

    samples = sync.sync_fastq_names(["NY-MX22068-2"])

    assert [sample.fastq_name for sample in samples] == ["NY-MX22068-2"]
    assert Sample.objects.count() == 1


class TestOnlyChangedRowsAreWritten:
    """The sweep restates nothing: a row OCS has not moved is not rewritten."""

    def test_an_unchanged_demand_is_not_rewritten(self, swept, make_sample):
        make_sample("STILL-1", ingest=NOT_COMPLETED)
        history = [
            {
                "fastq_name": "STILL-1",
                "demand_type_and_id": "align#d-1",
                "last_update_time": "2026-01-01T00:00:00Z",
            }
        ]
        demands = [{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}]

        first = swept(history=history, demands=demands)
        second = swept(history=history, demands=demands)

        assert first["statuses"] == 1, "the first sweep must write the row"
        assert second["statuses"] == 0, "the second sweep rewrote a row nothing had changed"
        assert second["unchanged"] == 1

    def test_a_changed_status_is_still_written(self, swept, make_sample):
        sample = make_sample("MOVED-2", ingest=NOT_COMPLETED)
        history = [{"fastq_name": "MOVED-2", "demand_type_and_id": "align#d-1", "last_update_time": when(1)}]
        swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "IN_PROGRESS", "last_update_time": when(1)}],
        )

        result = swept(
            history=history,
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": when(0)}],
        )

        assert result["statuses"] == 1
        assert sample.stage_status(Stage.ALIGN) == "COMPLETED"

    def test_the_sweep_records_that_it_ran_even_when_nothing_changed(self, swept, make_sample):
        """The freshness clock is about the sweep, not the rows.

        Max(synced_at) only advances when a row is written, so without this a healthy sweep
        over a quiet pipeline would have reported current data as hours stale.
        """
        make_sample("QUIET-1", ingest=NOT_COMPLETED)
        history = [
            {
                "fastq_name": "QUIET-1",
                "demand_type_and_id": "align#d-1",
                "last_update_time": "2026-01-01T00:00:00Z",
            }
        ]
        demands = [{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}]
        swept(history=history, demands=demands)
        cache.delete(sync.LAST_STATUS_SWEEP_KEY)

        swept(history=history, demands=demands)

        assert cache.get(sync.LAST_STATUS_SWEEP_KEY) is not None


class TestBulkUpsert:
    """Both sync paths write in one statement per batch rather than one per row."""

    def test_the_returned_samples_carry_their_primary_keys(self, ocs):
        """Callers go straight on to `sync_stage_statuses` with these, which keys on pk.

        Postgres populates the ids on an upserting bulk_create; a backend that did not
        would leave every returned sample with pk None and no stage status written.
        """
        ocs.metadata = [
            {**METADATA, "fastq_name": "PK-1"},
            {**METADATA, "fastq_name": "PK-2"},
        ]

        created = sync.sync_fastq_names(["PK-1", "PK-2"])
        updated = sync.sync_fastq_names(["PK-1", "PK-2"])

        assert [sample.pk for sample in created] == sorted(Sample.objects.values_list("id", flat=True))
        assert all(sample.pk is not None for sample in updated)
        assert Sample.objects.count() == 2

    def test_the_per_sample_refresh_writes_in_one_statement(self, ocs, django_assert_num_queries):
        """This runs behind the dashboard's Refresh button, where a batch is 400 samples."""
        ocs.metadata = [{**METADATA, "fastq_name": f"MANY-{i}"} for i in range(5)]
        samples = list(sync.sync_fastq_names([f"MANY-{i}" for i in range(5)]))
        for sample in samples:
            ocs.history[sample.fastq_name] = [
                {"demand_type": "align", "demand_id": "d-1", "last_update_time": when(1)}
            ]
        ocs.demands["d-1"] = {"status": "COMPLETED", "last_update_time": when(1)}

        with django_assert_num_queries(1):
            sync.sync_stage_statuses(samples)

        assert StageStatus.objects.count() == 5

    def test_the_per_sample_refresh_updates_rather_than_duplicating(self, ocs):
        ocs.history["NY-MX22068-2"] = [
            {"demand_type": "align", "demand_id": "d-1", "last_update_time": when(1)}
        ]
        ocs.demands["d-1"] = {"status": "IN_PROGRESS", "last_update_time": when(1)}
        sync.sync_batch("MTX-22068")
        first = StageStatus.objects.get().synced_at

        ocs.demands["d-1"] = {"status": "COMPLETED", "last_update_time": when(0)}
        sync.sync_batch("MTX-22068")

        record = StageStatus.objects.get()
        assert record.status == "COMPLETED"
        assert record.synced_at > first, "synced_at must be updated on the conflict half too"


class TestStageStatusColumns:
    """The two builders and the column list the upsert names must not drift apart.

    Adding a key to `stage_status_fields` and forgetting STAGE_STATUS_FIELDS means the
    column is written on insert and then never updated on conflict , a value that appears
    once and is silently frozen from then on.
    """

    def test_stage_status_fields_writes_exactly_the_declared_columns(self):
        fields = sync.stage_status_fields("d-1", {"status": "COMPLETED", "last_update_time": when(1)})

        assert set(fields) == set(sync.STAGE_STATUS_FIELDS)

    def test_submitted_stage_status_fields_writes_exactly_the_declared_columns(self):
        assert set(sync.submitted_stage_status_fields("d-1")) == set(sync.STAGE_STATUS_FIELDS)

    def test_every_declared_column_exists_on_the_model(self):
        for name in sync.STAGE_STATUS_FIELDS:
            StageStatus._meta.get_field(name)


class TestSubmittedStatus:
    """The row this app asserts between sending a command and OCS reporting on it."""

    def test_a_resubmission_blanks_the_previous_demands_timing_and_output(self, make_sample):
        """The prod bug: a forced re-run showed the *previous* demand's duration and file
        store id until the next sweep corrected it, because only the id and status were set.
        """
        sample = make_sample("RERUN-1", ingest=NOT_COMPLETED)
        StageStatus.objects.create(
            sample=sample,
            stage=Stage.ALIGN,
            status="COMPLETED",
            demand_id="old",
            last_update_time=dt.datetime.now(dt.UTC),
            started_at=dt.datetime.now(dt.UTC),
            duration_seconds=10102,
            file_store_id="b2b794e49df38f84a0271a2d76707b74beb80eb7",
        )

        StageStatus.objects.update_or_create(
            sample=sample,
            stage=Stage.ALIGN,
            defaults=sync.submitted_stage_status_fields("new"),
        )

        record = StageStatus.objects.get(sample=sample, stage=Stage.ALIGN)
        assert (record.demand_id, record.status) == ("new", "SUBMITTED")
        assert record.started_at is None
        assert record.duration_seconds is None
        assert record.file_store_id == ""


class TestDemandRanking:
    def test_demands_are_ranked_by_instant_not_by_spelling(self):
        """The registry emits both "…Z" and offset forms. Compared as strings, an older
        instant written with a positive offset sorts above a newer one written in UTC, and
        the wrong demand describes the stage.
        """
        earlier = {"status": "COMPLETED", "last_update_time": "2026-02-01T05:00:00+05:00"}
        later = {"status": "COMPLETED", "last_update_time": "2026-02-01T01:00:00Z"}

        assert sync._demand_rank(later) > sync._demand_rank(earlier)

    def test_an_abandoned_demand_still_ranks_below_anything_that_finished(self):
        finished = {"status": "COMPLETED", "last_update_time": when(900)}
        abandoned = {"status": "IN_PROGRESS", "last_update_time": when(850)}

        assert sync._demand_rank(finished) > sync._demand_rank(abandoned)


class TestStageCase:
    def test_a_registry_demand_type_in_upper_case_lands_on_its_stage(self, swept, make_sample):
        """History's half of the sweep is lowercased; the registry's was passed raw, so a
        demand type OCS wrote in upper case missed TRACKED_STAGES and vanished."""
        sample = make_sample("SHOUTY-1", ingest=NOT_COMPLETED)

        swept(
            history=[],
            demands=[
                {
                    "demand_id": "d-loud",
                    "demand_type": "ALIGN",
                    "status": "FAILED",
                    "last_update_time": when(1),
                    "request": {"execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=SHOUTY-1"}}},
                }
            ],
        )

        assert sample.stage_status(Stage.ALIGN) == "FAILED"
