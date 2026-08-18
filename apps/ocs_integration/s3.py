"""List folders and files under an OCS S3 file-store location."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import boto3
from django.conf import settings


@dataclass(frozen=True)
class FolderContents:
    """Hold one page of folders and files under an S3 prefix."""

    folders: list[str]
    files: list[dict[str, Any]]
    next_token: str | None


_local = threading.local()


def reset_client_cache() -> None:
    """Clear the current thread's cached S3 client."""
    _local.client = None


def _client():
    client = getattr(_local, "client", None)
    if client is None:
        session = boto3.Session(profile_name=settings.AWS_PROFILE or None)
        client = session.client("s3", region_name=settings.OCS_AWS_REGION)
        _local.client = client
    return client


def list_folder(
    s3_uri: str,
    relative_prefix: str = "",
    continuation_token: str | None = None,
    max_keys: int = 100,
) -> FolderContents:
    """List the immediate folders and files under an OCS file-store prefix."""
    bucket, root_prefix = _parse_s3_uri(s3_uri)
    relative_prefix = _validate_relative_prefix(relative_prefix)
    prefix = root_prefix + relative_prefix
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    request: dict[str, Any] = {
        "Bucket": bucket,
        "Prefix": prefix,
        "Delimiter": "/",
        "MaxKeys": max_keys,
    }
    if continuation_token:
        request["ContinuationToken"] = continuation_token

    response = _client().list_objects_v2(**request)
    folders = [item["Prefix"][len(prefix) :].rstrip("/") for item in response.get("CommonPrefixes", [])]
    files = [
        {
            "name": item["Key"][len(prefix) :],
            "key": item["Key"],
            "size": item["Size"],
            "last_modified": item["LastModified"],
        }
        for item in response.get("Contents", [])
        if item["Key"] != prefix
    ]
    return FolderContents(
        folders=folders,
        files=files,
        next_token=response.get("NextContinuationToken"),
    )


def list_files(s3_uri: str, relative_prefix: str = "") -> Iterator[str]:
    """Yield every object below a registered S3 folder."""
    bucket, root_prefix = _parse_s3_uri(s3_uri)
    prefix = root_prefix + _validate_relative_prefix(relative_prefix)
    paginator = _client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key != prefix:
                yield key


def get_object_body(s3_uri: str, key: str):
    """Open one object below a registered S3 location for streaming."""
    bucket, root_prefix = _parse_s3_uri(s3_uri)
    _validate_key(key, root_prefix)
    return _client().get_object(Bucket=bucket, Key=key)["Body"]


def validate_key(s3_uri: str, key: str) -> None:
    """Check that an S3 key stays below a registered file-store location."""
    _, root_prefix = _parse_s3_uri(s3_uri)
    _validate_key(key, root_prefix)


def relative_key(s3_uri: str, key: str) -> str:
    """Return an object's path relative to its registered file-store location."""
    _, root_prefix = _parse_s3_uri(s3_uri)
    _validate_key(key, root_prefix)
    return key[len(root_prefix) :]


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected an s3:// URI, got {s3_uri!r}")
    root_prefix = parsed.path.lstrip("/")
    if root_prefix and not root_prefix.endswith("/"):
        root_prefix += "/"
    return parsed.netloc, root_prefix


def _validate_relative_prefix(relative_prefix: str) -> str:
    relative_prefix = relative_prefix.strip("/")
    if any(part in {".", ".."} for part in relative_prefix.split("/")):
        raise ValueError("S3 folder paths cannot contain '.' or '..'")
    return f"{relative_prefix}/" if relative_prefix else ""


def _validate_key(key: str, root_prefix: str) -> None:
    if not key or not key.startswith(root_prefix):
        raise ValueError("The file is outside the registered S3 location")
    relative_key = key[len(root_prefix) :]
    if any(part in {".", ".."} for part in relative_key.split("/")):
        raise ValueError("S3 file paths cannot contain '.' or '..'")
