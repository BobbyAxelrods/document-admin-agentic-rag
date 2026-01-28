from dis import Instruction
from doctest import debug_script
import os
from pydoc import describe 
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
from rag.config import AGENT_OUTPUT_KEY

# Import tools
from rag.tools import (
    create_corpus,
    list_corpora,
    update_corpus,
    get_corpus,
    delete_corpus,
    import_files,
    list_files, 
    get_file,
    delete_file_from_corpus,
    query_corpus,
    get_corpus_id_by_display_name,
    get_file_id_by_name,
    list_gcs_buckets,
    create_gcs_bucket,
    upload_file_to_gcs,
    list_blobs,
    move_gcs_file,
    delete_gcs_file,
    delete_gcs_bucket,
    # create_daily_test_corpus,
    # validate_retrieval,
    # promote_document_to_prod,
    # cleanup_test_environment,
    # ingest_document,
    # create_candidate_corpus,
    # run_regression_tests,
    # run_regression_tests_from_excel,
    # rollback_production,
    # phase_1_upload_and_ingest,
    # phase_2_regression_test_xlsx,
    # phase_3_promote_validated,
    # cleanup_test_environment,
    # initialize_infrastructure
)


load_dotenv()
AZURE = os.getenv("AZURE", "azure/gpt-4o")

# build the instruction loader 

def load_instructions(instruction_file_name):
    path_of_instructions = os.path.join(os.path.dirname(__file__), f"{instruction_file_name}.md")
    try:
        with open(path_of_instructions, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"You are error reading instruction"

root_agent = Agent(
    name= "pru_rag_manager",
    model = LiteLlm(model=AZURE),
    description="managing rag data source lifecycle",
    instruction = load_instructions("admin"),
    tools = [
        # Storage Tools
        list_gcs_buckets,
        create_gcs_bucket,
        upload_file_to_gcs,
        list_blobs,
        move_gcs_file,
        delete_gcs_file,
        delete_gcs_bucket,
    
        # RAG Corpus Tools
        create_corpus,
        list_corpora,
        update_corpus,
        get_corpus,
        delete_corpus,
        import_files,
        list_files, # This is corpus list_files
        get_file,
        delete_file_from_corpus,
        query_corpus,
        get_corpus_id_by_display_name,
        get_file_id_by_name,
    
        # # Lifecycle Orchestration Tools
        # create_daily_test_corpus,
        # validate_retrieval,
        # promote_document_to_prod,
        # cleanup_test_environment,
        # ingest_document,
        # create_candidate_corpus,
        # run_regression_tests,
        # run_regression_tests_from_excel,
        # phase_1_upload_and_ingest,
        # phase_2_regression_test_xlsx,
        # phase_3_promote_validated,
        # rollback_production,
        # initialize_infrastructure
    ],
    output_key=AGENT_OUTPUT_KEY
)

