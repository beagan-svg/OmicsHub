"""Render data locations pages and actions."""

import csv
import io
import logging
import re
import zipfile
from collections import deque
from collections.abc import Buffer, Iterator

from botocore.exceptions import BotoCoreError, ClientError
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.ocs_integration import dynamodb, s3
from apps.sample_catalog.models import NOT_COMPLETED, BatchPrefix, Sample, Stage, StageStatus
from apps.web_ui import columns
from apps.web_ui import data_location_queries as locations

from .common import (
    DEFAULT_SORT,
    DOWNLOAD_SELECTION_LIMIT,
    FILTER_FIELDS,
    PAGE_SIZE_OPTIONS,
    SORTABLE,
    _batch_options,
    _Echo,
    _filtered_samples,
    _page_size,
    _prefix_counts,
    _scoped_distinct,
    _scoped_statuses,
    _sorted,
    _status_sync_context,
    _study_options,
    export_csv_filename,
)

logger = logging.getLogger(__name__)


@login_required
def data_locations(request):
    """List S3 locations for the visible fastq samples and OCS stages."""
    queryset = _sorted(_filtered_samples(request), request)
    page_size = _page_size(request)
    page = Paginator(queryset, page_size).get_page(request.GET.get("page"))
    stage_filters = [
        {"stage": stage, "selected": request.GET.get(f"{stage.value}_status", "")}
        for stage in columns.LOCATION_STAGES
    ]
    selected_location_stage = request.GET.get("location_stage", "")
    location_rows = locations.stage_rows(page.object_list)
    if selected_location_stage in {stage.value for stage in columns.LOCATION_STAGES}:
        location_rows = [row for row in location_rows if row["stage"].value == selected_location_stage]
        for row in location_rows:
            row["show_selector"] = True
    prefix = request.GET.get("batch_prefix")
    scope = Sample.objects.all()
    if prefix in BatchPrefix.values:
        scope = scope.filter(batch_prefix=prefix)
    return render(
        request,
        "data_locations.html",
        {
            "page": page,
            "page_size": page_size,
            "page_size_options": PAGE_SIZE_OPTIONS,
            "location_rows": location_rows,
            # Which column the table is ordered by, so the header can show the arrow. Only
            # fastq_name is exposed here, not every key `_sorted` accepts: the rest of this
            # table's columns are not asked for as sortable, and offering a link that does
            # nothing useful for them is worse than not offering one.
            "sort": request.GET.get("sort") if request.GET.get("sort") in SORTABLE else DEFAULT_SORT,
            "dir": "asc" if request.GET.get("dir") == "asc" else "desc",
            "columns": columns.visible_location_columns(request.user),
            "all_columns": columns.LOCATION_COLUMNS,
            "column_groups": columns.LOCATION_COLUMN_GROUPS,
            "locked_column": "",
            "default_column_keys": columns.LOCATION_DEFAULT_COLUMNS,
            "visible_column_keys": [column.key for column in columns.visible_location_columns(request.user)],
            "batch_prefixes": _prefix_counts(),
            "selected_prefix": request.GET.get("batch_prefix", ""),
            "search": request.GET.get("fastq_name") or "",
            "studies": _study_options(),
            "selected_studies": request.GET.getlist("study"),
            # Stage.POST_ALIGN's own label is "Post-alignment": overridden here rather than
            # in the model, since changing a TextChoices label needs a migration for what
            # is otherwise only a display string.
            "location_stages": [
                {
                    "value": stage.value,
                    "label": "Post-Alignment" if stage == Stage.POST_ALIGN else stage.label,
                }
                for stage in columns.LOCATION_STAGES
            ],
            "selected_location_stage": selected_location_stage,
            "filters": {field: request.GET.getlist(field) for field in FILTER_FIELDS},
            "stage_filters": stage_filters,
            "batches": _batch_options(request.GET.getlist("batch_name_from_vendor"), scope),
            "organisms": _scoped_distinct(scope, "organism_common_name"),
            "library_preps": _scoped_distinct(scope, "library_prep_method_name"),
            "statuses": [NOT_COMPLETED, *_scoped_statuses(scope)],
            "filters_open": any(request.GET.getlist(field) for field in FILTER_FIELDS)
            or any(row["selected"] for row in stage_filters),
            "active_filter_count": sum(1 for field in FILTER_FIELDS if request.GET.getlist(field))
            + sum(1 for row in stage_filters if row["selected"])
            + bool(request.GET.getlist("study")),
            **_status_sync_context(),
        },
    )


