"""Render submissions pages and actions."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.sample_catalog import multiome_pairing as pairing
from apps.sample_catalog.models import Sample, Stage
from apps.submission_queue import queue_entries as enqueue_service
from apps.submission_queue import queue_planning as planning
from apps.submission_queue.models import CartItem
from apps.web_ui import columns
from apps.web_ui.forms import ConfigUploadForm, SubmissionForm
from apps.workflow_engine import command_builder, config_loader, manifest_service, modality
from apps.workflow_engine.models import WorkflowConfig

from .common import OVERRIDABLE_FIELDS, PAGE_SIZE_OPTIONS, _page_size, staff_required

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
def checkout(request):
    """Show the cart and the manifest used for its submissions."""
    return render(request, "checkout.html", _checkout_context(request))


@login_required
@require_POST
def submit_review(request):
    """Build the plan showing commands, skips, and missing manifest values."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")
    return _render_submission_step(
        request, context, partial="partials/submission_review_modal.html", modal="submit"
    )


@login_required
@require_POST
def command_preview(request):
    """Build one fastq sample command from the submitted editor values."""
    config = _selected_config(request)
    if config is None:
        return JsonResponse({"error": "No active workflow config."}, status=400)

    fastq_name = request.POST.get("fastq_name", "")
    sample = Sample.objects.filter(fastq_name=fastq_name).prefetch_related("stage_statuses").first()
    if sample is None:
        return JsonResponse({"error": f"No sample named {fastq_name!r}."}, status=404)

    # Plan a multiome half with its partner so the preview shows the command for the pair.
    samples, _ = pairing.with_multiome_partners([sample])

    form = SubmissionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": str(next(iter(form.errors.values()))[0])}, status=400)

    plan = planning.build_plan(
        samples=samples,
        config=config.data,
        email=form.cleaned_data["email"] or request.user.email,
        modality=form.cleaned_data["modality"] or None,
        force=form.cleaned_data["force"] or None,
        batch_processing=form.cleaned_data["batch_processing"],
        command_config_choices=_command_config_choices(request),
        sample_overrides=_overrides_for(request, samples),
    )

    for entry in plan.entries:
        if entry.sample.fastq_name == fastq_name:
            return JsonResponse(
                {
                    "command": entry.command,
                    "command_config": entry.command_config_name,
                    "spacing": entry.spacing,
                    "edited": entry.edited,
                }
            )

    # Return the skip reason so the editor can replace the stale command.
    for skip in plan.skipped:
        if skip.sample.fastq_name == fastq_name:
            return JsonResponse({"error": skip.detail, "reason": skip.reason}, status=409)

    return JsonResponse({"error": "That sample is no longer part of this submission."}, status=409)


@login_required
@require_POST
def submit_commands(request):
    """Build the confirmation view with exact commands and the OCS notification address."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")
    return _render_submission_step(
        request, context, partial="partials/submission_confirmation_modal.html", modal="final"
    )


def _render_submission_step(request, context, *, partial, modal):
    """Render one step of the multi-step submission flow.

    An AJAX request gets the modal partial. A regular form post gets the full checkout page
    with the requested modal already open.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, partial, context)
    return render(request, "checkout.html", {**context, "open_modal": modal})


