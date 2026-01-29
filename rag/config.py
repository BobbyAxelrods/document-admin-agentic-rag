"""
Configuration settings for the Vertex AI RAG engine.
"""

# Google Cloud Project Settings
PROJECT_ID = "prudential-poc-484904"  # Replace with your project ID
LOCATION = "asia-east1"  # Default location for Vertex AI resources use GA 
AGENT_NAME = "pru-rag-admin"
INSTANCE_CONNECTION_NAME = "prudential-poc-484904:asia-east1:file-metadata"

# GCS Storage Settings
GCS_DEFAULT_STORAGE_CLASS = "STANDARD"
GCS_DEFAULT_LOCATION = "ASIA"
GCS_LIST_BUCKETS_MAX_RESULTS = 50
GCS_LIST_BLOBS_MAX_RESULTS = 100

# Bucket Names
STAGING_BUCKET_NAME = f"pru-rag-staging-{PROJECT_ID}"
PROD_BUCKET_NAME = f"pru-rag-prod-{PROJECT_ID}"
ARCHIVE_BUCKET_NAME = f"pru-rag-archive-{PROJECT_ID}"
EVAL_BUCKET_NAME =  f"pru-rag-eval-{PROJECT_ID}"

# RAG Corpus Settings
RAG_DEFAULT_EMBEDDING_MODEL = "publishers/google/models/text-embedding-005"
RAG_DEFAULT_TOP_K = 10
RAG_DEFAULT_SEARCH_TOP_K = 5
RAG_DEFAULT_VECTOR_DISTANCE_THRESHOLD = 0.5
RAG_DEFAULT_CHUNK_SIZE = 512
RAG_DEFAULT_CHUNK_OVERLAP = 100
RAG_DEFAULT_EMBEDDING_REQUESTS_PER_MIN = 1000

# Corpus Names
STAGING_CORPUS_DISPLAY_NAME = "pru-rag-staging-corpus"
PROD_CORPUS_DISPLAY_NAME = "pru-rag-prod-corpus"

# Logging Settings
LOG_LEVEL = "INFO" 
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
AGENT_OUTPUT_KEY = "last_response"


