from __future__ import annotations

import json

import pytest
from django.core.exceptions import ValidationError

from apps.workflow_engine import config_loader


class TestLoadJsonc:
    def test_strips_line_and_block_comments(self):
        text = """
        {
          // a line comment
          /* and a
             block comment */
          "references": {"mouse": {"MTX": "ref"}}
        }
        """
        assert config_loader.load_jsonc(text)["references"] == {"mouse": {"MTX": "ref"}}

    def test_expands_pipe_delimited_organism_keys(self):
        text = json.dumps({"references": {"macaque | macaque_nemestrina": {"RTX": "ref"}}})

        references = config_loader.load_jsonc(text)["references"]

        assert references == {"macaque": {"RTX": "ref"}, "macaque_nemestrina": {"RTX": "ref"}}

    def test_invalid_json_raises(self):
        with pytest.raises(ValidationError):
            config_loader.load_jsonc("{not json}")

    def test_expands_pipe_delimited_keys_in_every_organism_keyed_section(self):
        """probe_sets_by_organism is looked up the same way references is, so a pipe key
        left there resolves the probe set to "" instead of raising."""
        text = json.dumps(
            {
                "references": {"macaque | macaque_nemestrina": {"RTX": "ref"}},
                "probe_sets_by_organism": {"macaque | macaque_nemestrina": {"10xV4": "probes"}},
            }
        )

        config = config_loader.load_jsonc(text)

        assert set(config["probe_sets_by_organism"]) == {"macaque", "macaque_nemestrina"}

    def test_a_non_object_root_is_left_for_validate(self):
        """Parsing must not crash on it , `validate` is what reports it."""
        assert config_loader.load_jsonc("5") == 5

    def test_a_non_object_section_is_left_for_validate(self):
        assert config_loader.load_jsonc('{"references": []}')["references"] == []


def alignment(config: dict) -> dict:
    return config["workflows"]["MTX"]["alignment_command_configs"][0]


class TestValidate:
    def test_accepts_a_complete_config(self, config):
        config_loader.validate(config)

    @pytest.mark.parametrize("key", config_loader.REQUIRED_TOP_LEVEL_KEYS)
    def test_missing_top_level_key(self, config, key):
        del config[key]

        with pytest.raises(ValidationError, match=key):
            config_loader.validate(config)

    @pytest.mark.parametrize("key", config_loader.REQUIRED_STATUS_MAPPINGS)
    def test_missing_status_mapping(self, config, key):
        del config["status_mappings"][key]

        with pytest.raises(ValidationError, match=key):
            config_loader.validate(config)

    def test_missing_job_limit(self, config):
        del config["job_settings"]["limit"]

        with pytest.raises(ValidationError, match="limit"):
            config_loader.validate(config)

    @pytest.mark.parametrize("key", config_loader.REQUIRED_COMMAND_CONFIG_KEYS)
    def test_command_config_missing_a_required_key(self, config, key):
        del alignment(config)[key]

        with pytest.raises(ValidationError, match=key):
            config_loader.validate(config)

    def test_match_missing_library_preps(self, config):
        del alignment(config)["match"]["library_preps"]

        with pytest.raises(ValidationError, match="library_preps"):
            config_loader.validate(config)

    @pytest.mark.parametrize("field", config_loader.COMMAND_CONFIG_FIELDS)
    def test_modality_missing_a_command_config_list(self, config, field):
        del config["workflows"]["MTX"][field]

        with pytest.raises(ValidationError, match=field):
            config_loader.validate(config)

    def test_no_modalities_at_all(self, config):
        config["workflows"] = {}

        with pytest.raises(ValidationError, match="no modalities"):
            config_loader.validate(config)


