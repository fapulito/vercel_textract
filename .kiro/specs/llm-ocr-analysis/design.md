# Design Document: LLM-Powered OCR Analysis

## Overview

This feature extends the existing OCR SaaS application by integrating Amazon Bedrock with Claude 3 Haiku for intelligent document analysis. The system will maintain the current AWS Textract OCR pipeline while adding an optional LLM analysis layer that provides structured insights, data extraction, and document understanding.

**Key Design Principles:**
- Minimal changes to existing codebase (2-3 hour implementation)
- Backward compatible with current OCR workflow
- Cost-effective using Claude 3 Haiku ($0.25/1M input tokens)
- Progressive enhancement: LLM analysis is optional
- Reuse existing authentication, storage, and database infrastructure

## Architecture

### High-Level Flow

```
User Upload → S3 Storage → AWS Textract (OCR) → [Optional] Amazon Bedrock (LLM) → Results Display
                                                           ↓
                                                    Structured JSON
                                                           ↓
                                                    S3 Storage + Database
```

### Component Integration

1. **Existing Components (No Changes)**
   - Flask application factory pattern
   - Google OAuth authentication
   - PostgreSQL database with SQLAlchemy
   - S3 file storage
   - AWS Textract OCR processing
   - Stripe payment integration

2. **New Components**
   - Amazon Bedrock client (boto3)
   - LLM analysis service layer
   - Document history database model
   - Enhanced result templates with tabs
   - API endpoints for Enterprise tier

## Components and Interfaces

### 1. Database Schema Extensions

**New Model: DocumentHistory**
```python
class DocumentHistory(db.Model):
    __tablename__ = 'document_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    analysis_type = db.Column(db.String(50), nullable=True)  # 'general', 'invoice', 'contract', 'form', None
    textract_job_id = db.Column(db.String(100), nullable=False)
    csv_filename = db.Column(db.String(255), nullable=False)
    json_filename = db.Column(db.String(255), nullable=True)  # LLM analysis results
    file_size = db.Column(db.Integer, nullable=False)
    page_count = db.Column(db.Integer, nullable=True)
    processing_cost = db.Column(db.Float, nullable=True)  # Track AWS costs
    
    # Relationship
    user = db.relationship('User', backref='documents')
```

**Updated Model: User**
```python
# Add new fields to existing User model
llm_analyses_this_month = db.Column(db.Integer, nullable=False, default=0)
api_key = db.Column(db.String(64), nullable=True, unique=True)  # For Enterprise tier
api_key_created = db.Column(db.DateTime, nullable=True)
```

### 2. LLM Analysis Service

**File: `api/llm_service.py`**

