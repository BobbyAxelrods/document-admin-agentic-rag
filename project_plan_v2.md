# 🎯 Admin Agent for Vertex AI RAG Engine
## Project Implementation Plan

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Phase-by-Phase Implementation](#phase-by-phase-implementation)
4. [Database Schema](#database-schema)
5. [GCS Bucket Structure](#gcs-bucket-structure)
6. [Agent Workflow](#agent-workflow)
7. [Implementation Timeline](#implementation-timeline)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Plan](#deployment-plan)

---

## 1. Project Overview

### 1.1 What We're Building

**Admin Agent** - A controlled orchestration agent responsible for:
- ✅ Document ingestion and validation
- ✅ Promotion workflow with safety gates
- ✅ Production deployment with versioning
- ✅ Rollback and archival capabilities
- ✅ Complete audit trail

### 1.2 Core Principles

1. **GCS is the single source of truth** - RAG corpora are derived indexes (ephemeral, rebuildable)
2. **Safety-first** - Correctness over speed, traceability over convenience
3. **Fail-safe** - Always leave system in consistent state, rollback must always be possible
4. **Explicit approval** - No auto-promotions, admin must confirm all production changes

### 1.3 Key Features

```
✅ Versioned production buckets (prod-v1, prod-v2, prod-v3...)
✅ Regression testing with Excel test cases
✅ Atomic promotion (all-or-nothing)
✅ Instant rollback capability
✅ Complete metadata tracking in SQL
✅ 7-year archival retention
✅ Document locking (prevent concurrent modifications)
```

---

## 2. System Architecture

### 2.1 Environment Separation

```
┌─────────────────────────────────────────────────────────┐
│                     ENVIRONMENTS                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📦 Staging                                              │
│  ├─ Bucket: staging-bucket                              │
│  ├─ Corpus: staging-corpus (ephemeral)                  │
│  └─ Purpose: Validation & testing                       │
│                                                          │
│  🚀 Production (Versioned)                               │
│  ├─ Buckets: prod-bucket-v1, v2, v3...                  │
│  ├─ Corpus: production-corpus-vN                        │
│  ├─ Current: Only ONE has is_current_production=TRUE    │
│  └─ Purpose: Live user traffic                          │
│                                                          │
│  📚 Archive                                              │
│  ├─ Bucket: archive-bucket                              │
│  ├─ Retention: 7 years (immutable)                      │
│  └─ Purpose: Historical versions, rollback              │
│                                                          │
│  🗑️ Staging Archive                                      │
│  ├─ Bucket: staging-archive-bucket                      │
│  ├─ Retention: 30 days (auto-delete)                    │
│  └─ Purpose: Temporary staging file cleanup             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Admin Upload
     │
     ▼
┌──────────────┐
│   Staging    │ ◄─── Test with Excel
│   Bucket     │      (regression tests)
└──────┬───────┘
       │ (validation passed)
       ▼
┌──────────────┐
│ Production   │ ◄─── Create new version
│  Bucket vN   │      (atomic switch)
└──────┬───────┘
       │ (old version)
       ▼
┌──────────────┐
│   Archive    │ ◄─── 7-year retention
│   Bucket     │      (for rollback)
└──────────────┘
```

### 2.3 Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ADMIN AGENT                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────┐     ┌────────────────┐             │
│  │  File Manager  │────▶│  GCS Handler   │             │
│  │  - Upload      │     │  - Copy        │             │
│  │  - Validate    │     │  - Move        │             │
│  │  - Hash        │     │  - Verify      │             │
│  └────────────────┘     └────────────────┘             │
│                                                          │
│  ┌────────────────┐     ┌────────────────┐             │
│  │ Test Runner    │────▶│ Corpus Manager │             │
│  │ - Parse Excel  │     │ - Create       │             │
│  │ - Run queries  │     │ - Import       │             │
│  │ - Evaluate     │     │ - Delete       │             │
│  └────────────────┘     └────────────────┘             │
│                                                          │
│  ┌────────────────┐     ┌────────────────┐             │
│  │ Metadata Mgr   │────▶│  SQL Database  │             │
│  │ - Track files  │     │ - file_metadata│             │
│  │ - Track buckets│     │ - bucket_meta  │             │
│  │ - Audit logs   │     │ - audit_logs   │             │
│  └────────────────┘     └────────────────┘             │
│                                                          │
│  ┌────────────────┐     ┌────────────────┐             │
│  │ Promotion Mgr  │────▶│ Rollback Mgr   │             │
│  │ - Plan         │     │ - Verify       │             │
│  │ - Execute      │     │ - Restore      │             │
│  │ - Verify       │     │ - Log          │             │
│  └────────────────┘     └────────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Phase-by-Phase Implementation

### Phase 1: UPLOAD & INGEST 📤

**Goal:** Upload files to staging and prepare for validation

**Admin Action:**
```
Admin uploads files via UI/API
```

**Agent Workflow:**
```python
def phase_1_upload_and_ingest(files):
    for file in files:
        # 1. Validate file
        validate_file_format(file)  # pdf, docx, txt
        validate_file_size(file)    # max 50MB
        
        # 2. Compute SHA-256 hash
        content_hash = compute_sha256(file)
        
        # 3. Check for duplicates
        if exists_in_staging(content_hash):
            raise DuplicateError()
        
        # 4. Generate doc_id and version
        doc_id = generate_doc_id(file.name)
        existing_versions = get_all_versions(doc_id)
        
        if existing_versions:
            # Check if locked
            if is_locked(doc_id):
                raise LockedError("Document locked in active workflow")
            new_version = max(existing_versions) + 1
        else:
            new_version = 1
        
        # 5. Create stored filename
        stored_filename = f"v{new_version}_{content_hash[:8]}.{file.ext}"
        
        # 6. Upload to GCS
        staging_path = f"gs://staging-bucket/{doc_id}/{stored_filename}"
        upload_to_gcs(file, staging_path)
        
        # 7. Import to staging corpus
        import_to_corpus(staging_path, "staging-corpus")
        
        # 8. Save metadata
        insert_file_metadata({
            'id': content_hash,
            'doc_id': doc_id,
            'text_filename': file.name,
            'stored_filename': stored_filename,
            'version': new_version,
            'date': today(),
            'format': file.ext,
            'status': 'STAGED',
            'validation_status': 'PENDING',
            'bucket_status': 'staging',
            'bucket_path': staging_path,
            'uploaded_by': current_admin(),
            'uploaded_at': now()
        })
        
        # 9. Log event
        log_event('document.uploaded', doc_id, new_version)
```

**Output:**
```
✅ Files Staged Successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files uploaded: 3

1. user-manual.pdf
   Doc ID: user-manual
   Version: v2 (update)
   Hash: a3d5f8c2
   Status: STAGED
   
2. refund-policy.pdf
   Doc ID: refund-policy
   Version: v1 (new)
   Hash: b7e2f9a1
   Status: STAGED

3. faq.pdf
   Doc ID: faq
   Version: v1 (new)
   Hash: c9f3a1d2
   Status: STAGED

Next: Upload testcase.xlsx to run validation
```

**Implementation Checklist:**
- [ ] File upload handler
- [ ] SHA-256 hash computation
- [ ] Duplicate detection
- [ ] Version management
- [ ] GCS upload with retry logic
- [ ] Corpus import function
- [ ] Metadata insertion
- [ ] Event logging
- [ ] Document locking mechanism

---

### Phase 2: VALIDATION (Regression Testing) 🧪

**Goal:** Test documents with ground truth questions

**Admin Action:**
```
Admin uploads testcase.xlsx with test questions
```

**Excel Format:**
```
| doc_id        | question                     | expected_answer                              | min_score |
|---------------|------------------------------|----------------------------------------------|-----------|
| user-manual   | How do I reset my password?  | Click Settings > Security > Reset Password   | 0.85      |
| user-manual   | What is the support email?   | support@example.com                          | 0.90      |
| refund-policy | What is the refund window?   | 30 days from purchase                        | 0.85      |
```

**Agent Workflow:**
```python
def phase_2_validation(testcase_xlsx):
    # 1. Parse Excel
    test_cases = parse_excel(testcase_xlsx)
    
    # 2. Update file status
    staged_files = get_files_by_status('STAGED')
    for file in staged_files:
        update_file_metadata(file['id'], status='VALIDATING')
    
    # 3. Run tests
    results = []
    for test in test_cases:
        # Query staging corpus
        response = query_corpus(
            query=test['question'],
            corpus='staging-corpus',
            filter={'doc_id': test['doc_id']}
        )
        
        # Evaluate
        answer_match = test['expected_answer'].lower() in response.text.lower()
        score_pass = response.relevance_score >= test['min_score']
        passed = answer_match and score_pass
        
        results.append({
            'doc_id': test['doc_id'],
            'question': test['question'],
            'expected': test['expected_answer'],
            'actual': response.text,
            'score': response.relevance_score,
            'passed': passed
        })
    
    # 4. Calculate pass rate
    overall_pass = all(r['passed'] for r in results)
    
    # 5. Update metadata
    for file in staged_files:
        update_file_metadata(
            file['id'],
            validation_status='PASS' if overall_pass else 'FAIL',
            next_action='PROMOTE' if overall_pass else 'MANUAL_REVIEW'
        )
    
    return results
```

**Output (Success):**
```
🧪 Validation Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Status: PASS ✅
Tests Passed: 15/15 (100%)

Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. user-manual v2
   Q: "How do I reset my password?"
   Expected: "Click Settings > Security > Reset Password"
   Got: "To reset your password, click Settings > Security > Reset Password"
   Score: 0.92 ✅ (threshold: 0.85)
   Status: PASS ✅

2. user-manual v2
   Q: "What is the support email?"
   Expected: "support@example.com"
   Got: "Contact support@example.com for assistance"
   Score: 0.95 ✅ (threshold: 0.90)
   Status: PASS ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Next: Type 'APPROVE' to promote to production
```

**Output (Failure):**
```
🧪 Validation Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Status: FAIL ❌
Tests Passed: 13/15 (87%)

Failed Tests:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. user-manual v2
   Q: "What is the support email?"
   Expected: "support@example.com"
   Got: "Contact us through our website"
   Score: 0.72 ❌ (threshold: 0.90)
   Issue: Expected answer not found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Options:
1. REVISE - Upload corrected document
2. ADJUST - Modify test expectations in Excel
3. REJECT - Delete from staging
```

**Implementation Checklist:**
- [ ] Excel parser (pandas/openpyxl)
- [ ] RAG corpus query function
- [ ] Response evaluation logic
- [ ] Pass/fail determination
- [ ] Detailed result formatting
- [ ] Status updates in database
- [ ] Test result storage

---

### Phase 3: PROMOTION PREPARATION 📋

**Goal:** Create promotion plan for validated files

**Admin Action:**
```
Admin types: "APPROVE"
```

**Agent Workflow:**
```python
def phase_3_promotion_preparation():
    # 1. Get validated files
    validated_files = get_files_by_status(
        status='VALIDATING',
        validation_status='PASS'
    )
    
    if not validated_files:
        raise NoFilesError("No validated files ready")
    
    # 2. Create promotion plan
    plan = {
        'new_files': [],
        'updated_files': [],
        'archived_files': []
    }
    
    for file in validated_files:
        prod_version = get_production_version(file['doc_id'])
        
        if prod_version:
            # UPDATE
            plan['updated_files'].append({
                'doc_id': file['doc_id'],
                'current': prod_version['version'],
                'new': file['version']
            })
            plan['archived_files'].append({
                'doc_id': file['doc_id'],
                'version': prod_version['version']
            })
        else:
            # NEW
            plan['new_files'].append({
                'doc_id': file['doc_id'],
                'version': file['version']
            })
    
    # 3. Determine new production version
    current_prod = get_current_production_bucket()
    plan['new_bucket_version'] = current_prod['bucket_version'] + 1
    
    # 4. Calculate summary
    plan['summary'] = {
        'total': len(validated_files),
        'new': len(plan['new_files']),
        'updated': len(plan['updated_files']),
        'archived': len(plan['archived_files'])
    }
    
    return plan
```

**Output:**
```
📋 Promotion Plan
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  Files to promote: 3
  New files: 2
  Updated files: 1
  Files to archive: 1

Production Bucket:
  Current: prod-bucket-v5
  New: prod-bucket-v6

Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEW FILES:
1. refund-policy v1
   Action: Create new document
   
2. faq v1
   Action: Create new document

UPDATED FILES:
1. user-manual v1 → v2
   Action: Replace existing
   Archive: v1 → archive-bucket

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  WARNING: This will affect live production!

Type 'CONFIRM' to proceed
Type 'CANCEL' to abort
```

**Implementation Checklist:**
- [ ] Promotion plan generator
- [ ] Production version checker
- [ ] New vs update detection
- [ ] Archival planning
- [ ] Bucket version incrementer
- [ ] Plan display formatter
- [ ] Confirmation handler

---

### Phase 4: PROMOTION EXECUTION 🚀

**Goal:** Create new production bucket with all files (atomic switch)

**Admin Action:**
```
Admin types: "CONFIRM"
```

**Agent Workflow:**
```python
def phase_4_promotion_execution(promotion_plan):
    operation_id = generate_operation_id()
    
    try:
        # 1. Update status
        validated_files = get_files_by_status(
            status='VALIDATING',
            validation_status='PASS'
        )
        for file in validated_files:
            update_file_metadata(file['id'], status='PROMOTING')
        
        # 2. Get production info
        current_prod = get_current_production_bucket()
        new_version = promotion_plan['new_bucket_version']
        new_bucket_name = f"prod-bucket-v{new_version}"
        
        # 3. Create new GCS bucket
        create_gcs_bucket(new_bucket_name)
        
        # 4. Copy existing production files
        existing_files = get_files_by_bucket_status(
            f"production-v{current_prod['bucket_version']}"
        )
        
        for file in existing_files:
            # Skip if being updated
            if file['doc_id'] in [f['doc_id'] for f in validated_files]:
                continue
            
            # Copy to new bucket
            src = file['bucket_path']
            dst = src.replace(
                f"prod-bucket-v{current_prod['bucket_version']}",
                new_bucket_name
            )
            copy_gcs_file(src, dst)
            verify_checksum(src, dst)
            
            # Update metadata
            update_file_metadata(
                file['id'],
                bucket_status=f'production-v{new_version}',
                bucket_path=dst
            )
        
        # 5. Copy new/updated files from staging
        for file in validated_files:
            src = file['bucket_path']
            dst = src.replace('staging-bucket', new_bucket_name)
            
            copy_gcs_file(src, dst)
            verify_checksum(src, dst)
            
            update_file_metadata(
                file['id'],
                status='PRODUCTION',
                bucket_status=f'production-v{new_version}',
                bucket_path=dst,
                promoted_at=now()
            )
        
        # 6. Create bucket metadata
        new_bucket_id = generate_bucket_id()
        all_files = get_files_by_bucket_status(f'production-v{new_version}')
        
        insert_bucket_metadata({
            'bucket_id': new_bucket_id,
            'bucket_name': new_bucket_name,
            'bucket_type': 'production',
            'bucket_version': new_version,
            'bucket_status': 'ACTIVE',
            'is_current_production': False,  # Not live yet
            'total_files': len(all_files),
            'file_list': [f['id'] for f in all_files],
            'gcs_bucket_path': f'gs://{new_bucket_name}',
            'created_at': now(),
            'supersedes': current_prod['bucket_id']
        })
        
        # 7. Create and import to new corpus
        corpus_name = f'production-corpus-v{new_version}'
        create_corpus(corpus_name)
        batch_import_to_corpus(
            [f['bucket_path'] for f in all_files],
            corpus_name
        )
        
        # 8. Run smoke tests
        smoke_tests = load_smoke_test_queries()
        for test in smoke_tests:
            result = query_corpus(test['query'], corpus_name)
            assert result.status == 'success'
        
        # 9. ATOMIC: Switch production pointer
        # This is the GO-LIVE moment!
        BEGIN_TRANSACTION()
        
        update_bucket_metadata(
            current_prod['bucket_id'],
            is_current_production=False
        )
        update_bucket_metadata(
            new_bucket_id,
            is_current_production=True
        )
        
        COMMIT_TRANSACTION()
        
        # 10. Log success
        log_event({
            'event_type': 'document.promoted',
            'operation_id': operation_id,
            'bucket_version': new_version,
            'files_promoted': len(validated_files)
        })
        
        return {
            'status': 'success',
            'new_bucket': new_bucket_name,
            'files_promoted': len(validated_files),
            'total_files': len(all_files)
        }
        
    except Exception as e:
        log_error(operation_id, e)
        rollback_partial_changes(operation_id)
        raise
```

**Output:**
```
🚀 Promotion Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Production Bucket: prod-bucket-v6
Status: LIVE ✅

Files Promoted: 3
  - user-manual v2 (updated)
  - refund-policy v1 (new)
  - faq v1 (new)

Total Files in Production: 152

Verification:
✅ All files copied (152/152)
✅ Checksums verified
✅ Corpus created: production-corpus-v6
✅ Smoke tests passed (10/10)
✅ Production pointer updated

Previous Version: prod-bucket-v5
Status: Preserved for rollback (90 days)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 System is now serving user queries from prod-bucket-v6
Duration: 47 seconds
```

**Implementation Checklist:**
- [ ] GCS bucket creation
- [ ] Parallel file copy (ThreadPoolExecutor)
- [ ] Checksum verification
- [ ] Corpus creation and import
- [ ] Smoke test runner
- [ ] Atomic transaction wrapper
- [ ] Production pointer switch
- [ ] Rollback on failure
- [ ] Operation logging
- [ ] Error handling

---

### Phase 5: ARCHIVE OLD PRODUCTION 📦

**Goal:** Move superseded files to archive bucket

**Agent Workflow:**
```python
def phase_5_archive_old_production():
    # 1. Get old production bucket (N-1)
    current = get_current_production_bucket()
    old = get_bucket_metadata(bucket_version=current['bucket_version'] - 1)
    
    # 2. Get replaced files
    replaced_files = get_files_by_bucket_status(
        f"production-v{old['bucket_version']}"
    )
    replaced_files = [f for f in replaced_files if f['superseded_by']]
    
    # 3. Copy to archive
    for file in replaced_files:
        src = file['bucket_path']
        dst = src.replace(
            f"prod-bucket-v{old['bucket_version']}",
            'archive-bucket'
        )
        
        copy_gcs_file(src, dst)
        
        update_file_metadata(
            file['id'],
            status='ARCHIVE',
            bucket_status='archive',
            bucket_path=dst,
            archived_at=now()
        )
    
    # 4. Update old bucket metadata
    update_bucket_metadata(
        old['bucket_id'],
        bucket_status='ARCHIVED',
        archive_date=today(),
        archive_reason=f"Superseded by v{current['bucket_version']}",
        retention_expires_at=today() + timedelta(days=7*365)
    )
    
    # 5. Schedule cleanup (90 days)
    schedule_cleanup(old['bucket_name'], days=90)
    
    return {
        'status': 'archived',
        'files_archived': len(replaced_files)
    }
```

**Output:**
```
📦 Archival Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Old Production: prod-bucket-v5
Status: ARCHIVED

Files Archived: 1
  - user-manual v1

Archive Location: gs://archive-bucket/
Retention: 7 years (until 2032-01-27)

Rollback Available: Yes
  - Within 90 days: Instant rollback
  - After 90 days: Restore from archive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Implementation Checklist:**
- [ ] Old bucket identifier
- [ ] Replaced file detector
- [ ] Archive copy function
- [ ] Metadata updates
- [ ] Retention policy setter
- [ ] Cleanup scheduler

---

### Phase 6: CLEANUP 🧹

**Goal:** Clean up temporary resources

**Agent Workflow:**
```python
def phase_6_cleanup():
    # 1. Delete staging corpus
    delete_corpus('staging-corpus')
    
    # 2. Archive staging files
    staged_files = get_files_by_bucket_status('staging')
    for file in staged_files:
        src = file['bucket_path']
        dst = src.replace('staging-bucket', 'staging-archive-bucket')
        move_gcs_file(src, dst)
        update_file_metadata(
            file['id'],
            bucket_status='staging-archive',
            bucket_path=dst
        )
    
    # 3. Schedule staging archive deletion (30 days)
    schedule_cleanup('staging-archive-bucket', days=30)
    
    # 4. Clean old corpora (keep N and N-1 only)
    current = get_current_production_bucket()
    old_corpora = get_corpora(
        type='production',
        version_less_than=current['bucket_version'] - 1
    )
    for corpus in old_corpora:
        delete_corpus(corpus['name'])
    
    return {
        'status': 'cleaned',
        'staging_files_archived': len(staged_files),
        'old_corpora_deleted': len(old_corpora)
    }
```

**Output:**
```
🧹 Cleanup Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Staging corpus deleted
✅ Staging files archived (30-day retention)
✅ Old production corpora deleted

Preserved:
  - production-corpus-v6 (current)
  - production-corpus-v5 (rollback)

Deleted:
  - production-corpus-v4
  - production-corpus-v3
  - production-corpus-v2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Workflow complete. System is in clean state.
```

**Implementation Checklist:**
- [ ] Corpus deletion
- [ ] Staging file mover
- [ ] Cleanup scheduler
- [ ] Old corpus cleaner
- [ ] Retention policy enforcer

---

### Bonus: ROLLBACK 🔄

**Goal:** Emergency rollback to previous production

**Admin Action:**
```
Admin types: "ROLLBACK" with reason
```

**Agent Workflow:**
```python
def rollback_production(reason):
    operation_id = generate_operation_id()
    
    # 1. Get current and previous buckets
    current = get_current_production_bucket()
    previous = get_bucket_metadata(
        bucket_version=current['bucket_version'] - 1
    )
    
    if not previous:
        raise NoRollbackAvailable("No previous version")
    
    if previous['bucket_status'] != 'ARCHIVED':
        raise InvalidStateError("Previous version not archived")
    
    # 2. Verify integrity
    verify_bucket_integrity(previous)
    
    # 3. Run smoke tests
    corpus = f"production-corpus-v{previous['bucket_version']}"
    for test in load_smoke_test_queries():
        result = query_corpus(test['query'], corpus)
        assert result.status == 'success'
    
    # 4. ATOMIC: Switch pointer back
    BEGIN_TRANSACTION()
    
    update_bucket_metadata(
        current['bucket_id'],
        is_current_production=False,
        bucket_status='ROLLED_BACK'
    )
    update_bucket_metadata(
        previous['bucket_id'],
        is_current_production=True,
        bucket_status='ACTIVE'
    )
    
    COMMIT_TRANSACTION()
    
    # 5. Log rollback
    log_event({
        'event_type': 'rollback.completed',
        'operation_id': operation_id,
        'from_version': current['bucket_version'],
        'to_version': previous['bucket_version'],
        'reason': reason
    })
    
    return {
        'status': 'rolled_back',
        'current_production': previous['bucket_name']
    }
```

**Output:**
```
🔄 ROLLBACK COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current Production: prod-bucket-v5 ✅
Failed Version: prod-bucket-v6 (preserved for debugging)

Reason: High error rate detected in production queries

Verification:
✅ Bucket integrity verified
✅ Smoke tests passed (10/10)
✅ Production pointer updated

Duration: 45 seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ System restored to stable state
Users now querying prod-bucket-v5
```

**Implementation Checklist:**
- [ ] Previous version locator
- [ ] Integrity verification
- [ ] Smoke test runner
- [ ] Atomic pointer switch
- [ ] Rollback logging
- [ ] Error handling

---

## 4. Database Schema

### 4.1 Table: `file_metadata`

**Purpose:** Track individual files through lifecycle

```sql
CREATE TABLE file_metadata (
    -- Primary Identity
    id VARCHAR(64) PRIMARY KEY,           -- SHA-256 hash
    doc_id VARCHAR(100) NOT NULL,         -- Logical document ID
    text_filename VARCHAR(255) NOT NULL,  -- Original filename
    stored_filename VARCHAR(255) NOT NULL, -- GCS object name
    
    -- Versioning
    version INT NOT NULL,                 -- Version number
    date DATE NOT NULL,                   -- Upload date
    
    -- File Properties
    format VARCHAR(50) NOT NULL,          -- File extension
    file_size_bytes BIGINT NOT NULL,      -- File size
    
    -- Status Tracking
    status VARCHAR(20) NOT NULL,          -- STAGED, VALIDATING, PROMOTING, PRODUCTION, ARCHIVE, FAILED
    validation_status VARCHAR(20),        -- PENDING, IN_PROGRESS, PASS, FAIL
    next_action VARCHAR(50),              -- PROMOTE, MANUAL_REVIEW, etc.
    
    -- Location
    bucket_status VARCHAR(50) NOT NULL,   -- staging, production-vN, archive, staging-archive
    bucket_path TEXT NOT NULL,            -- Full GCS path
    corpus_name VARCHAR(100),             -- Which corpus
    
    -- Audit Trail
    uploaded_by VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP,
    archived_at TIMESTAMP,
    
    -- Relationships
    superseded_by VARCHAR(64),            -- Points to newer version
    supersedes VARCHAR(64),               -- Points to older version
    
    -- Constraints
    FOREIGN KEY (superseded_by) REFERENCES file_metadata(id),
    FOREIGN KEY (supersedes) REFERENCES file_metadata(id),
    
    -- Indexes
    INDEX idx_doc_id (doc_id),
    INDEX idx_status (status),
    INDEX idx_bucket_status (bucket_status),
    INDEX idx_validation_status (validation_status),
    INDEX idx_version (doc_id, version)
);
```

### 4.2 Table: `bucket_metadata`

**Purpose:** Track production bucket versions

```sql
CREATE TABLE bucket_metadata (
    -- Primary Identity
    bucket_id VARCHAR(64) PRIMARY KEY,    -- Unique bucket version ID
    bucket_name VARCHAR(255) NOT NULL,    -- Full bucket name
    bucket_type VARCHAR(50) NOT NULL,     -- staging, production, archive
    
    -- Versioning
    bucket_version INT NOT NULL,          -- Version number
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Status
    bucket_status VARCHAR(50) NOT NULL,   -- ACTIVE, ARCHIVED, ROLLED_BACK, DELETED
    is_current_production BOOLEAN DEFAULT FALSE, -- Only ONE should be TRUE
    
    -- Content Summary
    total_files INT DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    file_list JSON,                       -- Array of file IDs
    
    -- Archive Information
    archive_date DATE,
    archive_reason TEXT,
    retention_years INT DEFAULT 7,
    retention_expires_at DATE,
    
    -- Relationships
    superseded_by VARCHAR(64),
    supersedes VARCHAR(64),
    
    -- GCS Details
    gcs_bucket_path TEXT NOT NULL,
    corpus_name VARCHAR(100),
    
    -- Constraints
    FOREIGN KEY (superseded_by) REFERENCES bucket_metadata(bucket_id),
    FOREIGN KEY (supersedes) REFERENCES bucket_metadata(bucket_id),
    
    -- Indexes
    INDEX idx_bucket_type (bucket_type),
    INDEX idx_bucket_version (bucket_version),
    INDEX idx_bucket_status (bucket_status),
    INDEX idx_is_current (is_current_production)
);
```

### 4.3 Table: `audit_logs`

**Purpose:** Complete audit trail

```sql
CREATE TABLE audit_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(100) NOT NULL,     -- document.uploaded, document.promoted, etc.
    operation_id VARCHAR(64),             -- Correlation ID
    
    -- Context
    doc_id VARCHAR(100),
    version INT,
    bucket_id VARCHAR(64),
    admin_identity VARCHAR(100) NOT NULL,
    
    -- Details
    status VARCHAR(50),
    message TEXT,
    metadata JSON,
    error_details TEXT,
    
    -- Indexes
    INDEX idx_event_type (event_type),
    INDEX idx_timestamp (timestamp),
    INDEX idx_operation_id (operation_id),
    INDEX idx_doc_id (doc_id)
);
```

### 4.4 Example Data Flow

**After Phase 1 (Upload):**
```sql
-- file_metadata
id: a3d5f8c2...
doc_id: user-manual
version: 2
status: STAGED
bucket_status: staging
```

**After Phase 2 (Validation PASS):**
```sql
-- file_metadata
id: a3d5f8c2...
status: VALIDATING
validation_status: PASS
next_action: PROMOTE
```

**After Phase 4 (Promotion):**
```sql
-- file_metadata
id: a3d5f8c2...
status: PRODUCTION
bucket_status: production-v6
promoted_at: 2024-01-27 10:30:00

-- bucket_metadata
bucket_id: bucket-v6
bucket_version: 6
bucket_status: ACTIVE
is_current_production: TRUE
total_files: 152
```

**After Phase 5 (Archive):**
```sql
-- file_metadata (old version)
id: b7e2f9a1...
status: ARCHIVE
bucket_status: archive
archived_at: 2024-01-27 10:35:00

-- bucket_metadata (old bucket)
bucket_id: bucket-v5
bucket_status: ARCHIVED
archive_date: 2024-01-27
```

---

## 5. GCS Bucket Structure

### 5.1 Bucket Naming

```
staging-bucket
prod-bucket-v1
prod-bucket-v2
prod-bucket-v3
...
prod-bucket-vN
archive-bucket
staging-archive-bucket
```

### 5.2 Object Paths

```
gs://staging-bucket/
├── user-manual/
│   ├── v1_a3d5f8c2.pdf
│   └── v2_b7e2f9a1.pdf
├── refund-policy/
│   └── v1_c9f3a1d2.pdf
└── faq/
    └── v1_d4e8b2f3.pdf

gs://prod-bucket-v6/
├── user-manual/
│   └── v2_b7e2f9a1.pdf  (updated)
├── product-guide/
│   └── v1_e5f9c3a4.pdf  (existing)
├── refund-policy/
│   └── v1_c9f3a1d2.pdf  (new)
└── faq/
    └── v1_d4e8b2f3.pdf  (new)

gs://archive-bucket/
└── user-manual/
    └── v1_a3d5f8c2.pdf  (superseded)
```

### 5.3 Bucket Lifecycle Policies

**staging-archive-bucket:**
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
```

**archive-bucket:**
```json
{
  "versioning": {"enabled": true},
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 365}
      }
    ]
  },
  "retentionPolicy": {
    "retentionPeriod": 220752000  // 7 years in seconds
  }
}
```

**prod-bucket-v{N-1}** (rollback window):
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
```

---

## 6. Agent Workflow

### 6.1 Complete Workflow Diagram

```
┌────────────────────────────────────────────────────────────┐
│ PHASE 1: UPLOAD & INGEST                                   │
│ Admin uploads files → Agent stages to staging-bucket       │
│ Status: STAGED                                             │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 2: VALIDATION                                        │
│ Admin uploads testcase.xlsx → Agent runs regression tests │
│ Status: VALIDATING → PASS/FAIL                            │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 3: PROMOTION PREPARATION                             │
│ Admin approves → Agent creates promotion plan              │
│ Admin confirms plan                                        │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 4: PROMOTION EXECUTION                               │
│ • Create new production bucket (vN)                        │
│ • Copy old production files                                │
│ • Copy new/updated files from staging                      │
│ • Create new corpus                                        │
│ • Run smoke tests                                          │
│ • ATOMIC: Switch production pointer (GO LIVE)              │
│ Status: PRODUCTION                                         │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 5: ARCHIVE                                           │
│ Move superseded files to archive-bucket                    │
│ Update bucket status: ARCHIVED                             │
│ Status: ARCHIVE                                            │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│ PHASE 6: CLEANUP                                           │
│ • Delete staging corpus                                    │
│ • Archive staging files (30 days)                          │
│ • Delete old production corpora                            │
└────────────────────────────────────────────────────────────┘

         ┌──────────────────────────┐
         │  ROLLBACK (Emergency)    │
         │  Restore previous bucket │
         │  Duration: < 2 minutes   │
         └──────────────────────────┘
```

### 6.2 State Machine

```
File States:
STAGED → VALIDATING → PROMOTING → PRODUCTION → ARCHIVE
   │         │
   ├─────────┴──→ FAILED (validation fails)
   │
   └─────────────→ DELETED (admin rejects)

Bucket States:
ACTIVE → ARCHIVED → DELETED
   ↓
ROLLED_BACK → ACTIVE (restore previous version)
```

### 6.3 Atomic Operations

**Critical Atomic Operations:**
1. Production pointer switch (Phase 4, step 9)
2. Rollback pointer switch

**Transaction Wrapper:**
```python
@atomic_transaction
def switch_production_pointer(old_bucket_id, new_bucket_id):
    """MUST complete fully or rollback completely"""
    update_bucket(old_bucket_id, is_current_production=False)
    update_bucket(new_bucket_id, is_current_production=True)
```

---

## 7. Implementation Timeline

### Week 1: Foundation
- [ ] Set up GCP project
- [ ] Create GCS buckets
- [ ] Set up Cloud SQL database
- [ ] Create database tables
- [ ] Set up service accounts and IAM

### Week 2: Phase 1 & 2
- [ ] Implement file upload handler
- [ ] Implement SHA-256 hashing
- [ ] Implement GCS upload
- [ ] Implement Excel parser
- [ ] Implement validation test runner
- [ ] Test with sample files

### Week 3: Phase 3 & 4
- [ ] Implement promotion planner
- [ ] Implement bucket creation
- [ ] Implement file copy with verification
- [ ] Implement corpus management
- [ ] Implement atomic pointer switch
- [ ] Test promotion workflow

### Week 4: Phase 5, 6 & Rollback
- [ ] Implement archival logic
- [ ] Implement cleanup scheduler
- [ ] Implement rollback mechanism
- [ ] Test complete end-to-end workflow
- [ ] Load testing

### Week 5: Polish & Deploy
- [ ] Error handling improvements
- [ ] Logging and monitoring
- [ ] Admin UI/CLI
- [ ] Documentation
- [ ] Production deployment

---

## 8. Testing Strategy

### 8.1 Unit Tests
```
✅ File upload validation
✅ Hash computation
✅ Version management
✅ Excel parsing
✅ Query evaluation
✅ Checksum verification
✅ Metadata operations
```

### 8.2 Integration Tests
```
✅ End-to-end upload flow
✅ Validation with real corpus
✅ Promotion workflow
✅ Rollback procedure
✅ Archive and cleanup
```

### 8.3 Load Tests
```
✅ Concurrent file uploads
✅ Bulk promotion (100+ files)
✅ Large file handling (50MB)
✅ Query performance under load
```

### 8.4 Failure Tests
```
✅ Network failure during upload
✅ Checksum mismatch
✅ Validation failure scenarios
✅ Partial promotion rollback
✅ Corpus creation failure
```

---

## 9. Deployment Plan

### 9.1 Pre-Deployment Checklist

**Infrastructure:**
- [ ] GCS buckets created
- [ ] Cloud SQL database provisioned
- [ ] Service accounts configured
- [ ] IAM permissions set
- [ ] Vertex AI API enabled

**Code:**
- [ ] All phases implemented
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Error handling tested
- [ ] Logging configured

**Documentation:**
- [ ] Admin runbook
- [ ] Troubleshooting guide
- [ ] Rollback procedures
- [ ] Excel template

### 9.2 Deployment Steps

**Step 1: Database Setup**
```bash
# Run SQL migrations
python manage.py migrate

# Create initial bucket metadata
python scripts/init_buckets.py
```

**Step 2: Initial Production Bucket**
```bash
# Create prod-bucket-v1 with existing documents
python scripts/seed_production.py \
  --source-path gs://existing-docs/ \
  --version 1
```

**Step 3: Deploy Agent**
```bash
# Deploy to Cloud Run / GKE
gcloud run deploy admin-agent \
  --image gcr.io/project/admin-agent:v1 \
  --service-account admin-agent@project.iam.gserviceaccount.com
```

**Step 4: Smoke Tests**
```bash
# Verify agent is working
python tests/smoke_test.py --env production
```

### 9.3 Post-Deployment

**Monitoring:**
- Set up Cloud Logging queries
- Configure alerting (promotion failures, rollbacks)
- Create dashboard (files by status, promotion rate)

**First Promotion:**
- Upload 1-2 test files
- Run through complete workflow
- Verify production serves new files
- Test rollback

---

## 10. Operational Runbook

### 10.1 Daily Operations

**Check System Health:**
```sql
-- Check current production
SELECT bucket_name, bucket_version, total_files
FROM bucket_metadata
WHERE is_current_production = TRUE;

-- Check pending promotions
SELECT COUNT(*) FROM file_metadata
WHERE validation_status = 'PASS' AND status = 'VALIDATING';

-- Check recent errors
SELECT * FROM audit_logs
WHERE event_type LIKE '%error%'
AND timestamp > NOW() - INTERVAL '24 hours';
```

### 10.2 Emergency Procedures

**Rollback Production:**
```bash
# Via agent
agent rollback --reason "High error rate in production"

# Manual (if agent unavailable)
python scripts/emergency_rollback.py \
  --to-version 5 \
  --reason "Agent unavailable"
```

**System Recovery:**
```bash
# If database is corrupted
python scripts/rebuild_metadata.py --from-gcs

# If corpus is broken
python scripts/rebuild_corpus.py \
  --bucket prod-bucket-v6 \
  --corpus production-corpus-v6
```

### 10.3 Maintenance

**Monthly Cleanup:**
```bash
# Clean up old staging archives (> 30 days)
python scripts/cleanup_staging.py --older-than 30

# Verify archive integrity
python scripts/verify_archive.py
```

**Quarterly Review:**
```sql
-- Check storage usage
SELECT 
  bucket_type,
  SUM(total_size_bytes) / 1024 / 1024 / 1024 as size_gb
FROM bucket_metadata
GROUP BY bucket_type;

-- Check promotion history
SELECT 
  DATE_TRUNC('month', promoted_at) as month,
  COUNT(*) as promotions
FROM file_metadata
WHERE promoted_at IS NOT NULL
GROUP BY month
ORDER BY month DESC;
```

---

## 11. Success Metrics

### 11.1 KPIs

**Reliability:**
- Promotion success rate: > 99%
- Rollback time: < 2 minutes
- Zero data loss incidents

**Performance:**
- Upload to staging: < 5 seconds
- Validation time: < 2 minutes
- Promotion time: < 1 minute

**Quality:**
- Validation pass rate: > 95%
- Smoke test pass rate: 100%
- Checksum verification: 100%

### 11.2 Monitoring Queries

```sql
-- Promotion success rate (last 30 days)
SELECT 
  COUNT(CASE WHEN status = 'PRODUCTION' THEN 1 END) * 100.0 / COUNT(*) as success_rate
FROM file_metadata
WHERE promoted_at > NOW() - INTERVAL '30 days';

-- Average promotion time
SELECT 
  AVG(EXTRACT(EPOCH FROM (promoted_at - uploaded_at))) as avg_seconds
FROM file_metadata
WHERE promoted_at IS NOT NULL;

-- Rollback frequency
SELECT COUNT(*) as rollbacks
FROM audit_logs
WHERE event_type = 'rollback.completed'
AND timestamp > NOW() - INTERVAL '30 days';
```

---

## 12. Risk Mitigation

### 12.1 Identified Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during promotion | CRITICAL | Checksums + atomic operations + rollback |
| Concurrent modifications | HIGH | Document locking mechanism |
| Corpus creation failure | HIGH | Retry logic + manual fallback |
| Database corruption | MEDIUM | Daily backups + rebuild from GCS |
| Network failures | LOW | Retry with exponential backoff |

### 12.2 Backup Strategy

**Database Backups:**
- Automated daily backups (Cloud SQL)
- Point-in-time recovery enabled
- 30-day retention

**GCS Versioning:**
- Object versioning enabled on archive-bucket
- Retention policy prevents accidental deletion

**Disaster Recovery:**
- Complete metadata can be rebuilt from GCS
- Corpora can be reconstructed from buckets
- RTO: 4 hours
- RPO: 0 (no data loss)

---

## 13. Future Enhancements

### Phase 2 Features (Post-MVP)

- [ ] **Bulk Operations:** Upload and promote 100+ files at once
- [ ] **Scheduled Promotions:** Promote at specific time (e.g., 2am)
- [ ] **Approval Workflows:** Multi-level approval for production
- [ ] **A/B Testing:** Run parallel production versions
- [ ] **Auto-Rollback:** Automatic rollback on error threshold
- [ ] **Metrics Dashboard:** Real-time visualization
- [ ] **Slack Notifications:** Alert on promotions/rollbacks
- [ ] **Version Diff:** Show changes between versions
- [ ] **Semantic Versioning:** Support v1.2.3 format
- [ ] **Document Dependencies:** Link related documents

---

## 14. Appendix

### 14.1 Service Account Permissions

**admin-agent@project.iam.gserviceaccount.com:**
```
GCS Permissions:
- staging-bucket: roles/storage.objectAdmin
- prod-bucket-*: roles/storage.objectCreator (write-only)
- archive-bucket: roles/storage.objectCreator (append-only)
- staging-archive-bucket: roles/storage.objectAdmin

Vertex AI:
- roles/aiplatform.admin (corpus management)

Cloud SQL:
- roles/cloudsql.client
```

**rollback-agent@project.iam.gserviceaccount.com:**
```
GCS Permissions:
- prod-bucket-*: roles/storage.objectAdmin (delete for rollback)
- archive-bucket: roles/storage.objectViewer (read-only)

Vertex AI:
- roles/aiplatform.admin (pointer updates)
```

### 14.2 Cost Estimation

**Monthly Costs (Estimated):**
```
GCS Storage:
- staging-bucket: 10 GB × $0.02 = $0.20
- prod-bucket-vN: 100 GB × $0.02 = $2.00
- archive-bucket: 500 GB × $0.01 (Nearline) = $5.00

Cloud SQL:
- db-n1-standard-1: $45/month

Vertex AI:
- RAG corpus: $0.30 per 1M queries
- Estimate: 1M queries/month = $0.30

Total: ~$55/month
```

### 14.3 Glossary

| Term | Definition |
|------|------------|
| **doc_id** | Stable logical identifier for a document (e.g., "user-manual") |
| **version** | Sequential number tracking document updates (v1, v2, v3...) |
| **content_hash** | SHA-256 hash of file content for deduplication |
| **bucket_version** | Production bucket version number (prod-bucket-v6) |
| **corpus** | Vertex AI RAG index containing document embeddings |
| **promotion** | Process of moving validated files to production |
| **rollback** | Reverting to a previous production version |
| **atomic operation** | All-or-nothing operation that maintains consistency |

---

## 15. Contact & Support

**Project Owner:** [Your Name]
**Team:** RAG Infrastructure
**Repository:** [GitHub URL]
**Documentation:** [Docs URL]
**Slack Channel:** #rag-admin-agent

---

**Last Updated:** 2024-01-27
**Version:** 1.0
**Status:** Ready for Implementation

---

# 🚀 Ready to Build!

This plan provides:
✅ Complete phase-by-phase workflow
✅ Detailed database schema
✅ Implementation checklists
✅ Testing strategy
✅ Deployment plan
✅ Operational runbook

**Next Steps:**
1. Review and approve this plan
2. Set up GCP infrastructure
3. Start with Phase 1 implementation
4. Iterate through each phase
5. Deploy to production

Good luck! 🎯