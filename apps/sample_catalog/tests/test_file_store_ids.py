"""File store ids: the id `ocs gfs` commands take for what a stage produced.

The subtle half is ingest. One ingest demand transfers a whole sequencing run, so its
history row lists an output per fastq in it , production has rows with fifteen , and only
`fastq_gfs_path` says which one belongs to the sample the row is keyed on. Align and
post-align rows carry exactly one output and need no such tiebreak. Every shape asserted
here was taken from prod-fastq-history rather than invented.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.ocs_integration import dynamodb
from apps.sample_catalog import ocs_sync as sync
from apps.sample_catalog.models import Sample, Stage

FASTQ_GFS = "gfs://a86dcdfc0ce54e2fb16740a83131da36ae47976d"
FASTQ_ID = "a86dcdfc0ce54e2fb16740a83131da36ae47976d"
ALIGN_OUTPUT = "gfs://b2b794e49df38f84a0271a2d76707b74beb80eb7"
ALIGN_ID = "b2b794e49df38f84a0271a2d76707b74beb80eb7"
OTHER_OUTPUT = "gfs://14569d8fd4c5a2bf1b6774b4d2929ea453b94bce"


def history_row(stage: str, demand_id: str, outputs: list[str], fastq_gfs_path=FASTQ_GFS) -> dict:
    """Return a fastq-history row shaped like a DynamoDB result."""
    return {
        "fastq_name": "NY-MX2147-9",
        "demand_type_and_id": f"{stage}#{demand_id}",
        "last_update_time": "2026-01-01T00:00:00Z",
        "fastq_gfs_path": fastq_gfs_path,
        "input_output_gfs_pairs": [{"inputs": [], "outputs": outputs}],
    }


class TestExtraction:
    def test_an_alignment_rows_single_output_is_the_id(self):
        row = history_row("align", "d-1", [ALIGN_OUTPUT])

        assert dynamodb.file_store_id(row) == ALIGN_ID

    def test_an_ingest_row_picks_this_samples_fastq_out_of_many_outputs(self):
        """The real defect this rule exists for: NY-MX2147-9's ingest lists nine outputs,
        one per fastq in the run, and eight of them belong to other samples."""
        row = history_row("ingest", "d-2", [OTHER_OUTPUT, FASTQ_GFS, ALIGN_OUTPUT])

        assert dynamodb.file_store_id(row) == FASTQ_ID

    def test_a_single_output_ingest_still_resolves(self):
        """Most ingests transfer one fastq; the output and fastq_gfs_path are the same."""
        row = history_row("ingest", "d-3", [FASTQ_GFS])

        assert dynamodb.file_store_id(row) == FASTQ_ID

    def test_several_outputs_and_no_way_to_choose_gives_nothing(self):
        """A wrong id points at another sample's data, which is worse than a blank cell."""
        row = history_row("align", "d-4", [ALIGN_OUTPUT, OTHER_OUTPUT], fastq_gfs_path=None)

        assert dynamodb.file_store_id(row) == ""

    def test_a_row_with_no_outputs_gives_nothing(self):
        """Export rows and interrupted post-aligns produce none."""
        assert dynamodb.file_store_id(history_row("export", "d-5", [])) == ""
        assert dynamodb.file_store_id({"fastq_name": "X", "demand_type_and_id": "align#d"}) == ""

    @pytest.mark.parametrize(
        "path",
        [
            "s3://prod-file-store-us-west-2-010668866872/abc/def",  # not a GFS path
            "gfs://SHORT",
            "gfs://B2B794E49DF38F84A0271A2D76707B74BEB80EB7",  # ids are lowercase hex
            "b2b794e49df38f84a0271a2d76707b74beb80eb7",  # no scheme
        ],
    )
    def test_anything_that_is_not_a_gfs_path_is_refused(self, path):
        """The column stores the value pasted into OCS tooling. Storing an invalid value
        would display unusable data instead of an empty result."""
        assert dynamodb.file_store_id(history_row("align", "d-6", [path], fastq_gfs_path=None)) == ""


