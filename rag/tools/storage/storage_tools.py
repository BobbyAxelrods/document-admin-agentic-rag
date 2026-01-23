def list_buckets() -> list[str]:
    """Lists all available buckets (Staging, Prod, Archive)."""
    print("Listing buckets...")
    return ["staging-bucket", "prod-bucket", "archive-bucket"]

def create_bucket(bucket_name: str) -> str:
    """Creates a new GCS bucket (if not already existing)."""
    print(f"Creating bucket: {bucket_name}")
    return f"Bucket {bucket_name} created."

def upload_file(local_path: str, bucket_name: str = "staging") -> str:
    """Uploads a local file to the Staging bucket (entry point)."""
    print(f"Uploading {local_path} to {bucket_name}")
    return f"File {local_path} uploaded to {bucket_name}."

def list_files(bucket_name: str) -> list[str]:
    """Lists files within a specific bucket."""
    print(f"Listing files in {bucket_name}")
    return ["file1.pdf", "file2.pdf"]

def move_file(file_name: str, source_bucket: str, dest_bucket: str) -> str:
    """Moves a file from one bucket to another (e.g., Staging -> Prod)."""
    print(f"Moving {file_name} from {source_bucket} to {dest_bucket}")
    return f"Moved {file_name}."

def delete_file(file_name: str, bucket_name: str) -> str:
    """Deletes a file from a bucket (cleanup)."""
    print(f"Deleting {file_name} from {bucket_name}")
    return f"Deleted {file_name}."
