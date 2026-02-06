from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

import boto3
from botocore.client import Config

logger = logging.getLogger("knoweasy-engine-api")


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v.strip()


@lru_cache(maxsize=1)
def get_r2_client():
    """Return an S3-compatible client for Cloudflare R2."""
    endpoint = _env("R2_ENDPOINT")
    access_key = _env("R2_ACCESS_KEY_ID")
    secret_key = _env("R2_SECRET_ACCESS_KEY")

    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("R2 config missing: set R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")

    # R2 uses S3-compatible API with SigV4. Region is 'auto'.
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=_env("R2_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def get_bucket_name() -> str:
    bucket = _env("R2_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("R2_BUCKET_NAME not set")
    return bucket


def presign_get_object(object_key: str, expires_in: Optional[int] = None) -> str:
    if not object_key:
        raise RuntimeError("object_key required")
    exp = expires_in
    if exp is None:
        exp = int(_env("R2_SIGNED_URL_EXP_SECONDS", "120"))
    client = get_r2_client()
    bucket = get_bucket_name()
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=exp,
    )