```python
import boto3
import json
from typing import Dict, List, Optional

class LLMAnalyzer:
    """Service for analyzing OCR text using Amazon Bedrock"""
    
    def __init__(self, region_name: str):
        self.bedrock = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
        
    def analyze_document(self, text: str, analysis_type: str) -> Dict:
        """
        Analyze extracted text using Claude 3 Haiku
        
        Args:
            text: OCR extracted text from Textract
            analysis_type: One of 'general', 'invoice', 'contract', 'form'
            
        Returns:
            Structured JSON with analysis results
        """
        prompt = self._build_prompt(text, analysis_type)
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1  # Low temperature for consistent extraction
        }
        
        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        analysis_text = response_body['content'][0]['text']
        
        # Parse JSON from response
        return self._parse_analysis(analysis_text, analysis_type)
    
    def _build_prompt(self, text: str, analysis_type: str) -> str:
        """Build specialized prompts for different document types"""
        
        base_instruction = f"""Analyze the following document text and extract structured information.
Return your response as valid JSON only, with no additional text.

Document text:
{text[:4000]}  # Limit to ~4000 chars to stay within token limits

"""
        
        prompts = {
            'general': base_instruction + """
Provide a JSON response with:
{
  "summary": "Brief 2-3 sentence summary",
  "key_points": ["point1", "point2", "point3"],
  "document_type": "detected type (e.g., letter, report, form)",
  "entities": {
    "people": [],
    "organizations": [],
    "dates": [],
    "locations": []
  }
}""",
            
            'invoice': base_instruction + """
Extract invoice information as JSON:
{
  "vendor": "Company name",
  "invoice_number": "INV-123",
  "date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "total_amount": "123.45",
  "currency": "USD",
  "line_items": [
    {"description": "Item", "quantity": 1, "unit_price": "10.00", "total": "10.00"}
  ],
  "tax": "0.00",
  "subtotal": "123.45"
}""",
            
            'contract': base_instruction + """
Extract contract information as JSON:
{
  "contract_type": "Type of agreement",
  "parties": ["Party A", "Party B"],
  "effective_date": "YYYY-MM-DD",
  "expiration_date": "YYYY-MM-DD",
  "key_terms": [
    {"term": "Payment terms", "details": "Net 30"},
    {"term": "Termination", "details": "30 days notice"}
  ],
  "obligations": {
    "party_a": ["obligation1", "obligation2"],
    "party_b": ["obligation1", "obligation2"]
  },
  "important_clauses": ["clause1", "clause2"]
}""",
            
            'form': base_instruction + """
Extract form fields as JSON:
{
  "form_type": "Type of form",
  "fields": [
    {"label": "Name", "value": "John Doe"},
    {"label": "Date", "value": "2024-01-01"},
    {"label": "Signature", "value": "Present/Absent"}
  ],
  "checkboxes": [
    {"label": "Option A", "checked": true},
    {"label": "Option B", "checked": false}
  ],
  "completeness": "Complete/Incomplete/Partially Complete"
}"""
        }
        
        return prompts.get(analysis_type, prompts['general'])
    
    def _parse_analysis(self, analysis_text: str, analysis_type: str) -> Dict:
        """Parse and validate JSON response from Claude"""
        try:
            # Extract JSON from response (Claude might add explanation)
            start = analysis_text.find('{')
            end = analysis_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = analysis_text[start:end]
                return json.loads(json_str)
            else:
                # Fallback if no JSON found
                return {"error": "Could not parse JSON", "raw_response": analysis_text}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw_response": analysis_text}
```

### 3. Updated Route Handlers

**New Routes in `api/index.py`:**

