"""Render the staff pages for uploading, activating, and inspecting workflow configs."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.web_ui.forms import ConfigUploadForm
from apps.workflow_engine import config_loader, manifest_service
from apps.workflow_engine.models import WorkflowConfig

from .view_helpers import staff_required

ARGUMENT_DESCRIPTIONS = {
    "--reference-names": (
        "OmicsHub selects this value from the References table by matching the fastq "
        "sample's organism, modality, and library prep method."
    ),
    "--cellflex-probe-set-name": (
        "OmicsHub selects this value from the Probe Sets table by matching the fastq "
        "sample's organism and, when the manifest lists one, its library prep method."
    ),
    "--asset-name": (
        "This names the OCS asset, a Docker image OCS built and registered, that runs the command."
    ),
    "--asset-tag": (
        'This pins the version of the OCS asset that runs the command. "latest" leaves it '
        "unpinned, so the command always runs the newest published version."
    ),
    "--load-names": (
        "This identifies the load OCS aligns, which can combine multiple fastq sample halves "
        "(for example, the GEX and ATAC halves of a multiome sample) under one alignment job."
    ),
    "--{input_name_flag}": (
        "This resolves to --load-names or --fastq-names, whichever matches how the fastq "
        "sample was submitted, and its value is the load or fastq name OCS aligns."
    ),
    "--cellranger-addopts": "OCS passes this value straight through to Cell Ranger's own command-line flags.",
    "--execution-vcpus": "This reserves compute capacity for the alignment job.",
    "--notify-on": "This sets which OCS status triggers an email notification.",
    "--notify": "This is the email address OCS notifies.",
}

STATUS_MAPPING_LABELS = {
    "ingest_complete": "Ingest complete",
    "alignment_complete": "Alignment complete",
    "post_alignment_complete": "Post-alignment complete",
}


@login_required
@staff_required
def configs(request):
    """Show settings for uploading and activating the submission manifest."""
    if request.method == "POST":
        form = ConfigUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            for error in form.errors.values():
                messages.error(request, str(error[0]))
            return redirect("web_ui:configs")

        name = form.cleaned_data["file"].name
        try:
            manifest_service.create_config(raw=form.raw, name=name[:255], user=request.user)
        except ValidationError as error:
            messages.error(request, f"{name} was rejected: {'; '.join(error.messages)}")
            return redirect("web_ui:configs")

        messages.success(request, f"Uploaded {name}. Activate it to start using it.")
        return redirect("web_ui:configs")

    return render(
        request,
        "configs.html",
        {"configs": WorkflowConfig.objects.select_related("uploaded_by")},
    )


@login_required
@staff_required
@require_POST
def activate_config(request, pk):
    config = get_object_or_404(WorkflowConfig, pk=pk)
    config.activate()
    messages.success(request, f"{config.name} is now active.")
    return redirect("web_ui:configs")


def _reference_rows(references: dict) -> list[dict]:
    """Flatten references into one row per organism, modality, and library prep method."""
    rows = []
    for organism, entry in references.items():
        if not isinstance(entry, dict):
            rows.append({"organism": organism, "modality": "All", "library_prep": "All", "reference": entry})
            continue
        for modality_key, value in entry.items():
            modality_label = "All" if modality_key.lower() == "all" else modality_key
            if isinstance(value, dict) and "library_preps" in value:
                for prep, reference in value["library_preps"].items():
                    rows.append(
                        {
                            "organism": organism,
                            "modality": modality_label,
                            "library_prep": prep,
                            "reference": reference,
                        }
                    )
            else:
                rows.append(
                    {
                        "organism": organism,
                        "modality": modality_label,
                        "library_prep": "All",
                        "reference": value,
                    }
                )
    return rows


def _probe_set_rows(probe_sets_by_organism: dict) -> list[dict]:
    """Flatten probe sets into one row per organism and library prep method."""
    rows = []
    for organism, entry in probe_sets_by_organism.items():
        if isinstance(entry, dict):
            for prep, probe_set in entry.items():
                rows.append({"organism": organism, "library_prep": prep, "probe_set": probe_set})
        else:
            rows.append({"organism": organism, "library_prep": "All", "probe_set": entry})
    return rows


def _command_config_rows(command_configs: list[dict]) -> list[dict]:
    """Attach a description to each argument in a modality's command configs."""
    rows = []
    for command_config in command_configs:
        arguments = [
            {**argument, "description": ARGUMENT_DESCRIPTIONS.get(argument.get("flag"))}
            for argument in command_config.get("arguments", [])
        ]
        rows.append({**command_config, "arguments": arguments})
    return rows


@login_required
def config_detail(request, pk):
    """Show one uploaded config as raw text or organized sections."""
    config = get_object_or_404(WorkflowConfig, pk=pk)
    view = request.GET.get("view")
    if view not in {"raw", "pretty"}:
        view = "pretty"

    view_options = [
        {"label": "Pretty", "value": "pretty", "url": "?view=pretty"},
        {"label": "Raw", "value": "raw", "url": "?view=raw"},
    ]
    context = {"config": config, "view": view, "view_options": view_options}
    if view == "pretty":
        data = config.data
        context.update(
            reference_rows=_reference_rows(data["references"]),
            probe_set_rows=_probe_set_rows(data["probe_sets_by_organism"]),
            chemistry_rows=data["chemistry_by_library_prep"],
            # Modality and stage are client-side tabs (tabs.js), not query params: every
            # combination has to be in the response for the browser to switch between
            # them without a reload, so nothing here is filtered down to one selection.
            modality_tab_options=[{"label": name, "value": name} for name in data["workflows"]],
            stage_tab_options=[
                {"label": "Alignment", "value": "alignment"},
                {"label": "Post-Alignment", "value": "post_alignment"},
            ],
            workflow_rows=[
                {
                    "modality": modality_name,
                    "alignment_configs": _command_config_rows(workflow.get("alignment_command_configs", [])),
                    "post_alignment_configs": _command_config_rows(
                        workflow.get("post_alignment_command_configs", [])
                    ),
                }
                for modality_name, workflow in data["workflows"].items()
            ],
            job_settings=data["job_settings"],
            status_mapping_rows=[
                {"label": STATUS_MAPPING_LABELS.get(key, key), "statuses": data["status_mappings"][key]}
                for key in config_loader.REQUIRED_STATUS_MAPPINGS
            ],
        )
    return render(request, "config_detail.html", context)