@login_required
@require_POST
def submit_confirm(request):
    """Queue the confirmed commands and remove queued samples from the cart."""
    context = _submission_context(request)
    if context is None:
        return redirect("web_ui:checkout")

    plan = context["plan"]
    if plan.needs_modality:
        messages.error(request, "Choose a modality for the samples that need one.")
        return redirect("web_ui:checkout")

    # Queueing and clearing the cart are one unit: a failure between them leaves the jobs
    # queued and still staged, and the user confirms the same submission again.
    with transaction.atomic():
        result = enqueue_service.enqueue(
            plan=plan,
            user=request.user,
            notify_email=context["submission"]["email"],
            forced=bool(context["submission"]["force"]),
            batch_processing=context["submission"]["batch_processing"],
        )
        # Only samples added to the queue leave the cart. Samples skipped while ingest is
        # running remain staged for a later submission.
        queued_names = {entry.sample.fastq_name for entry in result.created}
        queued_names |= {entry.sample.fastq_name for entry in result.already_queued}
        if queued_names:
            CartItem.objects.filter(user=request.user, sample__fastq_name__in=queued_names).delete()

    if result.created:
        messages.success(request, f"Queued {len(result.created)} jobs.")
    if result.already_queued:
        messages.info(request, f"{len(result.already_queued)} already queued; left alone.")
    if not result.created and not result.already_queued:
        messages.warning(request, "Nothing was queued. Every sample was skipped.")

    return redirect("web_ui:queue")


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
        "workflow_manifests.html",
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


def _cart_items(request):
    return (
        CartItem.objects.filter(user=request.user)
        .select_related("sample")
        .prefetch_related("sample__stage_statuses")
    )


def _selected_config(request):
    """Return the manifest used to build this submission.

    A manifest may be named explicitly. The checkout page's picker posts `config_id` and
    carries it through every step, so a user can check a submission against a manifest
        before it is the active one. Absent that, the active config is used, which is what the
        API and the worker also read.
    """
    config_id = request.POST.get("config_id") or request.GET.get("config_id")
    if config_id and config_id.isdigit():
        config = WorkflowConfig.objects.filter(pk=config_id).first()
        if config is not None:
            return config
    return WorkflowConfig.objects.filter(is_active=True).first()


def _checkout_context(request, config=None):
    """Build the cart page with staged samples and the selected manifest.

    `config` lets a caller that already looked it up (`_submission_context`, mid
    submission flow) pass it straight through instead of this running the same
    `WorkflowConfig` query a second time.
    """
    items = list(_cart_items(request))
    excluded_fastq_names = set(request.GET.getlist("exclude_fastq_names"))
    posted_fastq_names = set(request.POST.getlist("fastq_names"))
    if posted_fastq_names:
        excluded_fastq_names = {
            item.sample.fastq_name for item in items if item.sample.fastq_name not in posted_fastq_names
        }
    page_size = _page_size(request, "checkout_page_size")
    page = Paginator(items, page_size).get_page(request.GET.get("checkout_page"))
    selected_fastq_names = [
        item.sample.fastq_name for item in items if item.sample.fastq_name not in excluded_fastq_names
    ]
    if config is None:
        config = _selected_config(request)

    return {
        "cart_items": list(page.object_list),
        "cart_page": page,
        "cart_page_size": page_size,
        "checkout_excluded_fastq_names": excluded_fastq_names,
        "checkout_selected_fastq_names": selected_fastq_names,
        "checkout_page_param": "checkout_page",
        "checkout_page_size_param": "checkout_page_size",
        "page_size_options": PAGE_SIZE_OPTIONS,
        # Fixed, not the user's dashboard choice. See columns.CHECKOUT_COLUMNS.
        "columns": columns.CHECKOUT_COLUMN_LIST,
        "config": config,
        # The picker only ever shows a name and an upload date; .only() skips fetching
        # every config's full `data` (the whole parsed manifest) and `raw` (the whole
        # uploaded file text) on every checkout-flow request.
        "configs": list(WorkflowConfig.objects.only("name", "uploaded_at")),
        "modalities": modality.available_modalities(config.data) if config else [],
    }


