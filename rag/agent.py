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
    get_file_id_by_name
)

load_dotenv()
AZURE = os.getenv("AZURE")

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
        # Storage Tools (Commented out)
        # list_buckets,
        # create_bucket,
        # upload_file,
        # list_files, # Note: list_files is ambiguous if both are imported. We are using corpus list_files now.
        # move_file,
        # delete_file,
    
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
    
        # Lifecycle Orchestration Tools (Commented out)
        # create_daily_test_corpus,
        # validate_retrieval,
        # promote_document_to_prod,
        # cleanup_test_environment
    ],
    output_key=AGENT_OUTPUT_KEY
)


