# ====================== CORPUS TOOLS =====================

import vertexai
from vertexai.preview import rag
from google.adk.tools import FunctionTool
from typing import Dict, Optional, Any, List
from rag.config import (
    PROJECT_ID,
    LOCATION,
    RAG_DEFAULT_EMBEDDING_MODEL,
    RAG_DEFAULT_SEARCH_TOP_K,
    RAG_DEFAULT_TOP_K,
    RAG_DEFAULT_VECTOR_DISTANCE_THRESHOLD,
    RAG_DEFAULT_CHUNK_SIZE,
    RAG_DEFAULT_CHUNK_OVERLAP,
    RAG_DEFAULT_EMBEDDING_REQUESTS_PER_MIN,
)

# initialize vertexai
vertexai.init(project=PROJECT_ID, location=LOCATION)

def create_corpus(
    display_name: str,
    description: Optional[str] = None,
    embedding_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new RAG corpus in Vertex AI.

    Args:
        display_name: A human-readable name for the corpus
        description: Optional description for the corpus
        embedding_model: The embedding model to use (default: configured RAG_DEFAULT_EMBEDDING_MODEL)

    Returns:
        A dictionary containing the created corpus details.
    """
    # Force usage of the configured embedding model, ignoring any Agent-provided value
    # This prevents issues where the Agent hallucinates "ada-002" or includes region prefixes
    embedding_model = RAG_DEFAULT_EMBEDDING_MODEL

    try:
        embedding_model_config = rag.EmbeddingModelConfig(
            publisher_model=embedding_model
        )
        
        corpus = rag.create_corpus(
            display_name=display_name,
            description=description or f"RAG corpus : {display_name}",
            embedding_model_config=embedding_model_config
        )
        
        # Corpus name format: projects/{project}/locations/{location}/ragCorpora/{corpus_id}
        corpus_id = corpus.name.split('/')[-1]
        
        return {
            "status": "success",
            "corpus_id": corpus_id,
            "display_name": display_name,
            "embedding_model": embedding_model, # Return actual used model
            "name": corpus.name,
            "message": f"Successfully created RAG corpus `{display_name}` using model `{embedding_model}`"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to create RAG corpus: {str(e)}"
        }

def update_corpus(
    corpus_id: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates an existing RAG corpus with new display name and/or description.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        # We need to fetch the corpus object first to update it via the SDK object-oriented way
        # OR use the update_corpus method if it accepts ID. 
        # The vertexai SDK usually requires passing the corpus name string or object to update_corpus.
        
        # Ideally:
        # rag.update_corpus(corpus_name=..., display_name=..., description=...)
        
        updated_corpus = rag.update_corpus(
            corpus_name=corpus_name,
            display_name=display_name,
            description=description
        )
        
        return {
            "status": "success",
            "corpus_name": updated_corpus.name,
            "corpus_id": corpus_id,
            "display_name": updated_corpus.display_name,
            "description": updated_corpus.description,
            "message": f"Successfully updated RAG corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to update RAG corpus: {str(e)}"
        }

def list_corpora() -> Dict[str, Any]:
    """
    Lists all RAG corpora in the current project and location.
    """
    try:
        corpora = rag.list_corpora()
        
        corpus_list = []
        for corpus in corpora:
            corpus_id = corpus.name.split('/')[-1]
            
            # Safely get status
            status = "UNKNOWN"
            # Try different attribute paths for compatibility
            if hasattr(corpus, "corpus_status") and hasattr(corpus.corpus_status, "state"):
                status = str(corpus.corpus_status.state)
            
            corpus_list.append({
                "id": corpus_id,
                "name": corpus.name,
                "display_name": corpus.display_name,
                "description": getattr(corpus, "description", None),
                "create_time": str(getattr(corpus, "create_time", "")),
                "status": status
            })
        
        return {
            "status": "success",
            "corpora": corpus_list,
            "count": len(corpus_list),
            "message": f"Found {len(corpus_list)} RAG corpora"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list RAG corpora: {str(e)}"
        }

def get_corpus(corpus_id: str) -> Dict[str, Any]:
    """
    Retrieves details of a specific RAG corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        corpus = rag.get_corpus(name=corpus_name)
        
        files_count = 0
        try:
            # Simple list to count
            files_iter = rag.list_files(corpus_name=corpus_name)
            # rag.list_files returns an iterable, need to convert to list to count
            files_count = len(list(files_iter))
        except:
            pass

        return {
            "status": "success",
            "corpus": {
                "id": corpus_id,
                "name": corpus.name,
                "display_name": corpus.display_name,
                "description": getattr(corpus, "description", None),
                "create_time": str(getattr(corpus, "create_time", "")),
                "files_count": files_count
            },
            "message": f"Successfully retrieved RAG corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to retrieve RAG corpus: {str(e)}"
        }

def delete_corpus(corpus_id: str) -> Dict[str, Any]:
    """
    Deletes a RAG corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        rag.delete_corpus(name=corpus_name)
        return {
            "status": "success",
            "corpus_id": corpus_id,
            "message": f"Successfully deleted RAG corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to delete RAG corpus: {str(e)}"
        }

def import_files(
    corpus_id: str,
    gcs_uris: List[str],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    max_embedding_requests_per_min: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Imports files from Google Cloud Storage into a RAG corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"

        if chunk_size is None:
            chunk_size = RAG_DEFAULT_CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = RAG_DEFAULT_CHUNK_OVERLAP
        if max_embedding_requests_per_min is None:
            max_embedding_requests_per_min = RAG_DEFAULT_EMBEDDING_REQUESTS_PER_MIN

        transformation_config = rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
        )

        response = rag.import_files(
            corpus_name,
            gcs_uris,
            transformation_config=transformation_config,
            max_embedding_requests_per_min=max_embedding_requests_per_min,
        )
        
        imported_count = 0
        failed_count = 0
        skipped_count = 0
        
        if hasattr(response, "imported_rag_files_count"):
             imported_count = response.imported_rag_files_count
        if hasattr(response, "failed_rag_files_count"):
             failed_count = response.failed_rag_files_count
        if hasattr(response, "skipped_rag_files_count"):
             skipped_count = response.skipped_rag_files_count
        
        return {
            "status": "success",
            "imported_count": imported_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "message": f"Successfully initiated import of {len(gcs_uris)} URIs into corpus '{corpus_id}'. Imported: {imported_count}, Failed: {failed_count}, Skipped: {skipped_count}"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to import files: {str(e)}"
        }

def list_files(corpus_id: str) -> Dict[str, Any]:
    """
    Lists files in a RAG corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        files = rag.list_files(corpus_name=corpus_name)
        
        file_list = []
        for f in files:
            file_id = f.name.split('/')[-1]
            file_list.append({
                "id": file_id,
                "name": f.name,
                "display_name": f.display_name,
                "create_time": str(getattr(f, "create_time", ""))
            })
            
        return {
            "status": "success",
            "files": file_list,
            "count": len(file_list),
            "message": f"Found {len(file_list)} files in corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to list files: {str(e)}"
        }

def get_file(corpus_id: str, file_id: str) -> Dict[str, Any]:
    """
    Retrieves details of a specific file in a RAG corpus.
    """
    try:
        # File name format: projects/{project}/locations/{location}/ragCorpora/{corpus}/ragFiles/{file}
        # But SDK usually takes `name` as the full resource name
        file_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}/ragFiles/{file_id}"
        
        f = rag.get_file(name=file_name)
        
        return {
            "status": "success",
            "file": {
                "id": file_id,
                "name": f.name,
                "display_name": f.display_name,
                "create_time": str(getattr(f, "create_time", ""))
            },
            "message": f"Successfully retrieved file '{file_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to get file: {str(e)}"
        }

