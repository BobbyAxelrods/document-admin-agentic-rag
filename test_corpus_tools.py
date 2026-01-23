import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from rag.tools.corpus import (
    create_corpus,
    list_corpora,
    update_corpus,
    get_corpus,
    delete_corpus,
    list_files,
    get_corpus_id_by_display_name
)

def run_test():
    print("=== Starting Corpus Tools Test ===")
    
    test_corpus_name = "test_corpus_automation_check"
    
    # 1. Clean up if exists
    print("\n[1] Checking for existing test corpus...")
    existing_id = get_corpus_id_by_display_name(test_corpus_name)
    if existing_id:
        print(f"Found existing corpus {existing_id}, deleting...")
        delete_corpus(existing_id)
    
    # 2. Create Corpus
    print(f"\n[2] Creating corpus '{test_corpus_name}'...")
    result = create_corpus(display_name=test_corpus_name, description="Test corpus for automation")
    print(f"Create Result: {result}")
    
    if result.get("status") != "success":
        print("Failed to create corpus. Exiting.")
        return

    corpus_id = result.get("corpus_id")
    print(f"Corpus ID: {corpus_id}")
    
    # 3. Get Corpus Details
    print(f"\n[3] Getting details for corpus {corpus_id}...")
    details = get_corpus(corpus_id)
    print(f"Get Result: {details}")
    
    # 4. Update Corpus
    print(f"\n[4] Updating corpus {corpus_id} (Renaming)...")
    update_result = update_corpus(corpus_id, display_name=f"{test_corpus_name}_renamed", description="Updated description")
    print(f"Update Result: {update_result}")
    
    # 5. List Files (Should be empty)
    print(f"\n[5] Listing files in corpus {corpus_id}...")
    files_result = list_files(corpus_id)
    print(f"List Files Result: {files_result}")
    
    # 6. Delete Corpus
    print(f"\n[6] Deleting corpus {corpus_id}...")
    delete_result = delete_corpus(corpus_id)
    print(f"Delete Result: {delete_result}")
    
    print("\n=== Test Completed ===")

if __name__ == "__main__":
    run_test()
