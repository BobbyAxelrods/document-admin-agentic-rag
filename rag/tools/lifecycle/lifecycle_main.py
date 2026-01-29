import os 
import hashlib
import json
import io
from typing import Any, Optional, List, Dict
import pandas as pd 
import datetime
import pg8000
from google.cloud.sql.connector import Connector, IPTypes
import logging
from google.cloud import storage
from google.adk.tools import FunctionTool, ToolContext
import litellm
import sys
from google.cloud.sql.connector import Connector, IPTypes
from dotenv import load_dotenv

# Import corpus tools
from rag.tools.corpus.corpus_tools import (
    get_corpus_id_by_display_name,
    query_corpus,
    import_files,
    delete_file_from_corpus,
    create_corpus,
    delete_corpus,
    list_corpora,
    list_files
)
from rag.tools.storage.storage_tools import create_gcs_bucket, list_blobs
from rag.config import (
    PROJECT_ID, 
    LOCATION, 
    INSTANCE_CONNECTION_NAME,
    STAGING_BUCKET_NAME,
    PROD_BUCKET_NAME,
    ARCHIVE_BUCKET_NAME,
    EVAL_BUCKET_NAME,
    STAGING_CORPUS_DISPLAY_NAME,
    PROD_CORPUS_DISPLAY_NAME
)

# Logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)



# ===================== #
# ### database tools debug and test 
# ===================== #

