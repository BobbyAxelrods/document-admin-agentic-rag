"""
Configuration settings for the Vertex AI RAG engine.
"""

# Google Cloud Project Settings
PROJECT_ID = "prudential-poc-484904"  # Replace with your project ID
LOCATION = "asia-east1"  # Default location for Vertex AI resources use GA 
AGENT_NAME = "pru-rag-admin"

# GCS Storage Settings
GCS_DEFAULT_STORAGE_CLASS = "STANDARD"
GCS_DEFAULT_LOCATION = "ASIA"
GCS_LIST_BUCKETS_MAX_RESULTS = 50
GCS_LIST_BLOBS_MAX_RESULTS = 100

# RAG Corpus Settings
RAG_DEFAULT_EMBEDDING_MODEL = "publishers/google/models/text-embedding-005" # Simplified model name
RAG_DEFAULT_TOP_K = 10  # Default number of results for single corpus query
RAG_DEFAULT_SEARCH_TOP_K = 5  # Default number of results per corpus for search_all
RAG_DEFAULT_VECTOR_DISTANCE_THRESHOLD = 0.5

# Logging Settings
LOG_LEVEL = "INFO" 
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
AGENT_OUTPUT_KEY = "last_response"