def delete_file_from_corpus(corpus_id: str, file_id: str) -> Dict[str, Any]:
    """
    Deletes a file from a RAG corpus.
    """
    try:
        file_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}/ragFiles/{file_id}"
        rag.delete_file(name=file_name)
        return {
            "status": "success",
            "file_id": file_id,
            "message": f"Successfully deleted file '{file_id}' from corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to delete file: {str(e)}"
        }

def query_corpus(
    corpus_id: str,
    query: str,
    similarity_top_k: int = RAG_DEFAULT_TOP_K,
    vector_distance_threshold: float = RAG_DEFAULT_VECTOR_DISTANCE_THRESHOLD
) -> Dict[str, Any]:
    """
    Queries a RAG corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=corpus_name)],
            text=query,
            similarity_top_k=similarity_top_k,
            vector_distance_threshold=vector_distance_threshold
        )
        
        results = []
        if hasattr(response, "contexts") and hasattr(response.contexts, "contexts"):
            for ctx in response.contexts.contexts:
                results.append({
                    "text": ctx.text,
                    "source_uri": ctx.source_uri,
                    "distance": ctx.distance
                })
        
        return {
            "status": "success",
            "results": results,
            "count": len(results),
            "message": f"Found {len(results)} results for query"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to query corpus: {str(e)}"
        }

def get_corpus_id_by_display_name(display_name: str) -> Optional[str]:
    """
    Helper: Finds a corpus ID by its display name.
    """
    try:
        corpora = rag.list_corpora()
        for corpus in corpora:
            if corpus.display_name == display_name:
                return corpus.name.split('/')[-1]
        return None
    except:
        return None

def get_file_id_by_name(corpus_id: str, file_display_name: str) -> Optional[str]:
    """
    Helper: Finds a file ID by its display name in a specific corpus.
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        files = rag.list_files(corpus_name=corpus_name)
        for f in files:
            # Check if display name matches OR if the file name ends with the display name (e.g. URI)
            if f.display_name == file_display_name or f.display_name.endswith(file_display_name):
                return f.name.split('/')[-1]
        return None
    except:
        return None

def promote_to_prod():
    # to do
    try:

        pass
    except:
        pass
    pass