"""Load and validate an uploaded workflow manifest.

The file is JSONC: JSON with `//` and `/* */` comments, and organism keys that may list
several organisms separated by pipes ("macaque | macaque_nemestrina"). Both are handled
here so the rest of the code sees plain JSON with one organism per key.

Validation is the only thing standing between an arbitrary uploaded file and the argv
handed to `subprocess.run`, so it checks the type of every container it reads as well as
the presence of every key.
"""

from __future__ import annotations

import json
import re

from django.core.exceptions import ValidationError

REQUIRED_TOP_LEVEL_KEYS = (
    "references",
    "probe_sets_by_organism",
    "chemistry_by_library_prep",
    "workflows",
    "job_settings",
    "status_mappings",
)

REQUIRED_STATUS_MAPPINGS = ("ingest_complete", "alignment_complete", "post_alignment_complete")

COMMAND_CONFIG_FIELDS = ("alignment_command_configs", "post_alignment_command_configs")

REQUIRED_COMMAND_CONFIG_KEYS = ("name", "match", "command", "arguments", "spacing")

# Sections keyed by organism, and so subject to both pipe-separated keys and the
# separator/case folding `command_builder.organism_entry` does. A pipe key left
# unexpanded in any of them resolves to nothing instead of raising.
ORGANISM_KEYED_SECTIONS = ("references", "probe_sets_by_organism")

_TYPE_NAMES = {
    dict: "an object",
    list: "a list",
    str: "a string",
    bool: "a boolean",
    int: "a number",
    float: "a number",
    type(None): "null",
}


def _type_name(value) -> str:
    return _TYPE_NAMES.get(type(value), type(value).__name__)


def _is_int(value) -> bool:
    """Return whether a value is a JSON integer rather than a Boolean."""
    return isinstance(value, int) and not isinstance(value, bool)


def load_jsonc(text: str) -> dict:
    """Load JSONC text into a manifest with organism keys expanded."""
    without_block_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    without_comments = re.sub(r"^\s*//.*$", "", without_block_comments, flags=re.MULTILINE)

    try:
        config = json.loads(without_comments)
    except json.JSONDecodeError as error:
        raise ValidationError(f"Config is not valid JSON: {error}") from error

    if isinstance(config, dict):
        for section in ORGANISM_KEYED_SECTIONS:
            if isinstance(config.get(section), dict):
                config[section] = {
                    organism.strip(): entry
                    for organisms, entry in config[section].items()
                    for organism in organisms.split("|")
                }

    return config


def validate(config: dict) -> None:
    """Raise ValidationError when the manifest cannot build a submission command.

Checks structure only. Every section the builder reads must be present and correctly shaped.
    the way it expects. Whether a given reference or asset tag exists on OCS is not
    knowable here and is left for the submission to report.
    """
    if not isinstance(config, dict):
        raise ValidationError(f"Config must be an object, not {_type_name(config)}")

    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in config]
    if missing:
        raise ValidationError(f"Config is missing required keys: {', '.join(missing)}")

    # Every check below indexes into these, so a wrong type here is fatal on its own.
    wrong_type = [
        f"{key} must be an object, not {_type_name(config[key])}"
        for key in REQUIRED_TOP_LEVEL_KEYS
        if not isinstance(config[key], dict)
    ]
    if wrong_type:
        raise ValidationError(wrong_type)

    errors: list[str] = []

    missing_mappings = [key for key in REQUIRED_STATUS_MAPPINGS if key not in config["status_mappings"]]
    if missing_mappings:
        errors.append(f"status_mappings is missing: {', '.join(missing_mappings)}")

    limit = config["job_settings"].get("limit")
    if "limit" not in config["job_settings"]:
        errors.append("job_settings is missing 'limit'")
    elif not _is_int(limit):
        # Compared against a job count on every beat tick, so a string is a TypeError there.
        errors.append(f"job_settings 'limit' must be a number, not {_type_name(limit)}")

    if not config["workflows"]:
        errors.append("workflows defines no modalities")

    for modality, workflow in config["workflows"].items():
        if not isinstance(workflow, dict):
            errors.append(f"workflows.{modality} must be an object, not {_type_name(workflow)}")
            continue
        for field in COMMAND_CONFIG_FIELDS:
            if field not in workflow:
                errors.append(f"workflows.{modality} is missing {field}")
                continue
            command_configs = workflow[field]
            if not isinstance(command_configs, list):
                errors.append(
                    f"workflows.{modality}.{field} must be a list, not {_type_name(command_configs)}"
                )
                continue
            for index, command_config in enumerate(command_configs):
                label = f"workflows.{modality}.{field}[{index}]"
                errors.extend(_command_config_errors(command_config, label))

    if errors:
        raise ValidationError(errors)


def _command_config_errors(command_config, label: str) -> list[str]:
    """Return validation errors for one command config entry."""
    if not isinstance(command_config, dict):
        return [f"{label} must be an object, not {_type_name(command_config)}"]

    errors = [
        f"{label} is missing '{key}'" for key in REQUIRED_COMMAND_CONFIG_KEYS if key not in command_config
    ]

    if "match" in command_config:
        if not isinstance(command_config["match"], dict):
            errors.append(f"{label}.match must be an object, not {_type_name(command_config['match'])}")
        elif "library_preps" not in command_config["match"]:
            errors.append(f"{label}.match is missing 'library_preps'")

    if "command" in command_config and not isinstance(command_config["command"], list):
        # A string here is not a near miss: the builder calls list() on it, which explodes
        # it into one argv element per character.
        errors.append(
            f"{label}.command must be a list of words, not {_type_name(command_config['command'])} — "
            f'write ["ocs", "fastqs", "align"], not "ocs fastqs align"'
        )

    if "arguments" in command_config:
        errors.extend(_argument_errors(command_config["arguments"], label))

    spacing = command_config.get("spacing")
    if "spacing" in command_config and (not _is_int(spacing) or spacing < 0):
        errors.append(f"{label}.spacing must be a number of seconds, zero or more")

    return errors


def _argument_errors(arguments, label: str) -> list[str]:
    """Return errors when a command argument or its value is not a string."""
    if not isinstance(arguments, list):
        return [f"{label}.arguments must be a list, not {_type_name(arguments)}"]

    errors = []
    for index, argument in enumerate(arguments):
        where = f"{label}.arguments[{index}]"
        if not isinstance(argument, dict):
            errors.append(f"{where} must be an object, not {_type_name(argument)}")
            continue
        if not isinstance(argument.get("flag"), str):
            errors.append(f"{where} needs a string 'flag'")
        if "value" in argument and not isinstance(argument["value"], str):
            errors.append(f"{where} 'value' must be a string, not {_type_name(argument['value'])}")
    return errors