def _submission_context(request):
    """Plan the posted fastq sample selection and gather modal data.

    Return None after messaging the user when there is nothing to plan.
    """
    config = _selected_config(request)
    if config is None:
        messages.error(request, "No active workflow config. Upload and activate one first.")
        return None

    fastq_names = request.POST.getlist("fastq_names")
    samples = list(Sample.objects.filter(fastq_name__in=fastq_names).prefetch_related("stage_statuses"))
    if not samples:
        messages.error(request, "Select at least one sample to submit.")
        return None

    # Add the missing multiome partners and notify the user because both halves are required
    # for one run.
    samples, added_partners = pairing.with_multiome_partners(samples)
    if added_partners:
        names = ", ".join(sample.fastq_name for sample in added_partners)
        messages.info(request, f"Added {len(added_partners)} multiome partner(s) to the selection: {names}.")

    form = SubmissionForm(request.POST)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, str(error[0]))
        return None

    submission = {
        "fastq_names": [sample.fastq_name for sample in samples],
        "modality": form.cleaned_data["modality"],
        "force": form.cleaned_data["force"],
        "batch_processing": form.cleaned_data["batch_processing"],
        "email": form.cleaned_data["email"] or request.user.email,
        "choices": _command_config_choices(request),
        "overrides": _overrides_for(request, samples),
        "config_id": str(config.pk),
    }

    plan = planning.build_plan(
        samples=samples,
        config=config.data,
        email=submission["email"],
        modality=submission["modality"] or None,
        force=submission["force"] or None,
        batch_processing=submission["batch_processing"],
        command_config_choices=submission["choices"],
        sample_overrides=submission["overrides"],
    )

    # needs_command_config recomputes on every access, so the groups are enriched once here
    # and passed on rather than mutated in place.
    unconfigured_groups = plan.needs_command_config
    for group in unconfigured_groups:
        group["options"] = command_builder.available_command_configs(
            config.data, group["modality"], group["stage"]
        )

    return {
        **_checkout_context(request, config=config),
        "plan": plan,
        "unconfigured_groups": unconfigured_groups,
        # Placeholders the config cannot fill for this prep. Asked for in the modal, and
        # carried forward as hidden fields so the confirm step re-plans with the same
        # answers rather than rediscovering the gap.
        "value_groups": plan.needs_values,
        # Whether closing the modal would throw away decisions the user made in it. Only
        # these three survive nothing but a re-plan: a workflow they picked, an asset they
        # chose for an unlisted prep, and any per-sample edit. Without something to lose,
        # closing costs nothing and asking about it is the kind of prompt people learn to
        # dismiss without reading, which makes the prompt useless when it matters.
        "has_unsaved_choices": bool(
            submission["overrides"] or submission["choices"] or submission["modality"]
        ),
        "submission": submission,
        # Posted back as "stage::library prep::config name" so one field carries all three.
        "choice_values": [
            f"{stage}::{prep}::{name}" for (stage, prep), name in submission["choices"].items()
        ],
        "align_groups": _batch_groups(plan, Stage.ALIGN, config.data),
        "postalign_groups": _batch_groups(plan, Stage.POST_ALIGN, config.data),
        "align_entries": [e for e in plan.entries if e.stage == Stage.ALIGN],
        "postalign_entries": [e for e in plan.entries if e.stage == Stage.POST_ALIGN],
    }


def _batch_groups(plan, stage: str, config: dict) -> list[dict]:
    """Return planned entries for one stage grouped by vendor batch.

    Each entry carries what its editor needs, including alternative command configs for its
    modality and stage and the reference and chemistry values the manifest offers for its
    organism. The template therefore renders the form without reaching back into the manifest.
    """
    groups: dict[str, dict] = {}
    for entry in plan.entries:
        if entry.stage != stage:
            continue
        batch = entry.sample.batch_name_from_vendor or "not provided"
        group = groups.setdefault(batch, {"batch": batch, "entries": []})
        group["entries"].append(
            {
                "entry": entry,
                "options": command_builder.available_command_configs(config, entry.modality, stage),
                # Passing the command config narrows the editor to the fields this command
                # substitutes. There is no Reference menu above a post-QC command, which
                # names no genome and could not have used the value.
                "fields": command_builder.placeholder_fields(
                    config,
                    entry.modality,
                    entry.sample.organism_common_name,
                    command_config=_command_config_for(config, entry, stage),
                ),
            }
        )
    return list(groups.values())