def test_connection():
    try: 
        print("Attempting connecting database Cloud SQL ")

        connector = Connector()
        def getconn() -> pg8000.dbapi.Connection:
            conn: pg8000.Connection = connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                ip_type = IPTypes.PUBLIC,
            )
            return conn

        conn = getconn()
        print("SUCESS : Connected to database ")
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
            
            """)
            tables = cur.fetchall()
            print(f"Existing tables: {[t[0] for t in tables]}")
        finally:
            cur.close()
        
        conn.close()
        connector.close()
    except Exception as e: 
        print(f"")

# ===================== #
# ### utils for lifecycle 
# ===================== #

# Constants (Imported from config)

# Initialize Storage Client
try:
    storage_client = storage.Client(project=PROJECT_ID)
except Exception as e:
    logger.error(f"Failed to initialize storage client: {e}")
    storage_client = None

#  Cloud SQL Configuration 
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres") 
DB_NAME = os.getenv("DB_NAME", "rag_metadata")
# Note: INSTANCE_CONNECTION_NAME is imported from config

def test_db_connection() -> Dict[str, Any]:
    """
    Quick DB connectivity test using the Cloud SQL Python Connector (pg8000).
    Returns a dict with status and optional details for diagnostics.
    """
    try:
        connector = Connector()
        conn: pg8000.dbapi.Connection = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC,
        )
        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1;")
                one = cur.fetchone()
                return {
                    "status": "success",
                    "message": "DB connection OK",
                    "result": one[0] if one else None
                }
            finally:
                cur.close()
        finally:
            conn.close()
            connector.close()
    except Exception as e:
        logger.error(f"DB connection test failed: {e}")
        return {"status": "error", "message": str(e)}

def get_connection():
    """
    Establish connection in cloud SQL instaces using the Python Connector
    """
    try:
        # initialize Connector object
        connector = Connector()

        def getconn() -> pg8000.dbapi.Connection:
            conn: pg8000.dbapi.Connection = connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                ip_type=IPTypes.PUBLIC,  # Use public IP as requested
                timeout=30 
            )
            return conn

        # Create connection using the connector
        conn = getconn()
        return conn 

    except Exception as e:
        logger.error(f"failed to connect to DB: {e}")
        raise e

# Create Table if not any 
def init_file_metadata_sql_table():
    create_file_table = """
            CREATE TABLE IF NOT EXISTS file_metadata (
            -- Primary Identity
            id TEXT PRIMARY KEY,                    -- hash (content or filename, your choice)
            text_filename VARCHAR(255) NOT NULL,    -- Original filename (e.g., "user-manual.pdf")
            stored_filename VARCHAR(255) NOT NULL,  -- GCS object name (e.g., "doc_id/v20260127__hash.pdf")
            
            -- Versioning
            version BIGINT NOT NULL,                   -- Version number per text_filename
            upload_date DATE NOT NULL,              -- Upload date (YYYY-MM-DD)
            
            -- File Properties
            format VARCHAR(50),                     -- File extension (pdf, docx, txt)
            file_size_bytes BIGINT,
            
            -- Status Tracking
            status VARCHAR(20) NOT NULL 
                CHECK (status IN ('STAGED','PRODUCTION','ARCHIVE','FAILED')),
            validation_status VARCHAR(20) 
                DEFAULT 'PENDING'
                CHECK (validation_status IN ('PENDING','PASS','FAIL')),
            next_action VARCHAR(50),                -- e.g. INGEST_TO_PROD, MANUAL_REVIEW
            
            -- Location (Which bucket/corpus)
            bucket_status VARCHAR(50),              -- staging, production-v1, production-v2, archive
            bucket_path TEXT,                       -- Full GCS path (gs://...)
            corpus_name VARCHAR(100),               -- Corpus name
            
            -- Audit Trail
            uploaded_by VARCHAR(100),
            uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            promoted_at TIMESTAMP,
            archived_at TIMESTAMP,
            
            -- Relationships (Version Chain)
            superseded_by TEXT,
            supersedes TEXT,
            
            CONSTRAINT fk_superseded_by FOREIGN KEY (superseded_by) REFERENCES file_metadata(id),
            CONSTRAINT fk_supersedes FOREIGN KEY (supersedes) REFERENCES file_metadata(id),
            
            -- Ensure one version number per base filename
            CONSTRAINT ux_filename_version UNIQUE (text_filename, version)
        );

        -- Helpful indexes
        CREATE INDEX IF NOT EXISTS ix_file_status ON file_metadata(status, validation_status);
        CREATE INDEX IF NOT EXISTS ix_file_bucket ON file_metadata(bucket_status);
        CREATE INDEX IF NOT EXISTS ix_file_corpus ON file_metadata(corpus_name);
        CREATE INDEX IF NOT EXISTS ix_file_uploaded_at ON file_metadata(uploaded_at);
    """
    conn = None 
    try: 
        conn= get_connection()
        cur = conn.cursor()
        try:
            cur.execute(create_file_table)
        finally:
            cur.close()
        conn.commit()
        logger.info("Metadata table initialized successfully")
    except Exception as e: 
        logger.error(f"Error initializing table : {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def init_buckets_sql_table():
    """Initializes the buckets table."""
    create_buckets_table = """
        CREATE TABLE IF NOT EXISTS buckets (
            bucket_name VARCHAR(255) PRIMARY KEY,
            bucket_type VARCHAR(50) NOT NULL CHECK (bucket_type IN ('STAGING', 'PRODUCTION', 'ARCHIVE')),
            region VARCHAR(50) DEFAULT 'US',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS ix_bucket_type ON buckets(bucket_type);
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(create_buckets_table)
        finally:
            cur.close()
        conn.commit()
        logger.info("Buckets table initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing buckets table: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def register_bucket_metadata(bucket_name: str, bucket_type: str, region: str = "US", description: str = ""):
    """Upserts bucket metadata."""
    sql = """
        INSERT INTO buckets (bucket_name, bucket_type, region, description)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (bucket_name) DO UPDATE SET
            bucket_type = EXCLUDED.bucket_type,
            region = EXCLUDED.region,
            description = EXCLUDED.description,
            is_active = TRUE;
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(sql, (bucket_name, bucket_type, region, description))
        finally:
            cur.close()
        conn.commit()
        logger.info(f"Registered bucket {bucket_name} metadata")
    except Exception as e:
        logger.error(f"Error registering bucket metadata: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def initialize_infrastructure(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Initializes the entire lifecycle infrastructure:
    1. Creates SQL tables (file_metadata, buckets).
    2. Ensures GCS buckets exist (Staging, Prod, Archive).
    3. Registers buckets in SQL.
    """
    # 1. SQL Tables
    init_file_metadata_sql_table()
    init_buckets_sql_table()
    
    # 2. GCS Buckets & Registration
    buckets_config = [
        {"name": STAGING_BUCKET_NAME, "type": "STAGING", "desc": "Staging area for new documents"},
        {"name": PROD_BUCKET_NAME, "type": "PRODUCTION", "desc": "Production documents serving the RAG corpus"},
        {"name": ARCHIVE_BUCKET_NAME, "type": "ARCHIVE", "desc": "Archived versions of documents"},
        {"name": EVAL_BUCKET_NAME, "type": "PRODUCTION", "desc": "Evaluation results bucket"}
    ]
    
    report = []
    
    for b_conf in buckets_config:
        # Create/Ensure GCS Bucket
        # storage_tools.create_gcs_bucket handles "exists" check gracefully
        res = create_gcs_bucket(tool_context, b_conf["name"], location=LOCATION)
        status = res.get("status")
        msg = res.get("message")
        
        # Register in SQL
        register_bucket_metadata(
            bucket_name=b_conf["name"],
            bucket_type=b_conf["type"],
            region=LOCATION,
            description=b_conf["desc"]
        )
        
        report.append({
            "bucket": b_conf["name"],
            "status": status,
            "message": msg,
            "registered_in_db": "yes"
        })
        
    # 3. RAG Corpora
    corpora_config = [
        {"display_name": PROD_CORPUS_DISPLAY_NAME, "desc": "Production RAG Corpus"},
        {"display_name": STAGING_CORPUS_DISPLAY_NAME, "desc": "Staging RAG Corpus"}
    ]

    for c_conf in corpora_config:
        # Check if exists
        cid = get_corpus_id_by_display_name(c_conf["display_name"])
        if not cid:
            res = create_corpus(display_name=c_conf["display_name"], description=c_conf["desc"])
            status = res.get("status")
            msg = res.get("message")
        else:
            status = "exists"
            msg = f"Corpus '{c_conf['display_name']}' already exists (ID: {cid})"
            
        report.append({
            "corpus": c_conf["display_name"],
            "status": status,
            "message": msg
        })
        
    return {
        "status": "success",
        "message": "Infrastructure initialized successfully.",
        "details": report
    }

def upsert_file_metadata(
    id: str,
    text_filename: str,
    stored_filename: str,
    version: int,
    upload_date: str, # YYYY-MM-DD
    format: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    status: str = 'STAGED',
    validation_status: str = 'PENDING',
    next_action: Optional[str] = None,
    bucket_status: Optional[str] = None,
    bucket_path: Optional[str] = None,
    corpus_name: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    superseded_by: Optional[str] = None,
    supersedes: Optional[str] = None
    ):
    """
    Inserts or updates document metadata in Cloud SQL (file_metadata table).
    """

    sql_upsert = """
    INSERT INTO file_metadata (
        id, text_filename, stored_filename, version, upload_date,
        format, file_size_bytes, status, validation_status, next_action,
        bucket_status, bucket_path, corpus_name, uploaded_by,
        superseded_by, supersedes
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s
    )
    ON CONFLICT (id) DO UPDATE
    SET 
        status = EXCLUDED.status,
        validation_status = EXCLUDED.validation_status,
        next_action = EXCLUDED.next_action,
        bucket_status = EXCLUDED.bucket_status,
        bucket_path = EXCLUDED.bucket_path,
        corpus_name = EXCLUDED.corpus_name,
        promoted_at = CASE WHEN EXCLUDED.status = 'PRODUCTION' AND file_metadata.status != 'PRODUCTION' THEN CURRENT_TIMESTAMP ELSE file_metadata.promoted_at END,
        archived_at = CASE WHEN EXCLUDED.status = 'ARCHIVE' AND file_metadata.status != 'ARCHIVE' THEN CURRENT_TIMESTAMP ELSE file_metadata.archived_at END,
        superseded_by = EXCLUDED.superseded_by,
        supersedes = EXCLUDED.supersedes;
    """
    conn = None 
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(sql_upsert, (
                id, text_filename, stored_filename, version, upload_date,
                format, file_size_bytes, status, validation_status, next_action,
                bucket_status, bucket_path, corpus_name, uploaded_by,
                superseded_by, supersedes
            ))
        finally:
            cur.close()
        conn.commit()
        logger.info(f"Metadata upserted for file_id: {id}")
    except Exception as e:
        logger.error(f"Error upserting metadata: {e}")
        if conn:
            conn.rollback()
        raise e

    finally:
        if conn:
            conn.close()



# Calculate sha256 specific for filename only 
## make sure to inform user if file is updated , use base filename
def _calculate_hash(file_path: str)-> str:
    """
    Calculate sha 256 has of the filename (path string)
    """

    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    hashname = hashlib.sha256()
    hashname.update(file_path.encode("utf-8"))
    return hashname.hexdigest()

# get bucket 

def _get_bucket_gcs(bucket_name:str):
    """
    Ensure bucket exists, create if not. 
    """
    try:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            # use tools to create it with correct region 
            # we use simplified creation here or call the tool 
            # calling the SDK directly for simplicity in helper 
            bucket.create(location=LOCATION.split('-')[0].upper())
        return bucket
    except Exception as e:
        logger.error(f"Error accessing bucket {bucket_name}: {e}")
        return None 

# ingest in staging 
def ingest_document(
    file_path:str,
    doc_id:str,
    version: Optional[str]
) -> Dict[str,Any]:
    """
    Phase 1 : Ingestion Stage 

    1. Validate files
    2. Compute filename hash , detection via filename 
    3. Upload to staging bucket
    4. Set initial state
    5. set the medata in sql db  

    """

    try: 
        if not os.path.exists(file_path):
            return {"status": "Error", "message": f"File not found: {file_path}"}

        if not version:
            version = datetime.datetime.now().strftime("v%Y%m%d%H%M")

        filename_hash = _calculate_hash(file_path)
        file_ext = os.path.splitext(file_path)[1]
        
        # We need content hash too if we want to track duplicates properly, but for now we use filename hash
        content_hash = filename_hash # Placeholder

        # generate hashing gcs path : {version}/{filename}
        # User requested to use original filename only (no hash in path)
        
        base_filename = os.path.basename(file_path)
        blob_name = f"{version}/{base_filename}"

        # ensure staging bucket
        bucket = _get_bucket_gcs(STAGING_BUCKET_NAME)

        if not bucket:
            return {"status": "error", "message": f"Could not access staging bucket {STAGING_BUCKET_NAME}" }
        

        blob = bucket.blob(blob_name)
        if blob.exists():
            return {"status": "warning", "message": f"Document already staged: {blob_name}"}

        # 4. upload file here
        blob.upload_from_filename(file_path)
        
        # Verify upload
        if not blob.exists():
             return {"status": "error", "message": f"Upload failed for {blob_name} in {STAGING_BUCKET_NAME}"}



        # 5 Set Metadata 
        blob.metadata = {
            "doc_id" : doc_id,
            "version" : version,
            "content_hash" : content_hash,
            "staged" : "staged",
            "upload_timestamp" : datetime.datetime.now().isoformat()
        }

        # update blob metadata 
        blob.patch()
        
        # Upsert into DB (Basic Staged Status)
        # Note: version needs to be int for the schema we defined, but here it's string vYYYY...
        # Let's parse version or change schema. Schema says INT. 
        # For simplicity, let's use timestamp as int or just 1 for now.
        # Assuming version is YYYYMMDDHHMM
        try:
            version_int = int(version.replace("v",""))
        except:
            version_int = 1

        upsert_file_metadata(
            # id=doc_id, # Using doc_id as primary key might be an issue if we have multiple versions? 
                       # Schema says id TEXT PRIMARY KEY.
                       # If doc_id is hash of filename, it's unique per filename.
                       # But we want multiple versions.
                       # Actually, the schema has `ux_filename_version UNIQUE (text_filename, version)`.
                       # The `id` field should probably be `doc_id` + `version`.
            id=f"{doc_id}_{version}", 
            text_filename=os.path.basename(file_path),
            stored_filename=blob_name,
            version=version_int,
            upload_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            format=file_ext.replace(".",""),
            file_size_bytes=os.path.getsize(file_path),
            status='STAGED',
            validation_status='PENDING',
            bucket_status='staging',
            bucket_path=f"gs://{STAGING_BUCKET_NAME}/{blob_name}"
        )

        return {
            "status": "success",
            "doc_id" : doc_id ,
            "version" : version ,
            "gcs_url" : f"gs://{STAGING_BUCKET_NAME}/{blob_name}",
            "message" : f"Document staged successfully : {blob_name}" 
        }

    except Exception as e:
        return {"status": "error", "message": f"Ingestion failed: {str(e)}"}

def _evaluate_with_llm(query: str, response: str, ground_truth: str) -> Dict[str, Any]:
    """
    Evaluates RAG response against ground truth using LiteLLM (matching Agent's config).
    """
    try:
        model_name = os.getenv("AZURE", "azure/gpt-4o")
        
        prompt = f"""
        You are an expert evaluator for RAG systems.
        
        Query: {query}
        Generated Response (Retrieved Context): {response}
        Ground Truth: {ground_truth}
        
        Task:
        1. Compare the Generated Response with the Ground Truth.
        2. Assign a score between 0.0 and 1.0 (1.0 being perfect match in meaning).
        3. Provide a brief reason.
        
        Output JSON format:
        {{
            "score": float,
            "reason": "string"
        }}
        """
        
        completion = litellm.completion(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"score": 0.0, "reason": f"Evaluation failed: {str(e)}"}

# =================MAIN PROCESS =====================
# =================MAIN PROCESS =====================

def phase_1_upload_and_ingest(
    tool_context: ToolContext,
    files: List[str],
    doc_ids: Optional[List[str]] = None
) -> Dict[str,Any]:

    results = []
    # Ensure DB is reachable before proceeding, so metadata operations won't silently fail
    db_check = test_db_connection()
    if db_check.get("status") != "success":
        return {"status": "error", "message": f"Database connectivity check failed: {db_check.get('message')}"}
    # validate 
    for idx, file_path in enumerate(files):
        if not os.path.exists(file_path):
            results.append({"status":"error","file": file_path,"message": "File Not Found"})
            continue

        # validate files type

        extension = os.path.splitext(file_path)[1].lower()
        if extension not in [".pdf",".txt",".docx",".md"]:
            results.append({"status":"error","file": file_path,"message":f"Unsupported format : {extension}"})

        doc_id = _calculate_hash(file_path)

        # add content hash here if needed , now make it simple and fast 

        # ingest document here 
        ingesting = ingest_document(file_path=file_path, doc_id=doc_id, version = None)
        results.append({**ingesting, "doc_id":doc_id})
    return {"status": "success", "project_id": PROJECT_ID, "items": results}



def phase_2_regression_test_xlsx(
    tool_context : ToolContext,
    candidate_corpus: str,
    excel_path:str,

) -> Dict[str,Any]:

    """
    Plan:

    1. Read the Excel file using pandas .
    2. Iterate through the rows.
    3. For each row, execute a RAG query using query_corpus .
    4.  Compare the result with the ground truth using an LLM as a judge ().
    5. Update the pandas DataFrame with the results (RAG response, Score, Pass/Fail status).
    6. Return the final DataFrame (as a dict/list of records) and summary statistics.

    """

    # Read Excel 
    df = pd.read_excel(excel_path)
    # get cols query 
    cols = [str(c).lower().strip() for c in df.columns]
    df.columns = cols

    # Identify columns (flexible)
    query_col = next((c for c in df.columns if c in ['query', 'question', 'input']), df.columns[0])
    truth_col = next((c for c in df.columns if c in ['ground_truth', 'answer', 'expected', 'truth']), None)

    # Resolve Corpus ID
    corpus_id = candidate_corpus
    resolved_id = get_corpus_id_by_display_name(candidate_corpus)
    if resolved_id:
        corpus_id = resolved_id

    # Check if corpus has files
    files_res = list_files(corpus_id)
    if files_res.get("status") != "success":
        return {
             "status": "error", 
             "message": f"Failed to list files for corpus {candidate_corpus} (ID: {corpus_id}): {files_res.get('message')}"
         }

    if not files_res.get("files"):
         return {
             "status": "error", 
             "message": f"Corpus {candidate_corpus} (ID: {corpus_id}) is empty. Please ensure 'create_candidate_corpus' completed successfully and files were imported."
         }

    # Loop and Validate
    total_score = 0
    pass_count = 0
    evaluated_rows = []

    # Setup for continuous save
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    date_folder = datetime.datetime.now().strftime("%Y-%m-%d")
    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    
    # Define temporary and final paths
    temp_blob_path = f"temp_processing/{base_name}_{timestamp}_working.xlsx"
    final_blob_path = f"eval_results/{date_folder}/{base_name}_results_{timestamp}.xlsx"

    # Helper to save current progress to GCS
    def save_progress_to_gcs(current_rows, blob_path, is_temp=True):
        if not storage_client: return
        try:
            temp_df = pd.DataFrame(current_rows)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                temp_df.to_excel(writer, index=False)
            output_bytes = output.getvalue()
            
            bucket = storage_client.bucket(EVAL_BUCKET_NAME)
            blob = bucket.blob(blob_path)
            blob.upload_from_string(
                data=output_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            if not is_temp:
                logger.info(f"Saved results to gs://{EVAL_BUCKET_NAME}/{blob_path}")
        except Exception as e:
            logger.warning(f"Failed to save progress to {blob_path}: {e}")

    # 1. Upload initial file to temp location
    try:
        if storage_client:
            bucket = storage_client.bucket(EVAL_BUCKET_NAME)
            if not bucket.exists():
                create_gcs_bucket(tool_context=tool_context, bucket_name=EVAL_BUCKET_NAME, location=LOCATION)
            
            # Read bytes from local file
            with open(excel_path, "rb") as f:
                bucket.blob(temp_blob_path).upload_from_file(f)
            logger.info(f"Uploaded working copy to gs://{EVAL_BUCKET_NAME}/{temp_blob_path}")
    except Exception as e:
        logger.warning(f"Failed to upload initial working copy: {e}")
    
    try:
        for index, row in df.iterrows():
            query_text = str(row[query_col])
            # Use the identified truth column, but keep strict N/A handling for evaluation
            ground_truth = str(row[truth_col]) if truth_col and truth_col in df.columns else "N/A"
            if ground_truth.lower() == 'nan': ground_truth = "N/A"
            
            # Query RAG
            rag_result = query_corpus(corpus_id=corpus_id, query=query_text)
            
            response_text = "No response"
            if rag_result.get("status") == "success":
                 if "results" in rag_result and rag_result["results"]:
                     response_text = "\n\n".join([r.get("text", "") for r in rag_result["results"][:3]])
            
            # Evaluate
            eval_result = _evaluate_with_llm(query_text, response_text, ground_truth)
            score = eval_result.get("score", 0.0)
            
            is_pass = score >= 0.7
            if is_pass: pass_count += 1
            total_score += score
            
            # Construct Output Row:
            # 1. Start with original row data to preserve structure and values
            out_row = row.to_dict()
            
            # 2. Append new results columns
            out_row['rag_response'] = response_text[:1000] + "..." if len(response_text) > 1000 else response_text
            out_row['score'] = score
            out_row['status'] = "PASS" if is_pass else "FAIL"
            out_row['reason'] = eval_result.get("reason", "")
            out_row['row_id'] = index + 1
            
            evaluated_rows.append(out_row)

            # Checkpoint every 5 rows
            if (index + 1) % 5 == 0:
                save_progress_to_gcs(evaluated_rows, temp_blob_path, is_temp=True)

    except Exception as e:
        logger.error(f"Regression test interrupted: {e}")
        # Try to save whatever we have so far
        save_progress_to_gcs(evaluated_rows, temp_blob_path, is_temp=True)
        return {
            "status": "error", 
            "message": f"Regression test failed/interrupted: {str(e)}", 
            "partial_results_uri": f"gs://{EVAL_BUCKET_NAME}/{temp_blob_path}"
        }

    avg_score = total_score / len(df) if len(df) > 0 else 0
    failures = [r["row_id"] for r in evaluated_rows if r["status"] == "FAIL"]
    
    # Save results directly to GCS
    results_gcs_uri = ""
    try:
        # Save final to output folder
        save_progress_to_gcs(evaluated_rows, final_blob_path, is_temp=False)
        results_gcs_uri = f"gs://{EVAL_BUCKET_NAME}/{final_blob_path}"

        # Clean up temp file
        if storage_client:
            try:
                bucket = storage_client.bucket(EVAL_BUCKET_NAME)
                blob = bucket.blob(temp_blob_path)
                if blob.exists():
                    blob.delete()
                    logger.info(f"Deleted temporary working file: {temp_blob_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_blob_path}: {e}")

    except Exception as e:
        logger.error(f"Failed to save/upload regression results: {e}")
        results_gcs_uri = f"Error: {str(e)}"

    return {
        "status": "success",
        "project_id": PROJECT_ID,
        "results_file_uri": results_gcs_uri,
        "summary": {
            "total_queries": len(df),
            "passed": pass_count,
            "failed": len(failures),
            "average_score": round(avg_score, 2),
            "failed_row_ids": failures,
            "passed_row_ids": [r["row_id"] for r in evaluated_rows if r["status"] == "PASS"]
        },
        "details": evaluated_rows  # Contains all rows (Pass and Fail)
    }


def promote_document_to_prod(
    tool_context: ToolContext,
    doc_id: str,
    version: str,
    approve: bool = False
) -> Dict[str, Any]:
    """
    Promotes a specific validated document version from Staging to Production.
    
    Args:
        doc_id: The document identifier (hash or ID).
        version: The version string (e.g., v20260128...).
        approve: Explicit approval flag.
    """
    if not approve:
        return {"status": "error", "message": "Promotion requires explicit approval (set approve=True)."}
        
    try:
        # 1. Verify Staging File
        staging_bucket = _get_bucket_gcs(STAGING_BUCKET_NAME)
        
        # Find the file in staging
        blobs = list(staging_bucket.list_blobs(prefix=f"{doc_id}/{version}"))
        if not blobs:
            return {"status": "error", "message": f"Document {doc_id} version {version} not found in staging."}
        
        source_blob = blobs[0] # Assuming one file per version ID
        
        # 2. Move to Production Bucket
        prod_bucket = _get_bucket_gcs(PROD_BUCKET_NAME)
        if not prod_bucket:
             return {"status": "error", "message": "Could not access production bucket."}
             
        # New name in prod: keep structure or flat? Keep structure for now
        new_blob_name = source_blob.name 
        prod_blob = staging_bucket.copy_blob(source_blob, prod_bucket, new_blob_name)
        
        # 3. Ingest into Production Corpus
        # Resolve prod corpus ID
        prod_corpus_id = get_corpus_id_by_display_name(PROD_CORPUS_DISPLAY_NAME)
        if not prod_corpus_id:
            # Create if not exists
            create_res = create_corpus(display_name=PROD_CORPUS_DISPLAY_NAME)
            prod_corpus_id = create_res.get("corpus_id")
            
        gcs_uri = f"gs://{PROD_BUCKET_NAME}/{new_blob_name}"
        import_res = import_files(corpus_id=prod_corpus_id, gcs_uris=[gcs_uri])
        
        # 4. Update Metadata
        # (Assuming upsert_file_metadata can find the record by composite ID or we query first)
        # For now, just upsert with new status
        upsert_file_metadata(
            id=f"{doc_id}_{version.replace('v','')}", # Match ID construction in ingest
            text_filename=os.path.basename(source_blob.name),
            stored_filename=new_blob_name,
            version=int(version.replace("v","")),
            upload_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            status='PRODUCTION',
            validation_status='PASS',
            bucket_status='production',
            bucket_path=gcs_uri,
            corpus_name=PROD_CORPUS_DISPLAY_NAME
        )
        
        # 5. Archive old versions (Completed in step 2.5)
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "version": version,
            "prod_uri": gcs_uri,
            "message": f"Successfully promoted {doc_id} {version} to Production."
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Promotion failed: {str(e)}"}


def phase_3_promote_validated(
    tool_context: ToolContext,
    promotion_plan: List[Dict[str, str]],
    confirm_all: bool = False
) -> Dict[str, Any]:
    """
    Batch promotes validated documents based on a plan.
    
    Args:
        promotion_plan: List of dicts with {"doc_id": "...", "version": "..."}
        confirm_all: Safety flag to execute all.
    """
    if not confirm_all:
        return {"status": "waiting", "message": "Please confirm promotion by setting confirm_all=True."}
        
    results = []
    for item in promotion_plan:
        res = promote_document_to_prod(
            tool_context=tool_context,
            doc_id=item.get("doc_id"),
            version=item.get("version"),
            approve=True
        )
        results.append(res)
        
    return {
        "status": "success",
        "promoted_count": len([r for r in results if r["status"] == "success"]),
        "details": results
    }

def rollback_production(
    tool_context: ToolContext,
    doc_id: str,
    target_version: str
) -> Dict[str, Any]:
    """
    Rolls back a document in production to a previous version from the Archive.
    
    Args:
        tool_context: The tool context.
        doc_id: The document ID (e.g., 'policy_manual').
        target_version: The version string to restore (e.g., 'v1.0').
    """
    # 1. Verify existence in Archive
    # Construct potential blob name (assuming naming convention doc_id_version.ext or similar)
    # Since we don't know the exact extension, we might need to search or assume strict naming.
    # For this implementation, we'll assume the user provides the specific version identifier that matches the file name in Archive.
    
    # Check if we can find the file in Archive bucket
    from rag.tools import list_blobs
    
    # We search for the specific version in the archive
    # Pattern: {doc_id}_{target_version} or just matching the name if the user provided the full name
    archive_files = list_blobs(tool_context, ARCHIVE_BUCKET_NAME, prefix=f"{doc_id}")
    if archive_files.get("status") != "success":
        return {"status": "error", "message": f"Could not access Archive bucket: {archive_files.get('message')}"}
    
    found_blob = None
    for fname in archive_files.get("files", []):
        if target_version in fname:
            found_blob = fname
            break
            
    if not found_blob:
        return {
            "status": "error", 
            "message": f"Target version '{target_version}' for doc '{doc_id}' not found in Archive bucket ({ARCHIVE_BUCKET_NAME})."
        }
    
    # 2. Promote it back to Production
    # We treat this as a promotion from Archive -> Prod
    # promote_document_to_prod usually expects from Staging. We might need to handle Archive source.
    # Let's use move_gcs_file to bring it to Staging first (to simulate a standard promotion flow) or directly copy.
    
    # For safety and standard workflow: Copy Archive -> Staging, then Promote.
    from rag.tools import move_gcs_file
    
    # We copy (not move, to keep history) back to staging
    # Note: move_gcs_file might strictly move. If so, we should use a copy tool if available.
    # If only move is available, we move it back to staging.
    
    move_res = move_gcs_file(tool_context, source_bucket=ARCHIVE_BUCKET_NAME, source_blob=found_blob, destination_bucket=STAGING_BUCKET_NAME)
    if move_res.get("status") != "success":
        return {"status": "error", "message": f"Failed to restore file to staging: {move_res.get('message')}"}
        
    # 3. Now Promote from Staging to Prod (this handles indexing and prod bucket)
    # We approve automatically since this is an explicit rollback command
    promote_res = promote_document_to_prod(
        tool_context, 
        doc_id=doc_id, 
        version=target_version, 
        approve=True
    )
    
    return {
        "status": "success",
        "message": f"Rollback initiated for {doc_id} to version {target_version}.",
        "details": promote_res
    }

def cleanup_test_environment(
    tool_context: ToolContext
) -> Dict[str, Any]:
    """
    Cleans up temporary test corpora and candidate corpora.
    """
    # list_corpora and delete_corpus are imported from corpus_tools
    
    report = []
    
    # 1. List all corpora
    corpora_res = list_corpora()
    if corpora_res.get("status") != "success":
        return {"status": "error", "message": "Failed to list corpora for cleanup."}
        
    # 2. Find targets
    targets = []
    for corpus in corpora_res.get("corpora", []):
        dname = corpus.get("display_name", "")
        if dname.startswith("test_") or dname.startswith("candidate_") or "temp" in dname:
            targets.append(corpus.get("id"))
            
    # 3. Delete them
    for cid in targets:
        del_res = delete_corpus(cid)
        report.append({
            "corpus_id": cid,
            "status": del_res.get("status"),
            "message": del_res.get("message")
        })
        
    return {
        "status": "success", 
        "cleaned_count": len(report),
        "details": report,
        "message": f"Cleanup completed. Removed {len(report)} temporary corpora."
    }

def create_daily_test_corpus(tool_context: ToolContext) -> Dict[str, Any]:
    """Creates a daily test corpus."""
    name = f"test_{datetime.datetime.now().strftime('%Y%m%d')}"
    return create_corpus(display_name=name)

def validate_retrieval(tool_context: ToolContext, query: str, expected: str) -> Dict[str, Any]:
    """Simple validation helper."""
    # Placeholder
    return {"status": "success", "message": "Validation helper"}

def create_candidate_corpus(tool_context: ToolContext, source_bucket: str) -> Dict[str, Any]:
    """
    Creates a candidate corpus and imports files from the source bucket.
    """
    display_name = f"candidate_corpus_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 1. Create Corpus
    create_res = create_corpus(display_name=display_name)
    if create_res.get("status") != "success":
        return create_res
        
    corpus_id = create_res.get("corpus_id")
    
    # 2. List files in source bucket
    # list_blobs returns a dict with "files" list
    blobs_res = list_blobs(tool_context, source_bucket)
    if blobs_res.get("status") != "success":
        return {
            "status": "warning",
            "corpus_id": corpus_id,
            "message": f"Corpus created but failed to list files from {source_bucket}: {blobs_res.get('message')}"
        }
        
    files = blobs_res.get("files", [])
    if not files:
         return {
            "status": "success",
            "corpus_id": corpus_id,
            "message": f"Corpus created but source bucket {source_bucket} is empty."
        }
        
    # 3. Import Files
    # Filter out directory markers if any (paths ending in /)
    valid_files = [f for f in files if not f.endswith('/')]
    
    if not valid_files:
         return {
            "status": "warning",
            "corpus_id": corpus_id,
            "message": "No valid files found in source bucket (ignoring directories)."
        }

    gcs_uris = [f"gs://{source_bucket}/{f}" for f in valid_files]
    
    # We import in batches if needed, but import_files handles list.
    import_res = import_files(corpus_id=corpus_id, gcs_uris=gcs_uris)
    
    return {
        "status": "success",
        "corpus_id": corpus_id,
        "display_name": display_name,
        "imported_count": import_res.get("imported_count", 0),
        "message": f"Created candidate corpus '{display_name}' and initiated import of {len(files)} files."
    }

def run_regression_tests(tool_context: ToolContext) -> Dict[str, Any]:
    """Placeholder for advanced regression."""
    return {"status": "success"}

def run_regression_tests_from_excel(tool_context: ToolContext, excel_path: str) -> Dict[str, Any]:
    """Wrapper for phase 2."""
    return phase_2_regression_test_xlsx(tool_context, "candidate_corpus", excel_path)

# ===================== #
# Tool Definitions
# ===================== #
# Removed explicit FunctionTool wrappers to allow Agent to handle function wrapping.
# Functions are exported directly.
