"""Build an `ocs` command from a fastq sample and a workflow manifest."""

from __future__ import annotations

from apps.sample_catalog.models import Stage

COMMAND_CONFIG_FIELD = {
    Stage.ALIGN: "alignment_command_configs",
    Stage.POST_ALIGN: "post_alignment_command_configs",
}

# Which status_mappings list says a stage is finished.
COMPLETE_STATUS_KEY = {
    Stage.INGEST: "ingest_complete",
    Stage.ALIGN: "alignment_complete",
    Stage.POST_ALIGN: "post_alignment_complete",
}


class ConfigurationError(Exception):
    """Report that the manifest cannot describe this fastq sample."""


def _normalise_organism(name: str) -> str:
    """Normalize case and separators in an organism name."""
    return name.replace("_", "-").casefold()


def organism_entry(mapping: dict, organism_common_name: str, *, default=None):
    """Return the matching organism entry from a manifest section."""
    if organism_common_name in mapping:
        return mapping[organism_common_name]

    wanted = _normalise_organism(organism_common_name)
    matches = {key: value for key, value in mapping.items() if _normalise_organism(key) == wanted}
    if not matches:
        return default

    values = list(matches.values())
    if any(value != values[0] for value in values[1:]):
        raise ConfigurationError(
            f"Organism {organism_common_name!r} matches several entries that disagree: "
            f"{sorted(matches)}. Spell the organism exactly as the sample does, or make "
            f"the entries agree."
        )
    return values[0]


def select_command_config(
    config: dict,
    modality: str,
    stage: str,
    library_prep_method_name: str,
    organism_common_name: str,
) -> dict | None:
    """Return the first command config matching this sample, or None for an unlisted prep."""
    command_configs = config["workflows"][modality][COMMAND_CONFIG_FIELD[stage]]

    library_prep_is_listed = False
    for command_config in command_configs:
        match = command_config["match"]
        if library_prep_method_name not in match["library_preps"]:
            continue
        library_prep_is_listed = True

        # Omitting `organisms` matches any organism.
        organisms = match.get("organisms")
        if organisms is None or organism_common_name in organisms:
            return command_config

    if library_prep_is_listed:
        raise ConfigurationError(
            f"No {modality} {stage} command config for library prep {library_prep_method_name!r} "
            f"and organism {organism_common_name!r}"
        )
    return None


def available_command_configs(config: dict, modality: str, stage: str) -> list[dict]:
    """Return command configs a user may select for an unlisted library prep.

    Offering the manifest's own entries rather than free-text asset names keeps every
    queued command traceable to something in the file.
    """
    return [
        {"name": command_config["name"], "asset_name": _asset_name(command_config)}
        for command_config in config["workflows"][modality][COMMAND_CONFIG_FIELD[stage]]
    ]


def command_config_by_name(config: dict, modality: str, stage: str, name: str) -> dict:
    """Look up a command config the user chose by name."""
    for command_config in config["workflows"][modality][COMMAND_CONFIG_FIELD[stage]]:
        if command_config["name"] == name:
            return command_config
    raise ConfigurationError(f"No {modality} {stage} command config named {name!r}")


def _asset_name(command_config: dict) -> str:
    """Return the `--asset-name` value used by a command config."""
    for argument in command_config["arguments"]:
        if argument["flag"] == "--asset-name":
            return argument.get("value", "")
    return ""


def select_reference_name(
    config: dict,
    modality: str,
    organism_common_name: str,
    library_prep_method_name: str,
) -> str:
    """Look up the reference genome for an organism, modality and library prep."""
    organism_references = organism_entry(config["references"], organism_common_name)
    if organism_references is None:
        raise ConfigurationError(f"No references entry for organism {organism_common_name!r}")

    if modality in organism_references:
        reference_config = organism_references[modality]
    elif "all" in organism_references:
        reference_config = organism_references["all"]
    else:
        raise ConfigurationError(
            f"No reference for organism {organism_common_name!r} with modality {modality!r}: "
            f"expected a {modality!r} or 'all' entry, found {sorted(organism_references)}"
        )

    if isinstance(reference_config, str):
        return reference_config

    try:
        return reference_config["library_preps"][library_prep_method_name]
    except (KeyError, TypeError) as error:
        raise ConfigurationError(
            f"No reference for organism {organism_common_name!r}, modality {modality!r} "
            f"and library prep {library_prep_method_name!r}"
        ) from error


