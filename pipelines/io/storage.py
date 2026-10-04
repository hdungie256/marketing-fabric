import os


def bucket() -> str:
    return os.environ.get("S3_BUCKET", "lake")


def table_path(dataset_id: str) -> str:
    return f"s3a://{bucket()}/{dataset_id.replace('.', '/')}"


def ensure_bucket() -> None:
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], region_name="us-east-1")
    try:
        s3.head_bucket(Bucket=bucket())
    except ClientError:
        s3.create_bucket(Bucket=bucket())