class TestValidateTypes:
    """Every container the builder indexes into, checked before it is indexed into.

    An uploaded file is arbitrary JSON, and what is built out of it is the argv handed to
    `subprocess.run`. A wrong type used to be a 500 through the API and a traceback through
    the management command , or, for `command`, a command nobody wrote.
    """

    def test_a_command_written_as_a_string_is_refused(self, config):
        """`list("ocs fastqs align")` is one argv element per character."""
        alignment(config)["command"] = "ocs fastqs align tenx-arc"

        with pytest.raises(ValidationError, match="must be a list of words"):
            config_loader.validate(config)

    @pytest.mark.parametrize("root", [5, "a string", ["a", "list"], None])
    def test_a_root_that_is_not_an_object(self, root):
        with pytest.raises(ValidationError, match="Config must be an object"):
            config_loader.validate(root)

    @pytest.mark.parametrize("key", config_loader.REQUIRED_TOP_LEVEL_KEYS)
    def test_a_top_level_section_that_is_not_an_object(self, config, key):
        config[key] = []

        with pytest.raises(ValidationError, match=f"{key} must be an object"):
            config_loader.validate(config)

    def test_a_workflow_that_is_not_an_object(self, config):
        config["workflows"]["MTX"] = 5

        with pytest.raises(ValidationError, match="workflows.MTX must be an object"):
            config_loader.validate(config)

    def test_a_command_config_list_that_is_not_a_list(self, config):
        config["workflows"]["MTX"]["alignment_command_configs"] = {"name": "default"}

        with pytest.raises(ValidationError, match="alignment_command_configs must be a list"):
            config_loader.validate(config)

    def test_a_command_config_that_is_not_an_object(self, config):
        config["workflows"]["MTX"]["alignment_command_configs"] = ["default"]

        with pytest.raises(ValidationError, match=r"alignment_command_configs\[0\] must be an object"):
            config_loader.validate(config)

    def test_a_match_that_is_not_an_object(self, config):
        alignment(config)["match"] = ["10xRSeq_Mult"]

        with pytest.raises(ValidationError, match="match must be an object"):
            config_loader.validate(config)

    def test_arguments_that_are_not_a_list(self, config):
        alignment(config)["arguments"] = {"flag": "--notify"}

        with pytest.raises(ValidationError, match="arguments must be a list"):
            config_loader.validate(config)

    def test_an_argument_that_is_not_an_object(self, config):
        alignment(config)["arguments"] = ["--notify"]

        with pytest.raises(ValidationError, match=r"arguments\[0\] must be an object"):
            config_loader.validate(config)

    @pytest.mark.parametrize("flag", [5, None, ["--notify"]])
    def test_an_argument_without_a_string_flag(self, config, flag):
        alignment(config)["arguments"] = [{"flag": flag}]

        with pytest.raises(ValidationError, match="needs a string 'flag'"):
            config_loader.validate(config)

    def test_an_argument_missing_its_flag(self, config):
        alignment(config)["arguments"] = [{"value": "{email}"}]

        with pytest.raises(ValidationError, match="needs a string 'flag'"):
            config_loader.validate(config)

    def test_an_argument_value_that_is_not_a_string(self, config):
        """`value.format(...)` and the `{placeholder}` scan both assume a string."""
        alignment(config)["arguments"] = [{"flag": "--execution-vcpus", "value": 180}]

        with pytest.raises(ValidationError, match="'value' must be a string"):
            config_loader.validate(config)

    def test_a_flag_only_argument_is_still_fine(self, config):
        alignment(config)["arguments"] = [{"flag": "--include-introns"}]

        config_loader.validate(config)

    @pytest.mark.parametrize("spacing", ["180", None, 1.5, True])
    def test_spacing_that_is_not_a_whole_number(self, config, spacing):
        """It lands in a PositiveIntegerField and in `apply_async(countdown=...)`."""
        alignment(config)["spacing"] = spacing

        with pytest.raises(ValidationError, match="spacing must be a number of seconds"):
            config_loader.validate(config)

    def test_negative_spacing(self, config):
        alignment(config)["spacing"] = -1

        with pytest.raises(ValidationError, match="spacing must be a number of seconds"):
            config_loader.validate(config)

    def test_zero_spacing_is_allowed(self, config):
        alignment(config)["spacing"] = 0

        config_loader.validate(config)

    @pytest.mark.parametrize("limit", ["100", None, 1.5, True])
    def test_a_limit_that_is_not_a_whole_number(self, config, limit):
        """`in_progress >= limit` runs inside a Celery task on every beat tick."""
        config["job_settings"]["limit"] = limit

        with pytest.raises(ValidationError, match="'limit' must be a number"):
            config_loader.validate(config)
