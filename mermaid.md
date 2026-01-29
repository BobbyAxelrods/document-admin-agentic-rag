flowchart TD
    %% Actors
    Admin([Admin User])
    AdminAgent[Admin Agent]

    %% Storage Layer (System of Record)
    subgraph GCS [Google Cloud Storage]
        B_Staging[(Staging Bucket)]
        B_Prod[(Production Bucket)]
        B_Archive[(Archive Bucket)]
    end

    %% RAG Layer (Derived Indexes)
    subgraph RAG [Vertex AI RAG Engine]
        C_Test[[Test Corpus]]
        C_Prod[[Production Corpus]]
        C_Candidate[[Candidate Corpus]]
    end

    %% -----------------------------
    %% Phase 1: Ingestion
    %% -----------------------------
    Admin -->|1. Ingest| AdminAgent
    AdminAgent -->|"ingest_document<br/>(hash + upload)"| B_Staging

    %% -----------------------------
    %% Phase 2: Validation
    %% -----------------------------
    Admin -->|2. Validate| AdminAgent
    AdminAgent -->|"validate_retrieval<br/>(create daily corpus)"| C_Test
    B_Staging -.->|import| C_Test
    AdminAgent <-->|query| C_Test

    %% -----------------------------
    %% Phase 3: Regression Testing
    %% -----------------------------
    Admin -->|3. Regression Test| AdminAgent
    AdminAgent -->|create_candidate_corpus| C_Candidate
    B_Staging -.->|import new doc| C_Candidate
    B_Prod -.->|"import existing docs<br/>(excluding old version)"| C_Candidate
    AdminAgent -->|"run_regression_tests<br/>(compare results)"| C_Prod
    AdminAgent <-->|query| C_Candidate

    %% -----------------------------
    %% Phase 4: Promotion (Go Live)
    %% -----------------------------
    Admin -->|4. Promote| AdminAgent
    AdminAgent -->|promote_document_to_prod| B_Prod
    
    %% Archival Logic during Promotion
    B_Prod -.->|archive old version| B_Archive
    B_Prod -.->|delete old version| C_Prod
    
    %% Deployment
    B_Staging -->|copy to prod| B_Prod
    B_Prod -.->|import new version| C_Prod

    %% -----------------------------
    %% Phase 5: Rollback (Emergency)
    %% -----------------------------
    Admin -.->|5. Rollback| AdminAgent
    AdminAgent -->|rollback_production| B_Prod
    B_Archive -->|restore version| B_Prod
    B_Prod -.->|update index| C_Prod

    %% -----------------------------
    %% Phase 6: Cleanup
    %% -----------------------------
    Admin -->|6. Cleanup| AdminAgent
    AdminAgent -->|cleanup_test_environment| C_Test
    AdminAgent -->|cleanup_test_environment| C_Candidate
    
    %% Styling
    classDef storage fill:#e3f2fd,stroke:#1565c0
    classDef rag fill:#fff3e0,stroke:#ef6c00
    classDef actor fill:#f3e5f5,stroke:#6a1b9a

    class B_Staging,B_Prod,B_Archive storage
    class C_Test,C_Prod,C_Candidate rag
    class Admin,AdminAgent actor