```python
# Add after existing routes

@app.route('/upload', methods=['POST'])
@login_required
@check_usage_limit
def upload():
    # ... existing S3 upload code ...
    
    # NEW: Check if LLM analysis is requested
    enable_llm = request.form.get('enable_llm') == 'true'
    analysis_type = request.form.get('analysis_type', 'general')
    
    # Store in session for later use
    session['enable_llm'] = enable_llm
    session['analysis_type'] = analysis_type if enable_llm else None
    
    # ... rest of existing code ...

@app.route('/process_result/<job_id>/<original_filename>')
@login_required
def process_result(job_id, original_filename):
    textract = boto3.client('textract', region_name=os.environ.get('AWS_REGION'))
    
    try:
        response = textract.get_document_text_detection(JobId=job_id)
        
        if response.get('JobStatus') == 'SUCCEEDED':
            blocks = get_all_textract_blocks(job_id, response)
            csv_filename = create_and_upload_csv(blocks, original_filename)
            
            # NEW: LLM Analysis
            json_filename = None
            enable_llm = session.get('enable_llm', False)
            analysis_type = session.get('analysis_type')
            
            if enable_llm and analysis_type:
                # Check LLM quota
                if check_llm_quota(current_user):
                    # Extract text from blocks
                    text = '\n'.join([block['Text'] for block in blocks if block['BlockType'] == 'LINE'])
                    
                    # Analyze with LLM
                    from api.llm_service import LLMAnalyzer
                    analyzer = LLMAnalyzer(os.environ.get('AWS_REGION'))
                    analysis_result = analyzer.analyze_document(text, analysis_type)
                    
                    # Upload JSON to S3
                    json_filename = upload_json_to_s3(analysis_result, original_filename)
                    
                    # Increment LLM usage
                    current_user.llm_analyses_this_month += 1
                    db.session.commit()
            
            # NEW: Save to history
            save_to_history(
                user_id=current_user.id,
                filename=original_filename,
                textract_job_id=job_id,
                csv_filename=csv_filename,
                json_filename=json_filename,
                analysis_type=analysis_type
            )
            
            return redirect(url_for('success', csv_filename=csv_filename, json_filename=json_filename))
            
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/history')
@login_required
def history():
    """Display user's document processing history"""
    documents = DocumentHistory.query.filter_by(user_id=current_user.id)\
        .order_by(DocumentHistory.upload_date.desc())\
        .limit(50)\
        .all()
    
    return render_template('history.html', documents=documents)

@app.route('/history/<int:doc_id>')
@login_required
def view_history_item(doc_id):
    """View a specific document from history"""
    doc = DocumentHistory.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    
    # Generate presigned URLs
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
    csv_url = s3.generate_presigned_url('get_object', 
        Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': doc.csv_filename},
        ExpiresIn=300)
    
    json_url = None
    if doc.json_filename:
        json_url = s3.generate_presigned_url('get_object',
            Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': doc.json_filename},
            ExpiresIn=300)
    
    return render_template('result.html', 
        csv_filename=doc.csv_filename,
        json_filename=doc.json_filename,
        download_url=csv_url,
        json_url=json_url,
        from_history=True)

# API Routes for Enterprise Tier
@app.route('/api/v1/analyze', methods=['POST'])
def api_analyze():
    """API endpoint for document analysis"""
    # Authenticate via API key
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = User.query.filter_by(api_key=api_key, tier='enterprise').first()
    
    if not user:
        return jsonify({'error': 'Invalid API key or insufficient permissions'}), 401
    
    # Rate limiting check (100 requests/hour)
    # Implementation using Redis or database timestamps
    
    # Process uploaded file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    # ... similar processing logic as web upload ...
    
    return jsonify({
        'job_id': job_id,
        'status': 'processing',
        'status_url': url_for('api_status', job_id=job_id, _external=True)
    })

@app.route('/api/v1/status/<job_id>')
def api_status(job_id):
    """Check processing status via API"""
    # Authenticate and return status
    pass

@app.route('/api/v1/result/<job_id>')
def api_result(job_id):
    """Retrieve results via API"""
    # Authenticate and return JSON results
    pass
```

### 4. Helper Functions

```python
def check_llm_quota(user: User) -> bool:
    """Check if user has remaining LLM analysis quota"""
    limits = {
        'free': 2,
        'pro': 50,
        'enterprise': 500
    }
    
    # Reset monthly counter if needed
    if user.usage_reset_date < datetime.datetime.utcnow() - datetime.timedelta(days=30):
        user.llm_analyses_this_month = 0
        user.usage_reset_date = datetime.datetime.utcnow()
        db.session.commit()
    
    return user.llm_analyses_this_month < limits.get(user.tier, 0)

def upload_json_to_s3(analysis_result: Dict, original_filename: str) -> str:
    """Upload LLM analysis JSON to S3"""
    s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
    
    base_filename = os.path.splitext(original_filename)[0]
    json_filename = f"{base_filename}_analysis.json"
    
    json_bytes = json.dumps(analysis_result, indent=2).encode('utf-8')
    bytes_buffer = io.BytesIO(json_bytes)
    
    s3.upload_fileobj(bytes_buffer, os.environ.get('S3_BUCKET'), json_filename,
        ExtraArgs={'ContentType': 'application/json'})
    
    return json_filename

def save_to_history(user_id: int, filename: str, textract_job_id: str,
                   csv_filename: str, json_filename: Optional[str],
                   analysis_type: Optional[str]) -> None:
    """Save document processing record to history"""
    doc = DocumentHistory(
        user_id=user_id,
        filename=filename,
        textract_job_id=textract_job_id,
        csv_filename=csv_filename,
        json_filename=json_filename,
        analysis_type=analysis_type,
        file_size=0,  # Can be populated from S3 metadata
        page_count=None  # Can be extracted from Textract response
    )
    db.session.add(doc)
    db.session.commit()
```

