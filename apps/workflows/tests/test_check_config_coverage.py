"""The pre-activation dry run.

What it must get right is the difference between "this stage does not run for that prep"
and "this stage would fail" , the first is normal and the second is the reason to run it.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.workflows.models import WorkflowConfig

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command("check_config_coverage", *args, stdout=out, stderr=out)
    return out.getvalue()


class TestCheckConfigCoverage:
    def test_reports_a_covered_sample(self, active_config, make_sample):
        make_sample("READY-1")

        output = run()

        assert "ALIGNMENT" in output
        assert "Every combination in the mirror is covered." in output

    def test_a_listed_prep_with_no_reference_is_broken(self, active_config, make_sample):
        """The failure this exists to catch: the prep matches, the organism has no genome."""
        make_sample("ODD-1", organism_common_name="axolotl")

        output = run()

        assert "would fail to build a command" in output
        assert "axolotl" in output

    def test_an_unlisted_prep_is_not_reported_as_broken(self, active_config, make_sample):
        """No command config lists it, so the stage simply does not run. Not a fault."""
        make_sample("ATAC-1", library_prep_method_name="10xATAC_Mult")

        output = run()

        assert "Stage does not run for:" in output
        assert "10xATAC_Mult" in output
        assert "would fail to build a command" not in output

    def test_post_alignment_does_not_require_a_reference(self, config, user, make_sample):
        """Post-QC names no genome, so a missing reference must not be charged against it."""
        WorkflowConfig.objects.create(name="c", raw="{}", data=config, uploaded_by=user, is_active=True)
        make_sample("QC-1", organism_common_name="axolotl", align="COMPLETED")

        output = run()

        post_align = output.split("=== POST-ALIGNMENT ===", 1)[1]
        broken_line = next(line for line in post_align.splitlines() if "broken" in line)
        assert "0 samples" in broken_line

        # The alignment command for this prep *does* name a reference, so it is charged
        # there — which is what makes the post-alignment zero meaningful rather than a
        # config that simply covers nothing.
        alignment = output.split("=== ALIGNMENT ===", 1)[1].split("=== POST-ALIGNMENT ===", 1)[0]
        assert "axolotl" in alignment

    def test_checks_a_file_before_it_is_uploaded(self, tmp_path, active_config, make_sample, config):
        import json

        make_sample("READY-1")
        path = tmp_path / "candidate.jsonc"
        path.write_text("// a comment\n" + json.dumps(config))

        output = run(str(path))

        assert "candidate.jsonc" in output
        assert "ALIGNMENT" in output

    def test_an_invalid_file_is_refused(self, tmp_path, make_sample):
        make_sample("READY-1")
        path = tmp_path / "bad.jsonc"
        path.write_text('{"references": {}}')

        with pytest.raises(CommandError, match="missing required keys"):
            run(str(path))

    def test_says_so_when_there_is_no_active_config(self, make_sample):
        make_sample("READY-1")

        with pytest.raises(CommandError, match="No active config"):
            run()

    def test_an_empty_mirror_is_refused(self, active_config):
        with pytest.raises(CommandError, match="mirror is empty"):
            run()