class TestProjection:
    def test_the_history_scan_asks_for_both_gfs_attributes(self, monkeypatch):
        """Asserted on the projection because that is what silently drops fields: parsing
        is fine against a mock while production returns rows with neither attribute."""
        captured = {}

        def fake_scan(table_name, page_size, **kwargs):
            captured.update(kwargs)
            return iter([])

        monkeypatch.setattr(dynamodb, "_scan", fake_scan)
        list(dynamodb.scan_history())

        assert "fastq_gfs_path" in captured["ProjectionExpression"]
        assert "input_output_gfs_pairs" in captured["ProjectionExpression"]


@pytest.mark.django_db
class TestSweep:
    """Refresh file store ids for the full catalogue."""

    @pytest.fixture
    def sample(self):
        return Sample.objects.create(fastq_name="NY-MX2147-9", batch_name_from_vendor="MTX-2147")

    def test_the_id_reaches_the_mirror(self, swept, sample):
        swept(
            history=[history_row("align", "d-1", [ALIGN_OUTPUT])],
            demands=[{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}],
        )

        assert sample.stage_file_store_id(Stage.ALIGN) == ALIGN_ID

    def test_a_reingest_stores_the_output_of_the_demand_that_won(self, swept, sample):
        """Two ingest rows for one sample is a real shape , NY-AT16020-10 has exactly this,
        with a different fastq_gfs_path each time. Taking the id from whichever row was
        scanned last would pair the winning demand with the loser's output.
        """
        superseded = "gfs://70949c0b6b85a4ea7abd0d452b6ae27720637cad"
        swept(
            history=[
                history_row("ingest", "old", [superseded], fastq_gfs_path=superseded),
                history_row("ingest", "new", [FASTQ_GFS]),
            ],
            demands=[
                {"demand_id": "old", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"},
                {"demand_id": "new", "status": "COMPLETED", "last_update_time": "2026-02-01T00:00:00Z"},
            ],
        )

        record = sample.stage_statuses.get(stage=Stage.INGEST)
        assert record.demand_id == "new"
        assert record.file_store_id == FASTQ_ID

    def test_a_running_demand_has_no_output_yet_and_stores_blank(self, swept, sample):
        """An IN_PROGRESS alignment exists only in the registry , no history row, so no
        output. Blank is the truth; the demand id is still there to chase it with."""
        # Updated just now, so the sweep reads it as running rather than abandoned. That
        # judgement is on age, and a fixed date would flip this test as it aged.
        running_since = dt.datetime.now(dt.UTC).isoformat()
        swept(
            history=[],
            demands=[
                {
                    "demand_id": "d-9",
                    "demand_type": "align",
                    "status": "IN_PROGRESS",
                    "last_update_time": running_since,
                    "request": {
                        "execution_parameters": {"params": {"FASTQ_NAMES": "FASTQ_SET_1=NY-MX2147-9"}}
                    },
                }
            ],
        )

        record = sample.stage_statuses.get(stage=Stage.ALIGN)
        assert record.status == "IN_PROGRESS"
        assert record.file_store_id == ""

    def test_a_second_sweep_does_not_wipe_the_id(self, swept, sample):
        """file_store_id has to be in the upsert's update_fields; without it the value
        survives the INSERT and is dropped by every refresh after."""
        history = [history_row("align", "d-1", [ALIGN_OUTPUT])]
        demands = [{"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}]

        swept(history=history, demands=demands)
        swept(history=history, demands=demands)

        assert sample.stage_file_store_id(Stage.ALIGN) == ALIGN_ID


@pytest.mark.django_db
class TestPerSampleRefresh:
    """Refresh file store ids for one batch through per-sample history queries."""

    def test_the_id_reaches_the_mirror(self, monkeypatch):
        sample = Sample.objects.create(fastq_name="NY-MX2147-9", batch_name_from_vendor="MTX-2147")
        monkeypatch.setattr(
            sync.dynamodb,
            "get_history",
            lambda fastq_name: [
                {
                    "demand_type": "align",
                    "demand_id": "d-1",
                    "last_update_time": "2026-01-01T00:00:00Z",
                    "file_store_id": ALIGN_ID,
                }
            ],
        )
        monkeypatch.setattr(
            sync.dynamodb,
            "get_demands",
            lambda ids: {
                "d-1": {"demand_id": "d-1", "status": "COMPLETED", "last_update_time": "2026-01-01T00:00:00Z"}
            },
        )

        sync.sync_stage_statuses([sample])

        assert sample.stage_file_store_id(Stage.ALIGN) == ALIGN_ID