def uses_placeholder(command_config: dict, name: str) -> bool:
    """Return whether a command template substitutes `{name}`.

    Post-alignment is the case this exists for: those commands run over alignment output
    and name no genome, so resolving a reference for them would fail an organism on a
    value its command was never going to contain.

    `flag` is always a string and `value` is a string when present. `config_loader`
    refuses a config where either is not.
    """
    token = "{" + name + "}"
    return any(
        token in argument["flag"] or token in argument.get("value", "")
        for argument in command_config["arguments"]
    )


def missing_required_values(command_config: dict, placeholders: dict) -> list[str]:
    """Return placeholders in a template that resolve to empty values.

    `probe_set` and `chemistry` are looked up by library prep method, so a prep the config
    does not list resolves both to "". Substituted anyway, that emits a flag with no value
    after it, such as `--cellflex-probe-set-name  --cellranger-addopts --chemistry`, which is a
    command OCS is asked to make sense of rather than one anybody chose to send.

    `input_name_flag` is excluded: it is part of a flag's spelling, never a value, and it is
    always one of two literals.
    """
    return sorted(
        name
        for name, value in placeholders.items()
        if name != "input_name_flag" and not str(value).strip() and uses_placeholder(command_config, name)
    )


def placeholder_fields(
    config: dict,
    modality: str,
    organism_common_name: str,
    command_config: dict | None = None,
) -> dict[str, list[str]]:
    """Return values the user may select when editing a command.

    Only what the manifest already contains, so an edited command is still a command the
    manifest could have produced. References are narrowed to the sample's own organism,
    offering every reference in the file would invite aligning a mouse against human.

    Given the `command_config` the entry was built from, a field the command does not
    substitute is offered no values at all, and the editor drops it. A Reference menu
    above a post-QC command is a choice that cannot change the command.
    """
    fields: dict[str, list[str]] = {"reference_name": [], "chemistry": []}

    if command_config is None or uses_placeholder(command_config, "reference_name"):
        organism_references = organism_entry(config["references"], organism_common_name, default={})
        references: list[str] = []
        for key in (modality, "all"):
            entry = organism_references.get(key)
            if isinstance(entry, str):
                references.append(entry)
            elif isinstance(entry, dict):
                references.extend(entry.get("library_preps", {}).values())
        fields["reference_name"] = sorted(dict.fromkeys(references))

    if command_config is None or uses_placeholder(command_config, "chemistry"):
        chemistries = config["chemistry_by_library_prep"].values()
        fields["chemistry"] = sorted({value for value in chemistries if value})

    return fields


def resolve_placeholders(
    *,
    config: dict,
    sample,
    modality: str,
    email: str,
    command_config: dict,
    batch_processing: bool,
    overrides: dict | None = None,
) -> dict:
    library_prep_method_name = sample.library_prep_method_name
    organism_common_name = sample.organism_common_name

    probe_set_config = organism_entry(config["probe_sets_by_organism"], organism_common_name, default={})
    probe_set = (
        probe_set_config
        if isinstance(probe_set_config, str)
        else probe_set_config.get(library_prep_method_name, "")
    )

    if batch_processing and modality in ("RTX", "RFX"):
        input_name = sample.fastq_name
        input_name_flag = "fastq-names"
    else:
        input_name = sample.load_name
        input_name_flag = "load-names"

    # Resolved only when the template asks for it: a post-alignment command names no
    # genome, so resolving one would fail on a value it will never contain.
    reference_name = ""
    if uses_placeholder(command_config, "reference_name"):
        reference_name = select_reference_name(
            config=config,
            modality=modality,
            organism_common_name=organism_common_name,
            library_prep_method_name=library_prep_method_name,
        )

    placeholders = {
        "reference_name": reference_name,
        "load_name": sample.load_name,
        "input_name": input_name,
        "input_name_flag": input_name_flag,
        "email": email,
        "chemistry": config["chemistry_by_library_prep"].get(library_prep_method_name, ""),
        "probe_set": probe_set,
        "execution_vcpus": command_config.get("execution_vcpus", ""),
    }

    # Only keys the template already knows about, and only non-empty values: an override
    # cannot introduce a new placeholder, and clearing a field falls back to the config's
    # own answer rather than substituting an empty string into the command.
    for key, value in (overrides or {}).items():
        if key in placeholders and value:
            placeholders[key] = value

    return placeholders


def render_command_args(command_config: dict, placeholders: dict) -> list[str]:
    """Apply resolved placeholders to a command config's template."""
    command_args = list(command_config["command"])
    for argument in command_config["arguments"]:
        command_args.append(argument["flag"].format(**placeholders))
        if "value" in argument:
            command_args.append(argument["value"].format(**placeholders))
    return command_args
