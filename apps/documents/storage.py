"""Private MinIO adapter used by signatures and final documents."""

from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from minio import Minio
from minio.error import MinioException, S3Error
from urllib3.exceptions import HTTPError


class PrivateStorageError(RuntimeError):
    """Safe boundary for object-storage connection failures."""


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    version_id: str | None
    content_type: str
    size: int


def _client():
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket(client):
    if not client.bucket_exists(settings.MINIO_BUCKET):
        try:
            client.make_bucket(settings.MINIO_BUCKET)
        except S3Error as error:
            if error.code not in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                raise


def store_private_object(*, object_key, content, content_type):
    try:
        client = _client()
        _ensure_bucket(client)
        result = client.put_object(
            settings.MINIO_BUCKET,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
    except (MinioException, HTTPError, OSError) as error:
        raise PrivateStorageError(
            "Private object storage tidak dapat diakses."
        ) from error
    return StoredObject(
        object_key=object_key,
        version_id=result.version_id,
        content_type=content_type,
        size=len(content),
    )


def stat_private_object(object_key):
    try:
        item = _client().stat_object(settings.MINIO_BUCKET, object_key)
    except (MinioException, HTTPError, OSError) as error:
        raise PrivateStorageError(
            "Private object storage tidak dapat diakses."
        ) from error
    return StoredObject(
        object_key=object_key,
        version_id=item.version_id,
        content_type=item.content_type,
        size=item.size,
    )


def read_private_object(object_key):
    try:
        response = _client().get_object(
            settings.MINIO_BUCKET, object_key
        )
    except (MinioException, HTTPError, OSError) as error:
        raise PrivateStorageError(
            "Private object storage tidak dapat diakses."
        ) from error
    try:
        try:
            return response.read()
        except (MinioException, HTTPError, OSError) as error:
            raise PrivateStorageError(
                "Private object storage tidak dapat diakses."
            ) from error
    finally:
        response.close()
        response.release_conn()
