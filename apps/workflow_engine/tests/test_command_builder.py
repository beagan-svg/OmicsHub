"""Command building , the rules ported from the OCS Submission Capsule."""

from __future__ import annotations

import pytest

from apps.sample_catalog.models import Stage
from apps.workflow_engine import command_builder
from apps.workflow_engine.command_builder import ConfigurationError

EMAIL = "bicore@alleninstitute.org"


class TestSelectCommandConfig:
    def test_matches_by_library_prep(self, config):
        selected = command_builder.select_command_config(
            config=config,
            modality="MTX",
            stage=Stage.ALIGN,
            library_prep_method_name="10xRSeq_Mult",
            organism_common_name="mouse",
        )
        assert selected["name"] == "default"

    def test_unlisted_library_prep_returns_none(self, config):
        """Not every prep runs on every modality , the sample is skipped, not an error."""
        assert (
            command_builder.select_command_config(
                config=config,
                modality="MTX",
                stage=Stage.ALIGN,
                library_prep_method_name="10xV4",
                organism_common_name="mouse",
            )
            is None
        )

    def test_listed_prep_with_uncovered_organism_raises(self, config):
        """A prep restricted to organisms that exclude this one is a config gap, not a skip."""
        config["workflows"]["MTX"]["alignment_command_configs"][0]["match"]["organisms"] = ["human"]

        with pytest.raises(ConfigurationError):
            command_builder.select_command_config(
                config=config,
                modality="MTX",
                stage=Stage.ALIGN,
                library_prep_method_name="10xRSeq_Mult",
                organism_common_name="mouse",
            )

    def test_first_match_wins(self, config):
        specific = {
            "name": "specific",
            "match": {"library_preps": ["10xRSeq_Mult"], "organisms": ["mouse"]},
            "command": ["ocs"],
            "arguments": [],
            "spacing": 1,
        }
        config["workflows"]["MTX"]["alignment_command_configs"].insert(0, specific)

        selected = command_builder.select_command_config(
            config=config,
            modality="MTX",
            stage=Stage.ALIGN,
            library_prep_method_name="10xRSeq_Mult",
            organism_common_name="mouse",
        )
        assert selected["name"] == "specific"


class TestOrganismNameFolding:
    """`macaque_nemestrina` in the config must find `macaque-nemestrina` in local data.

    OCS uses both separators and the config was only ever written with one, which stranded
    125 real samples on "No references entry for organism".
    """

    def test_underscore_in_the_config_matches_a_hyphen_on_the_sample(self, config):
        config["references"]["macaque_nemestrina"] = {"MTX": "macaque_ref"}

        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="macaque-nemestrina",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "macaque_ref"
        )

    def test_hyphen_in_the_config_matches_an_underscore_on_the_sample(self, config):
        config["references"]["harbor-porpoise"] = {"MTX": "porpoise_ref"}

        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="harbor_porpoise",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "porpoise_ref"
        )

    def test_case_is_folded_too(self, config):
        config["references"]["Gray-Mouse-Lemur"] = {"all": "lemur_ref"}

        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="gray_mouse_lemur",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "lemur_ref"
        )

    def test_an_exact_key_still_wins(self, config):
        """A config that spells two organisms differently keeps what it says."""
        config["references"]["macaque-nemestrina"] = {"MTX": "exact_ref"}
        config["references"]["macaque_nemestrina"] = {"MTX": "folded_ref"}

        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="macaque-nemestrina",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "exact_ref"
        )

    def test_two_spellings_that_disagree_are_refused_rather_than_guessed(self, config):
        """Picking one at random here means aligning against the wrong genome."""
        config["references"]["macaque_nemestrina"] = {"MTX": "one_ref"}
        config["references"]["Macaque-Nemestrina"] = {"MTX": "another_ref"}

        with pytest.raises(ConfigurationError, match="disagree"):
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="macaque-nemestrina",
                library_prep_method_name="10xRSeq_Mult",
            )

    def test_two_spellings_that_agree_are_fine(self, config):
        """Which is what the config's own `harbor-porpoise | harbor_porpoise` expands to."""
        config["references"]["harbor_porpoise"] = {"MTX": "same_ref"}
        config["references"]["harbor-porpoise"] = {"MTX": "same_ref"}

        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="Harbor-Porpoise",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "same_ref"
        )

    def test_a_genuinely_absent_organism_still_raises(self, config):
        """Folding must not turn a missing entry into a silent empty reference."""
        with pytest.raises(ConfigurationError, match="No references entry for organism 'coyote'"):
            command_builder.select_reference_name(
                config=config,
                modality="RTX",
                organism_common_name="coyote",
                library_prep_method_name="10xV4",
            )

    def test_probe_sets_fold_the_same_way(self, config, make_sample):
        config["probe_sets_by_organism"]["naked_mole_rat"] = {"10xV4": "nmr_probe_set"}
        # The RTX alignment command also substitutes {reference_name}, so give it one.
        # spelled the other way round, which exercises the fold from both directions.
        config["references"]["naked-mole-rat"] = {"RTX": "nmr_ref"}
        sample = make_sample("NMR-1", organism_common_name="naked-mole-rat", library_prep_method_name="10xV4")

        placeholders = command_builder.resolve_placeholders(
            config=config,
            sample=sample,
            modality="RTX",
            email=EMAIL,
            command_config=config["workflows"]["RTX"]["alignment_command_configs"][0],
            batch_processing=False,
        )

        assert placeholders["probe_set"] == "nmr_probe_set"

    def test_the_editors_reference_menu_folds_too(self, config):
        """Otherwise the menu is empty for exactly the samples this fixed."""
        config["references"]["macaque_nemestrina"] = {"MTX": "macaque_ref"}

        fields = command_builder.placeholder_fields(config, "MTX", "macaque-nemestrina")

        assert fields["reference_name"] == ["macaque_ref"]


