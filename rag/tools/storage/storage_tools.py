from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError
from google.adk.tools import ToolContext
from typing import List, Dict, Any, Optional
import logging
import os
from rag.config import (
    PROJECT_ID, 
    LOCATION,
    GCS_DEFAULT_STORAGE_CLASS,
    GCS_DEFAULT_LOCATION,
    LOG_LEVEL,
    LOG_FORMAT
)

# Initialize logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT
)

# Initialize storage client
try:
    client = storage.Client(project=PROJECT_ID)
except Exception as e:
    logging.error(f"Failed to initialize storage client: {e}")
    client = None

def create_gcs_bucket(
    tool_context: ToolContext,
    bucket_name: str,
    storage_class: Optional[str] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new google cloud storage bucket.
    
    Args:
        tool_context: The tool context for ADK
        bucket_name: The name of the bucket to create
        storage_class: Storage class for the bucket (default: STANDARD)
        location: Location for the bucket (default: US)
        
    Returns:
        A dictionary containing the result of bucket creation
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
        
    if storage_class is None:
        storage_class = GCS_DEFAULT_STORAGE_CLASS
    if location is None:
        location = GCS_DEFAULT_LOCATION
        
    try:
        if client.lookup_bucket(bucket_name):
            return {
                "status": "warning", 
                "message": f"Bucket {bucket_name} already exists",
                "bucket_name": bucket_name
            }
            
        bucket = client.bucket(bucket_name)
        bucket.storage_class = storage_class
        new_bucket = client.create_bucket(bucket, location=location)
        
        if hasattr(tool_context, "state"):
            tool_context.state["last_bucket_name"] = bucket_name
            
        return {
            "status": "success",
            "bucket_name": bucket_name,
            "self_link": new_bucket.self_link,
            "location": new_bucket.location,
            "message": f"Successfully created bucket '{bucket_name}' in location '{location}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to create bucket: {str(e)}"
        }

def list_gcs_buckets(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Lists all available buckets in the project.
    
    Args:
        tool_context: The tool context for ADK
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        buckets = list(client.list_buckets())
        bucket_list = [bucket.name for bucket in buckets]
        return {
            "status": "success",
            "buckets": bucket_list,
            "count": len(bucket_list),
            "message": f"Found {len(bucket_list)} buckets."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list buckets: {str(e)}"
        }

def list_blobs(
    tool_context: ToolContext,
    bucket_name: str, 
    prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lists files (blobs) within a specific bucket.
    
    Args:
        tool_context: The tool context for ADK
        bucket_name: Name of the bucket
        prefix: Optional prefix to filter blobs
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
             return {
                "status": "error",
                "message": f"Bucket {bucket_name} does not exist."
            }
            
        blobs = bucket.list_blobs(prefix=prefix)
        file_list = [blob.name for blob in blobs]
        
        if hasattr(tool_context, "state"):
            tool_context.state["last_bucket_name"] = bucket_name

        return {
            "status": "success",
            "files": file_list,
            "count": len(file_list),
            "bucket": bucket_name,
            "message": f"Found {len(file_list)} files in {bucket_name}."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list files in bucket {bucket_name}: {str(e)}"
        }

def upload_file_to_gcs(
    tool_context: ToolContext,
    bucket_name: str, 
    source_file_name: str, 
    destination_blob_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Uploads a local file to a bucket.
    
    Args:
        tool_context: The tool context for ADK
        bucket_name: Name of the destination bucket
        source_file_name: Local path to the file
        destination_blob_name: Optional destination name in GCS
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        bucket = client.bucket(bucket_name)
        if not destination_blob_name:
            destination_blob_name = os.path.basename(source_file_name)
            
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        
        if hasattr(tool_context, "state"):
            tool_context.state["last_uploaded_file"] = f"gs://{bucket_name}/{destination_blob_name}"
        
        return {
            "status": "success",
            "bucket": bucket_name,
            "file": destination_blob_name,
            "gcs_uri": f"gs://{bucket_name}/{destination_blob_name}",
            "message": f"File {source_file_name} uploaded to gs://{bucket_name}/{destination_blob_name}."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to upload file: {str(e)}"
        }

def move_gcs_file(
    tool_context: ToolContext,
    source_bucket_name: str, 
    source_blob_name: str, 
    destination_bucket_name: str, 
    destination_blob_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Moves a file from one bucket to another.
    
    Args:
        tool_context: The tool context for ADK
        source_bucket_name: Source bucket name
        source_blob_name: Source file name
        destination_bucket_name: Destination bucket name
        destination_blob_name: Optional destination file name
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        source_bucket = client.bucket(source_bucket_name)
        source_blob = source_bucket.blob(source_blob_name)
        destination_bucket = client.bucket(destination_bucket_name)
        
        if not destination_blob_name:
            destination_blob_name = source_blob_name

        # Copy to new location
        new_blob = source_bucket.copy_blob(
            source_blob, destination_bucket, destination_blob_name
        )
        
        # Delete from old location
        source_blob.delete()
        
        return {
            "status": "success",
            "source": f"gs://{source_bucket_name}/{source_blob_name}",
            "destination": f"gs://{destination_bucket_name}/{destination_blob_name}",
            "message": f"Moved file from {source_bucket_name} to {destination_bucket_name}."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to move file: {str(e)}"
        }

def delete_gcs_file(
    tool_context: ToolContext,
    bucket_name: str, 
    blob_name: str
) -> Dict[str, Any]:
    """
    Deletes a file from a bucket.
    
    Args:
        tool_context: The tool context for ADK
        bucket_name: Name of the bucket
        blob_name: Name of the file to delete
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
        
        return {
            "status": "success",
            "file": blob_name,
            "bucket": bucket_name,
            "message": f"Deleted {blob_name} from {bucket_name}."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to delete file: {str(e)}"
        }

def delete_gcs_bucket(
    tool_context: ToolContext,
    bucket_name: str,
    force: bool = False
) -> Dict[str, Any]:
    """
    Deletes a GCS bucket.
    
    Args:
        tool_context: The tool context for ADK
        bucket_name: Name of the bucket to delete
        force: If True, deletes all blobs in the bucket before deleting the bucket
    """
    if not client:
        return {"status": "error", "message": "Storage client not initialized."}
    try:
        bucket = client.bucket(bucket_name)
        if force:
            blobs = list(bucket.list_blobs())
            for blob in blobs:
                blob.delete()
        
        bucket.delete()
        
        if hasattr(tool_context, "state") and tool_context.state.get("last_bucket_name") == bucket_name:
            tool_context.state.pop("last_bucket_name", None)
            
        return {
            "status": "success",
            "bucket": bucket_name,
            "message": f"Deleted bucket {bucket_name}."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to delete bucket: {str(e)}"
        }
