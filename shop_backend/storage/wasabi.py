import boto3
from botocore.config import Config

from shop_backend.config import settings


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.WASABI_ENDPOINT_URL,
        region_name=settings.WASABI_REGION,
        aws_access_key_id=settings.WASABI_ACCESS_KEY_ID,
        aws_secret_access_key=settings.WASABI_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_url(storage_key: str, bucket_override: str | None, ttl_seconds: int) -> str:
    client = _get_client()
    bucket = bucket_override or settings.WASABI_BUCKET
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": storage_key},
        ExpiresIn=ttl_seconds,
    )
