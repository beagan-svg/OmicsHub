"""Build commands and skip reasons for a set of fastq samples.

Write no queue entries. The API exposes this as a preview so the user sees the exact
commands and any sample without a workflow in the active manifest before confirming.

The stage rules are the ones from the OCS Submission Capsule:

* Alignment runs once ingest is complete, unless alignment is already complete or in
  progress.
* Post-alignment runs once alignment is complete, unless post-alignment is already
  complete or in progress, and never in the same pass as the alignment it depends on.
* Forcing a stage overrides "already complete" and "in progress", but not the
    prerequisite. Forcing post-alignment on a sample that has not aligned still does
  nothing, because there is no alignment output to run QC over.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from apps.sample_catalog.models import BatchPrefix, Sample, Stage
from apps.workflow_engine import command_builder
from apps.workflow_engine.command_builder import COMPLETE_STATUS_KEY, ConfigurationError

# A stage OCS is actively working on must not be resubmitted.
IN_PROGRESS = "IN_PROGRESS"


class SkipReason:
    MODALITY_UNRESOLVED = "modality_unresolved"
    INGEST_INCOMPLETE = "ingest_incomplete"
    # A multiome half whose partner is not ready. Distinct from INGEST_INCOMPLETE because
    # this sample's own ingest may be finished. It is waiting on the other half.
    PAIR_INGEST_INCOMPLETE = "pair_ingest_incomplete"
    ALIGNMENT_IN_PROGRESS = "alignment_in_progress"
    # Only reachable by forcing post-alignment: the stage was asked for by name and its
    # prerequisite is not met, so nothing runs rather than the alignment running instead.
    ALIGNMENT_INCOMPLETE = "alignment_incomplete"
    POST_ALIGNMENT_IN_PROGRESS = "post_alignment_in_progress"
    ALREADY_COMPLETE = "already_complete"
    LIBRARY_PREP_UNCONFIGURED = "library_prep_unconfigured"
    # The command config matched, but the file is missing something else the command needs
    # for this sample, usually a reference for its organism.
    CONFIG_INCOMPLETE = "config_incomplete"
    # The template substitutes a value this sample cannot supply, so the command would carry
    # a flag with nothing after it. The user is asked for the value rather than sent it.
    MISSING_VALUE = "missing_value"


@dataclass(frozen=True)
class PlannedEntry:
    sample: Sample
    stage: str
    modality: str
    modality_source: str
    command_args: list[str]
    command: str
    spacing: int
    # Which command config produced this, so the modal can show what is selected and offer
    # the alternatives, and so an edited entry can say what it was edited from.
    command_config_name: str = ""
    # The placeholder values actually used, whether the config's or the user's. Rendered as
    # the editor's current values rather than recomputed in the template.
    placeholders: dict | None = None
    edited: bool = False


@dataclass(frozen=True)
class SkippedSample:
    sample: Sample
    reason: str
    detail: str
    # Set when the skip is tied to a stage, so the UI can ask about that stage specifically.
    stage: str = ""
    modality: str = ""
    # For MISSING_VALUE: which placeholders came back empty, so the modal can ask for
    # exactly those and nothing else.
    missing_fields: tuple[str, ...] = ()
    # The command config that was in play, so the modal can name what needs the value.
    command_config_name: str = ""


@dataclass(frozen=True)
class Plan:
    entries: list[PlannedEntry]
    skipped: list[SkippedSample]
    # ATAC halves that this plan aligns through their GEX partner rather than on their own.
    # These samples are submitted with their partners, not as separate rows, so they are kept
    # apart from `skipped` rather than filtered out of it at each place that reads it.
    covered_by_pair: list[Sample]

    @property
    def needs_modality(self) -> list[SkippedSample]:
        """Return samples that need a modality before queueing."""
        return [skip for skip in self.skipped if skip.reason == SkipReason.MODALITY_UNRESOLVED]

    @property
    def needs_command_config(self) -> list[dict]:
        """Return unlisted library preps grouped for the submission modal.

        One card per (stage, library prep): the affected samples, and which modality's
        command configs to offer.
        """
        groups: dict[tuple[str, str], dict] = {}
        for skip in self.skipped:
            if skip.reason != SkipReason.LIBRARY_PREP_UNCONFIGURED:
                continue
            key = (skip.stage, skip.sample.library_prep_method_name)
            group = groups.setdefault(
                key,
                {
                    "stage": skip.stage,
                    "library_prep_method_name": skip.sample.library_prep_method_name,
                    "modality": skip.modality,
                    "samples": [],
                },
            )
            group["samples"].append(skip.sample)
        return list(groups.values())

    @property
    def needs_values(self) -> list[dict]:
        """Return empty command placeholders grouped for the submission modal.

        One card per (stage, library prep, field): the samples it blocks and the command
        config that wants the value. Grouped rather than per-sample because the cause is the
        library prep, so every sample sharing that prep needs the same answer.
        """
        groups: dict[tuple[str, str, str], dict] = {}
        for skip in self.skipped:
            if skip.reason != SkipReason.MISSING_VALUE:
                continue
            for placeholder in skip.missing_fields:
                key = (skip.stage, skip.sample.library_prep_method_name, placeholder)
                group = groups.setdefault(
                    key,
                    {
                        "stage": skip.stage,
                        "library_prep_method_name": skip.sample.library_prep_method_name,
                        "field": placeholder,
                        "command_config_name": skip.command_config_name,
                        "modality": skip.modality,
                        "samples": [],
                    },
                )
                group["samples"].append(skip.sample)
        return list(groups.values())


def build_plan(
    *,
    samples: list[Sample],
    config: dict,
    email: str,
    modality: str | None = None,
    force: str | None = None,
    batch_processing: bool = False,
    command_config_choices: dict[tuple[str, str], str] | None = None,
    sample_overrides: dict[str, dict] | None = None,
) -> Plan:
    """Build one alignment or post-alignment plan for each fastq sample.

    `modality` is the user's confirmed choice and applies to every sample; without it the
    modality is inferred from each sample's vendor batch name. `force` is a stage value
    ("align" or "post-align") that overrides the skip rules for that stage.

    `command_config_choices` maps (stage, library prep) to the name of a command config the
    user picked for a prep the config does not list. It only ever selects an entry that is
    already in the file, so a queued command stays traceable to it.

    `sample_overrides` maps a fastq name to what the user changed for that one sample in
    the submit modal, such as a different `command_config`, a different `reference_name` or
    `chemistry`, or a hand-edited `command`. Anything absent falls back to what the config
    decided, so an untouched sample plans identically with or without the dict.
    """
    choices = command_config_choices or {}
    overrides_by_sample = sample_overrides or {}
    entries: list[PlannedEntry] = []
    skipped: list[SkippedSample] = []
    covered_by_pair: list = []
    # select_command_config's result only depends on (modality, stage, library prep,
    # organism), not on which sample asked, so a submission spanning many samples but
    # few distinct combinations would otherwise re-scan the same manifest section once
    # per sample instead of once per combination it actually contains.
    command_config_cache: dict[tuple[str, str, str, str], tuple[dict | None, ConfigurationError | None]] = {}

    # Two samples sharing a load_name are one multiome job, aligned together , nothing
    # about their library prep decides that. load_name alone is not quite enough on its
    # own either: 262 load_names in the real mirror are shared by unrelated samples, so a
    # group only counts as a real pair once it actually has one MTX and one ATX side, the
    # one thing about a load_name's samples that a coincidence would not produce. Callers
    # pass every sample in the job; the dashboard and the API each expand the selection
    # through `with_multiome_partners` first. This is what lets this be a dict lookup
    # rather than a query per sample.
    groups_by_load: dict[str, list[Sample]] = {}
    for sample in samples:
        if sample.load_name:
            groups_by_load.setdefault(sample.load_name, []).append(sample)
    # Each group's representative is decided once here, not once per sample: with the
    # dict keyed by fastq_name instead, `_pair_block` and `_aligned_through_partner`
    # would each have to re-scan the group to find it, an O(group size) scan repeated
    # for every sample in that same group.
    load_groups = {
        load_name: (group, _group_representative(group))
        for load_name, group in groups_by_load.items()
        if any(s.batch_prefix == BatchPrefix.MTX for s in group)
        and any(s.batch_prefix == BatchPrefix.ATX for s in group)
    }

    for sample in samples:
        pair_block = _pair_block(sample=sample, load_groups=load_groups, config=config, force=force)
        if pair_block is not None:
            skipped.append(pair_block)
            continue

        # An ATAC half is never aligned on its own. cellranger-arc runs once over both
        # halves, submitted against the GEX side. There is nothing to plan for it and
        # nothing to report about it. Left in, it reached the command lookup, found no ATAC
        # entry in the MTX align config because none is needed, and
        # arrived in "Not Being Submitted" as six rows of `library_prep_unconfigured`,
        # reading like six samples dropped from the run rather than six that are in it.
        #
        # Alignment only. Post-alignment runs per half, so an ATAC sample whose next stage
        # is post-align is planned like any other sample.
        if _aligned_through_partner(sample=sample, load_groups=load_groups, config=config, force=force):
            covered_by_pair.append(sample)
            continue

        if modality:
            sample_modality = modality
            modality_source = "user_confirmed"
        else:
            # Read off the sample rather than re-derived here: it is a stored column, so
            # what gets queued is the same value the dashboard showed.
            sample_modality = sample.modality
            modality_source = "inferred"

        # Every sample now has a modality, so the question is no longer "could we work it
        # out" but "does the active config know how to run it".
        if sample_modality not in config["workflows"]:
            skipped.append(
                SkippedSample(
                    sample=sample,
                    reason=SkipReason.MODALITY_UNRESOLVED,
                    detail=(
                        f"{sample.batch_name_from_vendor!r} is {sample_modality}, and the "
                        f"active config defines no {sample_modality} workflow."
                    ),
                    modality=sample_modality,
                )
            )
            continue

        stage = _next_stage(sample=sample, config=config, force=force)
        if stage is None:
            skipped.append(_explain_skip(sample=sample, config=config, force=force))
            continue

        cache_key = (sample_modality, stage, sample.library_prep_method_name, sample.organism_common_name)
        if cache_key not in command_config_cache:
            try:
                command_config_cache[cache_key] = (
                    command_builder.select_command_config(
                        config=config,
                        modality=sample_modality,
                        stage=stage,
                        library_prep_method_name=sample.library_prep_method_name,
                        organism_common_name=sample.organism_common_name,
                    ),
                    None,
                )
            except ConfigurationError as caught_error:
                command_config_cache[cache_key] = (None, caught_error)
        command_config, config_error = command_config_cache[cache_key]
        if config_error is not None:
            skipped.append(
                SkippedSample(
                    sample=sample,
                    reason=SkipReason.LIBRARY_PREP_UNCONFIGURED,
                    detail=str(config_error),
                    stage=stage,
                    modality=sample_modality,
                )
            )
            continue

        if command_config is None:
            chosen = choices.get((stage, sample.library_prep_method_name))
            if chosen:
                command_config = command_builder.command_config_by_name(
                    config=config, modality=sample_modality, stage=stage, name=chosen
                )
            else:
                skipped.append(
                    SkippedSample(
                        sample=sample,
                        reason=SkipReason.LIBRARY_PREP_UNCONFIGURED,
                        detail=(
                            f"Library prep {sample.library_prep_method_name!r} is not listed in any "
                            f"{sample_modality} {stage} command config."
                        ),
                        stage=stage,
                        modality=sample_modality,
                    )
                )
                continue

        override = overrides_by_sample.get(sample.fastq_name, {})

        # Switching the command config is applied before anything is built, so the
        # placeholders below are resolved against the config the user actually chose.
        chosen_name = override.get("command_config")
        if chosen_name and chosen_name != command_config["name"]:
            try:
                command_config = command_builder.command_config_by_name(
                    config=config, modality=sample_modality, stage=stage, name=chosen_name
                )
            except ConfigurationError as error:
                skipped.append(
                    SkippedSample(
                        sample=sample,
                        reason=SkipReason.LIBRARY_PREP_UNCONFIGURED,
                        detail=str(error),
                        stage=stage,
                        modality=sample_modality,
                    )
                )
                continue

        # Building the placeholders reads the config for this sample's organism and prep, so
        # it can find a gap the command-config lookup above could not find. A missing reference
        # being the usual one. Uncaught, that gap took the whole page down with a 500 over
        # one unconfigured sample; reported, it is a row in "not being submitted" that names
        # the entry to add.
        try:
            placeholders = command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality=sample_modality,
                email=email,
                command_config=command_config,
                batch_processing=batch_processing,
                overrides=override,
            )
        except ConfigurationError as error:
            skipped.append(
                SkippedSample(
                    sample=sample,
                    reason=SkipReason.CONFIG_INCOMPLETE,
                    detail=str(error),
                    stage=stage,
                    modality=sample_modality,
                )
            )
            continue

        command_args = command_builder.render_command_args(command_config, placeholders)

        # A hand-edited command wins over everything above. Parsed with shlex so a quoted
        # reference name stays one argument. The CLI is run without a shell, so splitting
        # on whitespace would pass the quotes through as part of the value.
        #
        # "Edited" means the user changed the textarea, so it is judged against what the
        # textarea was *rendered* with, carried forward as `command_original`, and not
        # against the command these menus would build now. Those are different questions,
        # and using the second silently discarded every menu change: picking a new reference
        # makes the freshly built command differ from the untouched textarea, the textarea
        # then looks edited, and the stale text it still holds wins over the choice the user
        # just made. `command_original` is absent from an older form, in which case this
        # falls back to the previous comparison rather than treating everything as edited.
        edited_command = (override.get("command") or "").strip()
        rendered_command = (override.get("command_original") or "").strip() or " ".join(command_args)
        edited = bool(edited_command) and edited_command != rendered_command
        if edited:
            try:
                command_args = shlex.split(edited_command)
            except ValueError as error:
                # An unbalanced quote. One sample's typo must not take down the plan for
                # the whole selection, so it is held back like any other unusable sample.
                skipped.append(
                    SkippedSample(
                        sample=sample,
                        reason=SkipReason.MISSING_VALUE,
                        detail=f"The edited command could not be read: {error}.",
                        stage=stage,
                        modality=sample_modality,
                    )
                )
                continue

        # Refuse to build a command carrying an empty flag. The usual cause is a library
        # prep the config does not list: the user picked a template for it, which supplies
        # the flags, but `probe_set` and `chemistry` are looked up *by* library prep and so
        # come back empty. Rather than submit `--chemistry ` and let OCS work it out, the
        # sample is held back and the modal asks for the value.
        #
        # Checked after the raw edit, and skipped for one: a hand-written command is the
        # last escape hatch, and its author has already seen exactly what it says.
        missing = () if edited else command_builder.missing_required_values(command_config, placeholders)
        if missing:
            skipped.append(
                SkippedSample(
                    sample=sample,
                    reason=SkipReason.MISSING_VALUE,
                    detail=(
                        f"{command_config['name']!r} needs {', '.join(missing)}, which the "
                        f"config does not define for library prep "
                        f"{sample.library_prep_method_name!r}."
                    ),
                    stage=stage,
                    modality=sample_modality,
                    missing_fields=tuple(missing),
                    command_config_name=command_config["name"],
                )
            )
            continue

        entries.append(
            PlannedEntry(
                sample=sample,
                stage=stage,
                modality=sample_modality,
                modality_source=modality_source,
                command_args=command_args,
                command=" ".join(command_args),
                spacing=command_config["spacing"],
                command_config_name=command_config["name"],
                placeholders=placeholders,
                edited=edited,
            )
        )

    return Plan(entries=entries, skipped=skipped, covered_by_pair=covered_by_pair)


def _group_representative(group: list[Sample]) -> Sample:
    """Return the sample that represents a shared load_name's job.

    Use the sample with the MTX batch prefix when present. ATX has no workflow of its own,
    and an ATX sample's `modality` also resolves to MTX, so `batch_prefix`, not `modality`,
    distinguishes the two sides. Use the first sample when neither side is MTX to keep the
    choice deterministic.
    """
    return next((s for s in group if s.batch_prefix == BatchPrefix.MTX), group[0])


def _aligned_through_partner(*, sample, load_groups: dict, config: dict, force: str | None) -> bool:
    """Return whether this sample's alignment is covered by another sample sharing its load.

    Reached only after `_pair_block` has confirmed the representative is present and
    ingested, so the remaining question is which stage this sample is due for.
    """
    entry = load_groups.get(sample.load_name)
    if entry is None:
        return False
    _group, representative = entry
    if sample.fastq_name == representative.fastq_name:
        return False
    return _next_stage(sample=sample, config=config, force=force) == Stage.ALIGN


def _is_complete(sample: Sample, stage: str, config: dict) -> bool:
    return sample.stage_status(stage) in config["status_mappings"][COMPLETE_STATUS_KEY[stage]]


def _next_stage(*, sample, config: dict, force: str | None) -> str | None:
    """Return the one stage that can run for this fastq sample, or None.

    Forcing selects the stage as well as relaxing "already complete" and "in progress" for
    it. The prerequisite still holds and is not substituted for: forcing post-alignment on
    a sample that has not aligned does nothing, rather than quietly queueing the alignment
    the user did not ask for.
    """
    if force == Stage.ALIGN:
        return Stage.ALIGN if _is_complete(sample, Stage.INGEST, config) else None

    if force == Stage.POST_ALIGN:
        return Stage.POST_ALIGN if _is_complete(sample, Stage.ALIGN, config) else None

    if (
        _is_complete(sample, Stage.INGEST, config)
        and not _is_complete(sample, Stage.ALIGN, config)
        and sample.stage_status(Stage.ALIGN) != IN_PROGRESS
    ):
        return Stage.ALIGN

    if (
        _is_complete(sample, Stage.ALIGN, config)
        and not _is_complete(sample, Stage.POST_ALIGN, config)
        and sample.stage_status(Stage.POST_ALIGN) != IN_PROGRESS
    ):
        return Stage.POST_ALIGN

    return None


def _pair_block(*, sample, load_groups: dict, config: dict, force: str | None) -> SkippedSample | None:
    """Return why this shared-load job cannot yet align, or None.

    Two (or more) samples sharing a load_name align together as one job, so it cannot
    start until every sample in the group has finished ingest. Only the sample
    representing the group (`_group_representative`) is checked; the others are either
    covered by it (`_aligned_through_partner`) or, if the group has no other member,
    plan as an ordinary sample. Sharing a `load_name` alone is not an error.
    """
    entry = load_groups.get(sample.load_name)
    if entry is None:
        return None
    group, representative = entry
    if sample.fastq_name != representative.fastq_name:
        return None

    already_aligned = _is_complete(sample, Stage.ALIGN, config)
    if already_aligned and force != Stage.ALIGN:
        return None

    for partner in group:
        if partner.fastq_name == sample.fastq_name:
            continue
        if not _is_complete(partner, Stage.INGEST, config):
            return SkippedSample(
                sample=sample,
                reason=SkipReason.PAIR_INGEST_INCOMPLETE,
                detail=f"Waiting on its pair: {partner.fastq_name} ingest is "
                f"{partner.stage_status(Stage.INGEST)}.",
                stage=Stage.ALIGN,
            )

    return None


def _explain_skip(*, sample, config: dict, force: str | None = None) -> SkippedSample:
    """Return the skip reason from the statuses used for planning."""
    # Forcing narrows the question to the stage asked for, so the answer has to be about
    # that stage. Without this the fall-through below would report an unaligned sample as
    # "already complete", which is the opposite of true.
    if force == Stage.POST_ALIGN and not _is_complete(sample, Stage.ALIGN, config):
        return SkippedSample(
            sample=sample,
            reason=SkipReason.ALIGNMENT_INCOMPLETE,
            detail=(
                f"Post-alignment was forced, but alignment is "
                f"{sample.stage_status(Stage.ALIGN)}. There is no output to run QC over."
            ),
            stage=Stage.POST_ALIGN,
        )

    if not _is_complete(sample, Stage.INGEST, config):
        return SkippedSample(
            sample=sample,
            reason=SkipReason.INGEST_INCOMPLETE,
            detail=f"Ingest status is {sample.stage_status(Stage.INGEST)}",
        )

    if sample.stage_status(Stage.ALIGN) == IN_PROGRESS:
        return SkippedSample(
            sample=sample,
            reason=SkipReason.ALIGNMENT_IN_PROGRESS,
            detail="Alignment is running at OCS",
        )

    if sample.stage_status(Stage.POST_ALIGN) == IN_PROGRESS:
        return SkippedSample(
            sample=sample,
            reason=SkipReason.POST_ALIGNMENT_IN_PROGRESS,
            detail="Post-alignment is running at OCS",
        )

    return SkippedSample(
        sample=sample,
        reason=SkipReason.ALREADY_COMPLETE,
        detail=(
            f"Alignment is {sample.stage_status(Stage.ALIGN)} and "
            f"post-alignment is {sample.stage_status(Stage.POST_ALIGN)}"
        ),
    )