def _command_config_for(config: dict, entry, stage: str) -> dict | None:
    """Return the command config for a planned entry, or None when it is missing.

    A hand-edited entry can name a config that no longer resolves; the editor falls back to
    offering every field rather than failing to render the row.
    """
    try:
        return command_builder.command_config_by_name(
            config=config, modality=entry.modality, stage=stage, name=entry.command_config_name
        )
    except command_builder.ConfigurationError:
        return None


def _sample_overrides(request) -> dict[str, dict]:
    """Return submit-modal edits keyed by fastq name.

    Post one field per `(sample, attribute)`, such as `override__<fastq>__reference_name`,
    rather than a single blob, so a browser submitting the form without JavaScript
        still carries exactly what the user changed.

        The command textarea always posts, and a hand-edited command outranks the menus. An
        untouched textarea should not override a reference the user chose. The editor posts the
        command it rendered alongside it; if what came back is that same string the textarea
        was not touched, and it is dropped so the menus decide.
    """
    overrides: dict[str, dict] = {}
    originals: dict[str, str] = {}

    for key, value in request.POST.items():
        if not key.startswith("override__"):
            continue
        fastq_name, separator, field = key.removeprefix("override__").partition("__")
        if not separator:
            continue
        if field == "command_original":
            originals[fastq_name] = value
            continue
        if field not in OVERRIDABLE_FIELDS:
            continue
        if value:
            overrides.setdefault(fastq_name, {})[field] = value

    for fastq_name, fields in overrides.items():
        original = originals.get(fastq_name)
        if original is not None and fields.get("command", "").strip() == original.strip():
            fields.pop("command", None)

    return overrides


def _overrides_for(request, samples) -> dict[str, dict]:
    """Return all submission edits keyed by fastq name.

    Two sources, merged in precedence order: the per-prep answers to a missing placeholder,
    then the per-row edits from the command editor. A row the user edited by hand wins over
    the group answer that reached it, which is the order they made the two choices in.
    """
    merged: dict[str, dict] = {}
    for fastq_name, fields in _missing_value_answers(request, samples).items():
        merged.setdefault(fastq_name, {}).update(fields)
    for fastq_name, fields in _sample_overrides(request).items():
        merged.setdefault(fastq_name, {}).update(fields)
    return merged


def _missing_value_answers(request, samples) -> dict[str, dict]:
    """Return values supplied for placeholders the manifest could not fill.

        Posted as `missing__<stage>__<library prep>__<field>`, because the cause is the library
    prep rather than any one sample, so one answer covers every sample sharing that prep,
        and it is expanded here into the same per-sample override dict everything else uses.

        The value only reaches a sample whose prep it was given for, so an answer cannot leak
        onto an unrelated sample if the selection changes between steps.
    """
    answers: dict[str, dict] = {}
    for key, value in request.POST.items():
        if not key.startswith("missing__") or not value.strip():
            continue
        try:
            _, stage, prep, field = key.split("__", 3)
        except ValueError:
            continue
        if field not in OVERRIDABLE_FIELDS:
            continue
        for sample in samples:
            if sample.library_prep_method_name == prep:
                answers.setdefault(sample.fastq_name, {})[field] = value.strip()
    return answers


def _command_config_choices(request) -> dict[tuple[str, str], str]:
    """Return the command config selected for each unlisted library prep.

    Posted as "stage::library prep::name", so one menu carries all three. Anything that
    does not parse into three parts is ignored rather than raising: the planner then
    reports the prep as unconfigured, which is the state the user is being asked about.
    """
    choices = {}
    for value in request.POST.getlist("command_config_choice"):
        stage, _, remainder = value.partition("::")
        prep, _, name = remainder.partition("::")
        if name:
            choices[(stage, prep)] = name
    return choices
