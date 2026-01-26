flowchart TD
    %% Actors
    Admin([Admin User])
    Agent[Admin Agent]
    
    %% Infrastructure
    subgraph Storage [GCS Storage Library]
        S_Test[(Staging Bucket)]
        S_Prod[(Production Bucket)]
        S_Arch[(Archive Bucket)]
    end
    
    subgraph RAG [Vertex AI RAG Engine]
        C_Test[[Test Corpus]]
        C_Prod[[Production Corpus]]
        C_Arch[[Archive Corpus]]
    end

    %% Phase 1: Ingestion
    Admin -->|1. Ingest Doc| Agent
    Agent -->|upload_file_gcs_tool| S_Test
    Agent -->|import_files_tool| C_Test
    S_Test -.->|Data Flow| C_Test
    
    %% Phase 2: Validation
    Admin -->|2. Verify/Query| Agent
    Agent <-->|query_corpus_tool| C_Test
    
    %% Phase 3: Promotion
    Admin -->|3. Promote Doc| Agent
    
    %% Promotion Logic
    Agent -->|list_blobs_tool| S_Prod
    
    %% Path A: New Document
    S_Prod -- No --> MoveNew[move_gcs_file_tool]
    S_Test --> MoveNew --> S_Prod
    S_Prod -.->|import_files_tool| C_Prod
    
    %% Path B: Update Document
    S_Prod -- Yes --> ArchiveOld[move_gcs_file_tool]
    S_Prod --> ArchiveOld --> S_Arch
    S_Arch -.->|import_files_tool| C_Arch
    
    %% Cleanup
    Agent -->|delete_corpus_tool| C_Test
    Agent -->|delete_gcs_file_tool| S_Test

    classDef storage fill:#e1f5fe,stroke:#01579b
    classDef rag fill:#fff3e0,stroke:#e65100
    classDef actor fill:#f3e5f5,stroke:#4a148c
    
    class S_Test,S_Prod,S_Arch storage
    class C_Test,C_Prod,C_Arch rag
    class Admin,Agent actor