@login_required
@require_POST
def export_data_locations_csv(request):
    """Return the selected or filtered Data Locations rows as CSV."""
    chosen = request.POST.getlist("fastq_names")
    samples = _sorted(_filtered_samples(request), request)
    if chosen:
        samples = samples.filter(fastq_name__in=chosen)

    rows = locations.stage_rows(samples)
    selected_location_stage = request.GET.get("location_stage", "")
    if selected_location_stage in {stage.value for stage in columns.LOCATION_STAGES}:
        rows = [row for row in rows if row["stage"].value == selected_location_stage]

    visible = columns.visible_location_columns(request.user)
    writer = csv.writer(_Echo())
    headers = ["Fastq Name", *(column.label for column in visible), "S3 Location"]

    def csv_text(value) -> str:
        text = "" if value is None else str(value)
        return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text

    def csv_rows():
        yield writer.writerow(headers)
        for row in rows:
            values = []
            for column in visible:
                value = (
                    row["stage"].label
                    if column.key == "stage"
                    else row["status"]
                    if column.key == "status"
                    else row["column_values"].get(column.key, "")
                )
                if isinstance(value, list):
                    value = ", ".join(value)
                values.append(csv_text(value))
            yield writer.writerow([csv_text(row["fastq_name"]), *values, csv_text(row["s3_uri"])])

    response = StreamingHttpResponse(csv_rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{export_csv_filename(data_locations=True)}"'
    return response


@login_required
def data_location_contents(request, sample_id: int, stage: str):
    """List one folder from a stage's registered S3 file store."""
    if stage not in Stage.values:
        raise Http404("Unknown OCS stage")

    record = get_object_or_404(StageStatus, sample_id=sample_id, stage=stage)
    if not record.file_store_id:
        raise Http404("This stage has no file store")

    file_store = dynamodb.get_file_stores([record.file_store_id]).get(record.file_store_id)
    if not file_store or not file_store.get("s3_uri"):
        raise Http404("The file store record has no S3 location")

    prefix = request.GET.get("prefix", "").strip("/")
    token = request.GET.get("continuation_token") or None
    try:
        contents = s3.list_folder(str(file_store["s3_uri"]), prefix, token)
    except (BotoCoreError, ClientError) as error:
        logger.warning("S3 contents lookup failed for sample %s stage %s: %s", sample_id, stage, error)
        return render(
            request,
            "partials/data_location_contents.html",
            {
                "error": "Could not read this S3 location.",
                "s3_uri": file_store["s3_uri"],
            },
            status=502,
        )

    base_url = request.path
    parent_prefix = prefix.rpartition("/")[0]
    folder_links = [
        {
            "name": folder,
            "prefix": "/".join(part for part in (prefix, folder) if part),
            "url": f"{base_url}?{urlencode({'prefix': '/'.join(part for part in (prefix, folder) if part)})}",
        }
        for folder in contents.folders
    ]
    next_url = None
    if contents.next_token:
        next_url = f"{base_url}?{urlencode({'prefix': prefix, 'continuation_token': contents.next_token})}"

    return render(
        request,
        "partials/data_location_contents.html",
        {
            "s3_uri": file_store["s3_uri"],
            "prefix": prefix,
            "folders": folder_links,
            "files": contents.files,
            "next_url": next_url,
            "parent_url": (
                f"{base_url}?{urlencode({'prefix': parent_prefix})}" if parent_prefix else base_url
            )
            if prefix
            else None,
            "refresh_url": f"{base_url}?{urlencode({'prefix': prefix})}" if prefix else base_url,
            "download_url": reverse("web_ui:data-location-download", args=[sample_id, stage]),
        },
    )


@login_required
@require_POST
def download_data_location_files(request, sample_id: int, stage: str):
    """Stream selected S3 files and folders as one ZIP archive."""
    if stage not in Stage.values:
        raise Http404("Unknown OCS stage")

    record = get_object_or_404(StageStatus, sample_id=sample_id, stage=stage)
    sample = record.sample
    if not record.file_store_id:
        raise Http404("This stage has no file store")

    file_store = dynamodb.get_file_stores([record.file_store_id]).get(record.file_store_id)
    if not file_store or not file_store.get("s3_uri"):
        raise Http404("The file store record has no S3 location")

    keys = list(dict.fromkeys(request.POST.getlist("keys")))
    folders = list(dict.fromkeys(request.POST.getlist("folders")))
    if not keys and not folders:
        return JsonResponse({"error": "Select at least one file or folder."}, status=400)
    if len(keys) + len(folders) > DOWNLOAD_SELECTION_LIMIT:
        return JsonResponse(
            {"error": f"Select no more than {DOWNLOAD_SELECTION_LIMIT} files or folders."}, status=400
        )

    selected_keys: list[str] = []
    try:
        for key in keys:
            s3.validate_key(file_store["s3_uri"], key)
            selected_keys.append(key)
        for folder in folders:
            selected_keys.extend(s3.list_files(file_store["s3_uri"], folder))
        selected_keys = list(dict.fromkeys(selected_keys))
        if len(selected_keys) > DOWNLOAD_SELECTION_LIMIT:
            return JsonResponse(
                {"error": f"The selection contains more than {DOWNLOAD_SELECTION_LIMIT} files."},
                status=400,
            )
        if not selected_keys:
            return JsonResponse({"error": "The selected folders contain no files."}, status=400)
    except ValueError:
        return JsonResponse({"error": "One or more selected paths are outside this S3 location."}, status=400)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return JsonResponse({"error": "One or more selected paths are no longer available."}, status=400)
        logger.warning("S3 download authorization failed for sample %s stage %s", sample_id, stage)
        return JsonResponse({"error": "S3 could not read the selected paths."}, status=502)
    except BotoCoreError:
        logger.warning("S3 download authorization failed for sample %s stage %s", sample_id, stage)
        return JsonResponse({"error": "S3 could not read the selected paths."}, status=502)

    def stream_zip() -> Iterator[bytes]:
        output = _ZipOutput()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for key in selected_keys:
                body = s3.get_object_body(file_store["s3_uri"], key)
                try:
                    info = zipfile.ZipInfo(s3.relative_key(file_store["s3_uri"], key))
                    info.compress_type = zipfile.ZIP_STORED
                    with archive.open(info, "w") as target:
                        while chunk := body.read(1024 * 1024):
                            target.write(chunk)
                            yield from output.drain()
                finally:
                    body.close()
        yield from output.drain()

    filename = f"{_archive_part(sample.fastq_name)}-{_archive_part(stage)}.zip"
    response = StreamingHttpResponse(stream_zip(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class _ZipOutput(io.RawIOBase):
    """Collect ZIP writer chunks without buffering the archive."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: deque[bytes] = deque()
        self.position = 0

    def write(self, value: Buffer) -> int:
        chunk = bytes(value)
        self.chunks.append(chunk)
        self.position += len(chunk)
        return len(chunk)

    def tell(self) -> int:
        return self.position

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        return None

    def drain(self) -> Iterator[bytes]:
        while self.chunks:
            yield self.chunks.popleft()


def _archive_part(value: str) -> str:
    """Keep archive names readable while removing unsafe filename characters."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "download"
