from datetime import UTC, datetime

from django.test import override_settings

from apps.ocs_integration import s3


class FakeS3Client:
    def __init__(self):
        self.requests = []
        self.head_requests = []
        self.presign_requests = []

    def list_objects_v2(self, **kwargs):
        self.requests.append(kwargs)
        return {
            "CommonPrefixes": [{"Prefix": "results/counts/"}],
            "Contents": [
                {
                    "Key": "results/summary.csv",
                    "Size": 12,
                    "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
                }
            ],
            "NextContinuationToken": "next-page",
        }

    def head_object(self, **kwargs):
        self.head_requests.append(kwargs)
        return {"ContentLength": 12}

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.presign_requests.append((operation, Params, ExpiresIn))
        return "https://example.test/download"


@override_settings(AWS_PROFILE="omicshub", OCS_AWS_REGION="us-west-2")
def test_lists_only_the_current_s3_folder(monkeypatch):
    client = FakeS3Client()
    monkeypatch.setattr(
        s3.boto3,
        "Session",
        lambda profile_name=None: type("Session", (), {"client": lambda self, name, region_name: client})(),
    )
    s3.reset_client_cache()

    result = s3.list_folder("s3://bucket/results", "")

    assert result.folders == ["counts"]
    assert result.files[0]["name"] == "summary.csv"
    assert result.next_token == "next-page"
    assert client.requests[0] == {
        "Bucket": "bucket",
        "Prefix": "results/",
        "Delimiter": "/",
        "MaxKeys": 100,
    }


def test_rejects_parent_folder_paths():
    try:
        s3.list_folder("s3://bucket/results", "../other")
    except ValueError as error:
        assert "'.' or '..'" in str(error)
    else:
        raise AssertionError("parent folder path was accepted")


def test_rejects_a_file_outside_the_registered_location():
    try:
        s3.validate_key("s3://bucket/results", "other/summary.csv")
    except ValueError as error:
        assert "outside" in str(error)
    else:
        raise AssertionError("a file outside the registered location was accepted")
