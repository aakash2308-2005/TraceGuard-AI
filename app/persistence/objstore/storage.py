"""S3-compatible object storage adapter (MinIO locally).

Stores raw evidence, derived artifacts, and reports. Buckets are created on
first use. Server-side encryption is requested where the backend supports it.
"""

from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings
from app.observability.logging import get_logger

logger = get_logger("objstore")


class ObjectStore:
    """Thin wrapper over an S3-compatible client."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
            config=Config(signature_version="s3v4"),
        )

    def ensure_buckets(self) -> None:
        """Create required buckets if they do not exist."""
        for bucket in (
            self._settings.s3_bucket_evidence,
            self._settings.s3_bucket_reports,
        ):
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                self._client.create_bucket(Bucket=bucket)
                logger.info("bucket_created", bucket=bucket)

    def healthcheck(self) -> None:
        """Raise if the storage backend is not reachable."""
        self._client.list_buckets()

    def put_object(self, bucket: str, key: str, data: bytes, content_type: str) -> str:
        """Store an object and return its storage URI."""
        request = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        # Do not request SSE-S3 unconditionally: local MinIO deployments without
        # a configured KMS reject this header and turn otherwise valid uploads into 500s.
        if self._settings.s3_server_side_encryption:
            request["ServerSideEncryption"] = self._settings.s3_server_side_encryption
        self._client.put_object(**request)
        return f"s3://{bucket}/{key}"

    def get_object(self, bucket: str, key: str) -> bytes:
        """Retrieve an object's bytes."""
        resp = self._client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object."""
        self._client.delete_object(Bucket=bucket, Key=key)

    def presigned_get_url(self, bucket: str, key: str, expires: int = 300) -> str:
        """Return a short-lived presigned download URL."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )


@lru_cache
def get_object_store() -> ObjectStore:
    """Return a cached object-store client."""
    return ObjectStore()
