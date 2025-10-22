# Implementation Plan

- [x] 1. Update database models and configuration

  - Add new fields to User model: `llm_analyses_this_month`, `api_key`, `api_key_created`
  - Create DocumentHistory model with all required fields
  - Update PLAN_LIMITS dictionary to include Enterprise tier and LLM quotas
  - Add database migration/initialization for new tables
  - _Requirements: 1.1, 4.1, 4.2, 4.3, 5.1, 5.2_

- [x] 2. Implement LLM analysis service

  - [x] 2.1 Create `api/llm_service.py` with LLMAnalyzer class

    - Implement `__init__` method with Bedrock client initialization
    - Implement `analyze_document` method for Claude 3 Haiku invocation
    - Implement `_build_prompt` method with 4 specialized prompts (general, invoice, contract, form)
    - Implement `_parse_analysis` method for JSON extraction and validation
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Add helper functions for LLM workflow

  - [x] 3.1 Implement `check_llm_quota` function

    - Check user tier and monthly usage
    - Reset counter if month has passed
    - Return boolean for quota availability

    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 3.2 Implement `upload_json_to_s3` function

    - Convert analysis dict to JSON bytes
    - Generate filename from original document name
    - Upload to S3 with proper content type
    - Return S3 key for storage
    - _Requirements: 1.5_

  - [x] 3.3 Implement `save_to_history` function

    - Create DocumentHistory record
    - Store all metadata (filenames, job IDs, analysis type)
    - Commit to database
    - _Requirements: 3.1, 3.2_

- [x] 4. Update upload route for LLM options

  - Modify `/upload` POST route to accept `enable_llm` and `analysis_type` form parameters
  - Store LLM preferences in Flask session
  - Maintain backward compatibility (LLM is optional)
  - _Requirements: 1.1, 2.1_

- [x] 5. Enhance result processing with LLM analysis

  - [x] 5.1 Update `/process_result/<job_id>/<filename>` route

    - Check session for LLM enablement
    - Call `check_llm_quota` before processing
    - Extract text from Textract blocks
    - Invoke LLMAnalyzer if enabled and quota available
    - Upload JSON results to S3
    - Increment user's LLM usage counter
    - Call `save_to_history` with all metadata
    - Pass json_filename to success route
    - _Requirements: 1.2, 1.3, 4.4_

- [x] 6. Update success/result display

  - [x] 6.1 Modify `/success/<csv_filename>` route

    - Accept optional json_filename parameter
    - Generate presigned URL for JSON file if present
    - Pass both URLs to template
    - _Requirements: 1.4, 1.5_

  - [x] 6.2 Update `templates/result.html`

    - Add tab interface for "Text" and "Analysis" views
    - Display CSV preview in Text tab (existing functionality)
    - Display formatted JSON in Analysis tab with proper styling
    - Show analysis type badge
    - Provide download buttons for both CSV and JSON
    - _Requirements: 1.4, 1.5_

- [x] 7. Implement document history feature

  - [x] 7.1 Create `/history` route

    - Query DocumentHistory for current user
    - Order by upload_date descending
    - Limit to 50 most recent documents
    - Render history.html template
    - _Requirements: 3.2_

  - [x] 7.2 Create `/history/<int:doc_id>` route

    - Query specific document by ID and user_id
    - Generate presigned URLs for CSV and JSON
    - Render result.html with from_history flag
    - _Requirements: 3.3, 3.4_

  - [x] 7.3 Create `templates/history.html`

    - Display table of documents with filename, date, type, analysis type
    - Add clickable rows linking to view_history_item
    - Show download icons for CSV/JSON
    - Add "Back to Upload" navigation
    - _Requirements: 3.2_

- [x] 8. Update upload interface with LLM options

  - [x] 8.1 Modify `templates/index.html`

    - Add checkbox for "Enable AI Analysis"
    - Add dropdown for analysis type (General, Invoice, Contract, Form)
    - Display remaining LLM quota for current user
    - Show tier comparison table with LLM limits
    - Add link to history page
    - _Requirements: 1.1, 2.1, 4.3, 4.4_

- [x] 9. Implement Enterprise tier and pricing updates

  - [x] 9.1 Update Stripe integration

    - Add Enterprise tier price ID to environment variables
    - Update checkout session creation for Enterprise tier
    - Handle Enterprise tier webhook events
    - _Requirements: 5.3_

  - [x] 9.2 Add API key generation for Enterprise users

    - Create `/api/generate-key` route (Enterprise only)
    - Generate cryptographically secure random key
    - Store in user.api_key field
    - Display key once to user
    - _Requirements: 6.1_

- [ ]\* 10. Implement Enterprise API endpoints

  - [ ]\* 10.1 Create `/api/v1/analyze` POST endpoint

    - Authenticate via Bearer token (API key)
    - Validate Enterprise tier access
    - Accept file upload
    - Process with Textract and optional LLM
    - Return job_id and status_url
    - _Requirements: 6.2, 6.3_

  - [ ]\* 10.2 Create `/api/v1/status/<job_id>` GET endpoint

    - Authenticate via API key
    - Return processing status
    - _Requirements: 6.2_

  - [ ]\* 10.3 Create `/api/v1/result/<job_id>` GET endpoint

    - Authenticate via API key
    - Return JSON with CSV and analysis URLs
    - _Requirements: 6.4_

  - [ ]\* 10.4 Implement API rate limiting
    - Track requests per API key per hour
    - Limit to 100 requests/hour
    - Return 429 status when exceeded
    - _Requirements: 6.5_

- [ ]\* 11. Add cost tracking and monitoring

  - [ ]\* 11.1 Implement cost calculation

    - Calculate Textract cost per page
    - Calculate Bedrock cost per token
    - Store in DocumentHistory.processing_cost
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]\* 11.2 Create admin cost dashboard
    - Add `/admin/costs` route
    - Display aggregate costs by tier
    - Show profit margins
    - _Requirements: 7.4, 7.5_

- [x] 12. Create README-2.md for hackathon submission

  - Document the AI Agent capabilities
  - Explain LLM-powered document analysis features
  - Include architecture diagram
  - Add setup instructions for Amazon Bedrock
  - Document API usage for Enterprise tier
  - Add MIT License
  - Include demo screenshots/examples
  - Highlight AWS services used (Textract, Bedrock, S3)
  - _Requirements: All_

- [x] 13. Update dependencies and environment

  - Add boto3 Bedrock support (already in requirements.txt)
  - Document new environment variables in README-2.md
  - Test Bedrock permissions in IAM policy
  - _Requirements: All_

- [ ]\* 14. Testing and validation

  - [ ]\* 14.1 Test LLM analysis with sample documents

    - Test general summary with letter document
    - Test invoice extraction with sample invoice
    - Test contract analysis with sample agreement
    - Test form extraction with sample form
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ]\* 14.2 Test quota enforcement

    - Verify Free tier limited to 2 LLM analyses
    - Verify Pro tier limited to 50 analyses
    - Verify monthly reset functionality
    - _Requirements: 4.1, 4.2, 4.5_

  - [ ]\* 14.3 Test history functionality

    - Upload multiple documents
    - Verify history page displays correctly
    - Test viewing historical results
    - Test download links from history
    - _Requirements: 3.2, 3.3, 3.4_

  - [ ]\* 14.4 Test Enterprise API
    - Generate API key
    - Test authentication
    - Test rate limiting
    - Verify JSON responses
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
