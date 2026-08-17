"""Check which mirrored fastq samples a manifest can build commands for.

`config_loader.validate` checks whether a manifest is structurally valid. This command
checks whether the manifest names a command and reference for the lab's fastq samples
before activation, rather than finding one missing value at a time after activation.

Three outcomes per (modality, library prep, organism) combination in the mirror:

* **covered**: a command config matches and every value it substitutes resolves.
* **stage n/a**: no command config lists that library prep, so the stage does not run
  for it. Expected, not a fault: ATAC halves have no alignment of their own.
* **broken**: the library prep *is* listed but something the command needs is missing,
  usually a `references` entry for the organism. These samples fail at submit time.

Reads only, and writes nothing.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.sample_catalog.models import Sample, Stage
from apps.workflow_engine import command_builder, config_loader
from apps.workflow_engine.models import WorkflowConfig

STAGES = ((Stage.ALIGN, "ALIGNMENT"), (Stage.POST_ALIGN, "POST-ALIGNMENT"))


class Command(BaseCommand):
    help = "Report which samples in the mirror a workflow config can build commands for."

    def add_arguments(self, parser):
        parser.add_argument(
            "config_file",
            nargs="?",
            help="Path to a .jsonc config. Omit to check the active config in the database.",
        )
        parser.add_argument(
            "--show",
            type=int,
            default=10,
            help="How many combinations to list per section (default 10).",
        )

    def handle(self, *args, **options):
        data = self._load(options["config_file"])
        limit = options["show"]

        # Grouped by the database: the mirror holds hundreds of thousands of rows and only
        # the distinct combinations matter.
        combos = [
            ((row["modality"], row["library_prep_method_name"], row["organism_common_name"]), row["total"])
            for row in Sample.objects.values(
                "modality", "library_prep_method_name", "organism_common_name"
            ).annotate(total=Count("pk"))
        ]
        if not combos:
            raise CommandError("The mirror is empty. Sync some samples first.")

        broken_total = 0
        for stage, label in STAGES:
            covered, unlisted, broken = self._classify(data, stage, combos)
            broken_total += sum(row[3] for row in broken)

            self.stdout.write(f"\n=== {label} ===")
            self._summarise("covered  ", covered)
            self._summarise("stage n/a", unlisted)
            self._summarise("broken   ", broken, error=bool(broken))

            if broken:
                self.stdout.write(self.style.ERROR("  These fail at submit time:"))
                for mod, prep, organism, count, why in self._top(broken, limit):
                    self.stdout.write(f"    {count:>6}  {mod:<4} {prep:<22} {organism:<24} {why}")
            if unlisted:
                self.stdout.write("  Stage does not run for:")
                for mod, prep, organism, count in self._top(unlisted, limit):
                    self.stdout.write(f"    {count:>6}  {mod:<4} {prep:<22} {organism}")

        self.stdout.write("")
        if broken_total:
            # Not raising: this is a report, and a config with known gaps may still be the
            # right one to activate. The exit is the same either way; the count is the point.
            self.stdout.write(self.style.WARNING(f"{broken_total} samples would fail to build a command."))
        else:
            self.stdout.write(self.style.SUCCESS("Every combination in the mirror is covered."))

    def _load(self, path: str | None) -> dict:
        if path is None:
            config = WorkflowConfig.objects.filter(is_active=True).first()
            if config is None:
                raise CommandError("No active config. Pass a file path to check one before uploading.")
            uploaded = f"{config.uploaded_at:%Y-%m-%d %H:%M}"
            self.stdout.write(f"Checking the active config: {config.name} ({uploaded})")
            return config.data

        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            raise CommandError(f"Could not read {path}: {error}") from error

        self.stdout.write(f"Checking {path}")
        # Surfaced as a CommandError so the CLI prints the reason and exits non-zero,
        # rather than a Django traceback at someone checking a file before uploading it.
        try:
            data = config_loader.load_jsonc(raw)
            config_loader.validate(data)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        return data

    @staticmethod
    def _classify(data: dict, stage: str, combos: list):
        covered, unlisted, broken = [], [], []

        for (mod, prep, organism), count in combos:
            if mod not in data["workflows"]:
                broken.append((mod, prep, organism, count, f"config defines no {mod} workflow"))
                continue

            try:
                command_config = command_builder.select_command_config(
                    config=data,
                    modality=mod,
                    stage=stage,
                    library_prep_method_name=prep,
                    organism_common_name=organism,
                )
            except command_builder.ConfigurationError as error:
                broken.append((mod, prep, organism, count, str(error)))
                continue

            if command_config is None:
                unlisted.append((mod, prep, organism, count))
                continue

            # Only a command that names a reference needs one to exist. Post-alignment runs
            # over alignment output and names no genome, so checking it here would invent a
            # failure the submission would never hit.
            if command_builder.uses_placeholder(command_config, "reference_name"):
                try:
                    command_builder.select_reference_name(
                        config=data,
                        modality=mod,
                        organism_common_name=organism,
                        library_prep_method_name=prep,
                    )
                except command_builder.ConfigurationError as error:
                    broken.append((mod, prep, organism, count, str(error)))
                    continue

            covered.append((mod, prep, organism, count))

        return covered, unlisted, broken

    def _summarise(self, label: str, rows: list, *, error: bool = False):
        line = f"  {label}  {sum(row[3] for row in rows):>6} samples across {len(rows)} combinations"
        self.stdout.write(self.style.ERROR(line) if error else line)

    @staticmethod
    def _top(rows: list, limit: int) -> list:
        return sorted(rows, key=lambda row: -row[3])[:limit]