## Data Models

### Pricing Tier Comparison

| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| Documents/month | 5 | 200 | 1000 |
| LLM Analyses/month | 2 | 50 | 500 |
| Max pages | 3 | 50 | 100 |
| Max file size | 2MB | 5MB | 50MB |
| History retention | 90 days | 365 days | 730 days |
| API access | ❌ | ❌ | ✅ |
| Price | $0 | $10/mo | $99/mo |

### Cost Analysis

**AWS Service Costs (per document):**
- Textract: ~$0.0015 per page (1 page avg)
- S3 Storage: ~$0.000023 per MB per month
- Bedrock Claude 3 Haiku: ~$0.0001 per analysis (400 tokens avg)
- Total per LLM analysis: ~$0.0016

**Profitability:**
- Free tier: 2 LLM analyses = $0.0032 cost (acceptable for acquisition)
- Pro tier: $10/month, 50 analyses = $0.08 cost = 99.2% margin
- Enterprise tier: $99/month, 500 analyses = $0.80 cost = 99.2% margin

## Error Handling

### LLM Analysis Failures

1. **Bedrock API Errors**
   - Catch `boto3` exceptions
   - Fall back to OCR-only results
   - Display user-friendly message: "AI analysis unavailable, showing text extraction only"

2. **JSON Parsing Errors**
   - Return raw LLM response in error field
   - Log for debugging
   - Don't block user from accessing OCR results

3. **Quota Exceeded**
   - Check before calling Bedrock
   - Display upgrade prompt with clear messaging
   - Show remaining quota on upload page

### Database Failures

- Use existing connection pool settings
- Graceful degradation: history feature optional
- Don't block core OCR functionality

## Testing Strategy

### Unit Tests (Optional)

- Test LLM prompt building for each document type
- Test JSON parsing with various Claude responses
- Test quota checking logic
- Test API authentication

### Integration Tests (Optional)

- End-to-end flow: upload → OCR → LLM → results
- Test with sample invoices, contracts, forms
- Verify S3 uploads for JSON files
- Test history retrieval

### Manual Testing (Required)

1. Upload document with LLM analysis enabled
2. Verify both CSV and JSON results
3. Test each analysis type (general, invoice, contract, form)
4. Verify quota enforcement
5. Test history page display
6. Test Enterprise API endpoints with Postman

## Security Considerations

1. **API Keys**
   - Generate cryptographically secure random keys
   - Store hashed in database (optional enhancement)
   - Rate limit API endpoints

2. **S3 Access**
   - Continue using presigned URLs
   - Short expiration times (5 minutes)
   - No public bucket access

3. **LLM Input Sanitization**
   - Limit text length to prevent token abuse
   - No user-provided prompts (only predefined types)

## Performance Optimization

1. **Async Processing**
   - LLM analysis runs after Textract completes
   - No additional user wait time
   - Results available when page loads

2. **Caching**
   - Store LLM results in S3
   - Reuse from history instead of reprocessing

3. **Token Optimization**
   - Limit input text to 4000 characters
   - Use Claude 3 Haiku (fastest, cheapest)
   - Low temperature (0.1) for consistent results

## Deployment Considerations

### Environment Variables

Add to `.env` and Vercel:
```
AWS_BEDROCK_REGION=us-east-1  # Bedrock availability
ADMIN_EMAIL=your-email@example.com  # For admin access
```

### Database Migration

Run after deployment:
```python
flask db upgrade  # If using Flask-Migrate
# OR
flask --app api.index:create_app init-db  # Recreate tables
```

### Vercel Configuration

No changes needed - existing `vercel.json` works with new routes.

## Future Enhancements (Out of Scope)

- Multi-language support for OCR
- Batch processing API
- Webhook notifications for async results
- Custom LLM prompts for Enterprise users
- Document comparison and diff analysis
- Integration with popular business tools (Slack, email)