class TestSelectReferenceName:
    def test_by_modality(self, config):
        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="mouse",
                library_prep_method_name="10xRSeq_Mult",
            )
            == "mouse_mtx_ref"
        )

    def test_falls_back_to_all(self, config):
        assert (
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="human",
                library_prep_method_name="10xV4",
            )
            == "human_all_ref"
        )

    def test_nested_library_prep_mapping(self, config):
        assert (
            command_builder.select_reference_name(
                config=config,
                modality="RFX",
                organism_common_name="rat",
                library_prep_method_name="10xFXv2",
            )
            == "rat_fxv2_ref"
        )

    def test_missing_modality_and_all_raises(self, config):
        with pytest.raises(ConfigurationError):
            command_builder.select_reference_name(
                config=config,
                modality="RFX",
                organism_common_name="mouse",
                library_prep_method_name="10xRSeq_Mult",
            )

    def test_unknown_organism_raises(self, config):
        with pytest.raises(ConfigurationError):
            command_builder.select_reference_name(
                config=config,
                modality="MTX",
                organism_common_name="axolotl",
                library_prep_method_name="10xRSeq_Mult",
            )


class TestBuildCommandArgs:
    def test_substitutes_placeholders(self, config, make_sample):
        sample = make_sample()
        command_config = config["workflows"]["MTX"]["alignment_command_configs"][0]

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="MTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=False,
            ),
        )
        spacing = command_config["spacing"]

        assert args == [
            "ocs",
            "fastqs",
            "align",
            "tenx-arc",
            "--reference-names",
            "mouse_mtx_ref",
            "--load-names",
            "LOAD_1",
            "--notify",
            EMAIL,
        ]
        assert spacing == 180

    def test_rtx_uses_load_name_by_default(self, config, make_sample):
        sample = make_sample(batch_name_from_vendor="RTX-34056", library_prep_method_name="10xV4")
        command_config = config["workflows"]["RTX"]["alignment_command_configs"][0]

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="RTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=False,
            ),
        )
        assert "--load-names" in args
        assert args[args.index("--load-names") + 1] == "LOAD_1"
        assert args[-1] == "--chemistry SC3Pv4"

    def test_batch_processing_switches_rtx_to_fastq_names(self, config, make_sample):
        """The flag and its value change together , that is what {input_name_flag} is for."""
        sample = make_sample(batch_name_from_vendor="RTX-34056", library_prep_method_name="10xV4")
        command_config = config["workflows"]["RTX"]["alignment_command_configs"][0]

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="RTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=True,
            ),
        )
        assert "--fastq-names" in args
        assert args[args.index("--fastq-names") + 1] == sample.fastq_name

    def test_batch_processing_does_not_affect_mtx(self, config, make_sample):
        sample = make_sample()
        command_config = config["workflows"]["MTX"]["alignment_command_configs"][0]

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="MTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=True,
            ),
        )
        assert args[args.index("--load-names") + 1] == "LOAD_1"

    def test_probe_set_for_organism_with_a_single_string(self, config, make_sample):
        sample = make_sample(organism_common_name="human", library_prep_method_name="10xV4")
        command_config = {
            "name": "flex",
            "match": {"library_preps": ["10xV4"]},
            "command": ["ocs"],
            "arguments": [{"flag": "--cellflex-probe-set-name", "value": "{probe_set}"}],
            "spacing": 1,
        }

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="RTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=False,
            ),
        )
        assert args[-1] == "human_probe_set"

    def test_execution_vcpus_comes_from_the_command_config(self, config, make_sample):
        sample = make_sample()
        command_config = {
            "name": "vcpus",
            "match": {"library_preps": ["10xRSeq_Mult"]},
            "command": ["ocs"],
            "arguments": [{"flag": "--execution-vcpus", "value": "{execution_vcpus}"}],
            "execution_vcpus": 180,
            "spacing": 1,
        }

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="MTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=False,
            ),
        )
        assert args[-1] == "180"

    def test_flag_only_argument_appends_no_value(self, config, make_sample):
        sample = make_sample()
        command_config = {
            "name": "flag-only",
            "match": {"library_preps": ["10xRSeq_Mult"]},
            "command": ["ocs"],
            "arguments": [{"flag": "--include-introns"}],
            "spacing": 1,
        }

        args = command_builder.render_command_args(
            command_config,
            command_builder.resolve_placeholders(
                config=config,
                sample=sample,
                modality="MTX",
                email=EMAIL,
                command_config=command_config,
                batch_processing=False,
            ),
        )
        assert args == ["ocs", "--include-introns"]
