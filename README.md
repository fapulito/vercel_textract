# AI-Powered Document Intelligence Platform
## AWS AI Agent Global Hackathon Submission

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AWS](https://img.shields.io/badge/AWS-Textract%20%7C%20Bedrock%20%7C%20S3-orange)](https://aws.amazon.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green)](https://flask.palletsprojects.com/)

## 🎯 Project Overview

This application transforms traditional OCR into an **intelligent document analysis platform** by combining AWS Textract with Amazon Bedrock's Claude AI. It demonstrates autonomous AI agent capabilities by not just extracting text, but understanding, categorizing, and structuring document content without human intervention.

### What Makes This an AI Agent?

- **Autonomous Decision Making**: The system automatically selects specialized analysis strategies based on document type
- **Complex Task Execution**: Combines multiple AWS services (Textract → Bedrock → S3) in a coordinated workflow
- **Intelligent Reasoning**: Uses Claude 3 Haiku to extract structured insights, identify entities, and understand context
- **Self-Service Operation**: Processes documents end-to-end without human intervention once configured

## ✨ Key Features

### 🤖 AI-Powered Document Analysis
- **General Summary**: Extracts key points, entities (people, organizations, dates, locations), and document type
- **Invoice/Receipt Analysis**: Automatically extracts vendor, amounts, line items, dates, and tax information
- **Contract Review**: Identifies parties, key terms, obligations, important clauses, and dates
- **Form Data Extraction**: Structures form fields, checkboxes, and completeness status

### 📊 Document Processing
- **OCR with AWS Textract**: High-accuracy text extraction from PDFs and images
- **Real-time Status Tracking**: Live updates during document processing
- **CSV & JSON Export**: Download raw text and structured analysis results
- **Document History**: Access previous analyses without reprocessing

### 💼 Freemium Business Model
- **Free Tier**: 5 documents/month, 2 LLM analyses, 3 pages max
- **Pro Tier**: 200 documents/month, 50 LLM analyses, 50 pages max ($10/month)
- **Enterprise Tier**: 1000 documents/month, 500 LLM analyses, API access ($99/month)

### 🔐 Security & Authentication
- Google OAuth 2.0 integration
- Secure S3 presigned URLs for downloads
- API key authentication for Enterprise users

## 🏗️ Architecture

### High-Level System Design

```mermaid
graph TB
    subgraph "Client Layer"
        User[👤 User Browser]
    end

    subgraph "Vercel Platform"
        subgraph "Flask Application"
            WebApp[🌐 Flask Web Server]
            LLM[🧠 LLM Analyzer<br/>Claude Integration]
            Auth[🔐 Authentication]
        end
    end

    subgraph "AWS Cloud Services"
        S3[📦 Amazon S3<br/>Document Storage]
        Textract[📄 AWS Textract<br/>OCR Processing]
        Bedrock[🤖 Amazon Bedrock<br/>Claude 3 Haiku]
    end

    subgraph "External Services"
        Google[🔑 Google OAuth]
        Stripe[💳 Stripe Payments]
        DB[(🗄️ PostgreSQL)]
    end

    User -->|Upload Document| WebApp
    WebApp -->|Store| S3
    WebApp -->|Extract Text| Textract
    Textract -->|Read| S3
    WebApp -->|Analyze| Bedrock
    Bedrock -->|Structured Insights| WebApp
    WebApp -->|Save Results| S3
    WebApp -->|Track Usage| DB
    User -->|Authenticate| Google
    User -->|Subscribe| Stripe

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px
    classDef vercel fill:#000000,stroke:#FFFFFF,stroke-width:2px,color:#FFFFFF
    classDef external fill:#4285F4,stroke:#1967D2,stroke-width:2px,color:#FFFFFF
    
    class S3,Textract,Bedrock aws
    class WebApp,LLM,Auth vercel
    class Google,Stripe,DB external
```

### AI Agent Workflow

```
1. Document Upload
   ↓
2. AWS Textract OCR
   ↓
3. Text Extraction
   ↓
4. [AI Agent Decision Point]
   ├─ Check user quota
   ├─ Determine analysis type
   └─ Select specialized prompt
   ↓
5. Amazon Bedrock (Claude 3 Haiku)
   ├─ Understand document context
   ├─ Extract structured data
   └─ Generate insights
   ↓
6. JSON Structure & Validation
   ↓
7. Store Results (S3 + Database)
   ↓
8. Present to User
```

## 🚀 AWS Services Used

### 1. **Amazon Textract**
- **Purpose**: OCR text extraction from documents
- **Features Used**: 
  - `StartDocumentTextDetection` for async processing
  - `GetDocumentTextDetection` for result retrieval
  - Multi-page document support
- **Cost**: ~$0.0015 per page

### 2. **Amazon Bedrock (Claude 3 Haiku)**
- **Purpose**: LLM-powered document intelligence
- **Features Used**:
  - Anthropic Claude 3 Haiku model
  - Structured JSON output generation
  - Low-temperature inference for consistency
- **Cost**: ~$0.25 per 1M input tokens, ~$1.25 per 1M output tokens
- **Why Claude 3 Haiku**: Fast, cost-effective, excellent at structured extraction

### 3. **Amazon S3**
- **Purpose**: Document and result storage
- **Features Used**:
  - Document upload and storage
  - CSV and JSON result hosting
  - Presigned URLs for secure downloads
  - 90-730 day retention policies
- **Cost**: ~$0.023 per GB per month

### 4. **AWS IAM**
- **Purpose**: Security and access control
- **Permissions Required**:
  - `s3:PutObject`, `s3:GetObject`
  - `textract:StartDocumentTextDetection`, `textract:GetDocumentTextDetection`
  - `bedrock:InvokeModel`

## 📋 Setup Instructions

### Prerequisites
- Python 3.9 or higher
- AWS Account with Bedrock access (see setup steps below)
- Google Cloud Project (for OAuth)
- Stripe Account (for payments)
- PostgreSQL database (Neon recommended)
- AWS CLI (optional, for manual testing)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <project-directory>
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Note**: All required dependencies are listed in `requirements.txt`, including:
- `boto3` - AWS SDK for Python (includes Bedrock support)
- `Flask` - Web framework
- `psycopg2-binary` - PostgreSQL adapter
- `stripe` - Payment processing
- `cryptography` - Secure key generation

### 4. Configure AWS Services

#### Enable Amazon Bedrock
1. Go to AWS Console → Amazon Bedrock
2. Navigate to "Model access" in the left sidebar
3. Click "Manage model access"
4. Enable "Anthropic Claude 3 Haiku"
5. Wait for access to be granted (usually instant)

#### Create IAM User
1. Go to AWS Console → IAM
2. Create new user with programmatic access
3. Attach the following policy (also available in `.iampolicyaws.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:StartDocumentTextDetection",
        "textract:GetDocumentTextDetection"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
    }
  ]
}
```

**Important**: Replace `YOUR_BUCKET_NAME` with your actual S3 bucket name.

4. Save the Access Key ID and Secret Access Key

**Minimum Required Permissions**:
- `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` - For document storage
- `textract:StartDocumentTextDetection`, `textract:GetDocumentTextDetection` - For OCR
- `bedrock:InvokeModel` - For LLM analysis with Claude 3 Haiku

#### Create S3 Bucket
```bash
aws s3 mb s3://your-bucket-name --region us-east-1
```

### 5. Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to "APIs & Services" → "Credentials"
4. Create OAuth 2.0 Client ID
5. Add authorized redirect URIs:
   - `http://127.0.0.1:5000/login/callback` (local)
   - `https://your-app.vercel.app/login/callback` (production)
6. Save Client ID and Client Secret

### 6. Configure Stripe

1. Sign up at [Stripe](https://stripe.com/)
2. Create products for Pro and Enterprise tiers
3. Get API keys from Dashboard
4. Set up webhook endpoint: `https://your-app.vercel.app/stripe-webhook`

### 7. Set Environment Variables

Create a `.env` file in the project root:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name

# Note: AWS_REGION is used for all AWS services (S3, Textract, and Bedrock)
# Ensure your region supports Amazon Bedrock with Claude 3 Haiku.
# Recommended regions for full feature support:
# - us-east-1 (N. Virginia) - RECOMMENDED
# - us-west-2 (Oregon)
# - ap-southeast-1 (Singapore)
# - eu-central-1 (Frankfurt)
# - eu-west-3 (Paris)
# 
# Note: us-west-1 (N. California) has limited Bedrock model availability
# For full list, see: https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_DISCOVERY_URL=https://accounts.google.com/.well-known/openid-configuration

# Stripe Payment Configuration
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUBSCRIPTION_PRICE_ID=price_...  # Pro tier ($10/month)
STRIPE_ENTERPRISE_PRICE_ID=price_...    # Enterprise tier ($99/month)
STRIPE_ONETIME_PRICE_ID=price_...       # One-time payment option
STRIPE_MODE=payment                      # Default mode: 'payment' or 'subscription'

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development

# Admin Configuration (optional)
ADMIN_EMAIL=admin@example.com
```

### Environment Variable Details

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS IAM user access key with S3, Textract, and Bedrock permissions |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS IAM user secret key |
| `AWS_REGION` | Yes | AWS region (must support Bedrock, e.g., us-east-1, us-west-2) |
| `S3_BUCKET` | Yes | S3 bucket name for document storage |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth 2.0 client secret |
| `GOOGLE_DISCOVERY_URL` | Yes | Google OpenID discovery URL (usually constant) |
| `STRIPE_SECRET_KEY` | Yes | Stripe secret API key (use test key for development) |
| `STRIPE_PUBLISHABLE_KEY` | Yes | Stripe publishable API key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `STRIPE_SUBSCRIPTION_PRICE_ID` | Yes | Stripe price ID for Pro tier subscription |
| `STRIPE_ENTERPRISE_PRICE_ID` | Yes | Stripe price ID for Enterprise tier subscription |
| `STRIPE_ONETIME_PRICE_ID` | No | Stripe price ID for one-time payments |
| `STRIPE_MODE` | No | Payment mode: 'payment' or 'subscription' (default: payment) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | Flask secret key for session management (generate random string) |
| `FLASK_ENV` | No | Flask environment: 'development' or 'production' |
| `ADMIN_EMAIL` | No | Admin email for special privileges |

### 8. Verify AWS Permissions

#### Option 1: Automated Test Script (Recommended)

Run the provided test script to verify all AWS services:

```bash
python test_bedrock_connection.py
```

This script will test:
- AWS credentials configuration
- S3 bucket access
- Amazon Bedrock API access
- Claude 3 Haiku model invocation

**Expected Output**: All tests should pass (✅). If the Bedrock Invoke test fails, you need to:
1. Go to AWS Console → Amazon Bedrock → Model access
2. Click "Manage model access"
3. Enable "Anthropic Claude 3 Haiku"
4. Wait 1-2 minutes for access to be granted
5. Run the test script again

#### Option 2: Manual AWS CLI Tests

Test that your IAM user has the correct permissions:

```bash
# Test S3 access
aws s3 ls s3://your-bucket-name --region us-east-1

# Test Textract access (requires a test document in S3)
aws textract start-document-text-detection \
  --document-location '{"S3Object":{"Bucket":"your-bucket-name","Name":"test.pdf"}}' \
  --region us-east-1

# Test Bedrock access (list available models)
aws bedrock list-foundation-models --region us-east-1

# Verify Claude 3 Haiku is accessible
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --region us-east-1 \
  --query 'modelSummaries[?modelId==`anthropic.claude-3-haiku-20240307-v1:0`]'
```

If any command fails, review your IAM policy and ensure:
1. The IAM user has the policy attached (see `.iampolicyaws.json`)
2. Amazon Bedrock model access is enabled in the AWS Console
3. Your region supports Bedrock (us-east-1, us-west-2, etc.)
4. Wait a few minutes after enabling model access for permissions to propagate

### 9. Initialize Database

```bash
flask --app api.index:create_app init-db
```

### 10. Run Locally

```bash
flask --app api.index:create_app run --debug
```

Visit `http://127.0.0.1:5000`

### 11. Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Add environment variables in Vercel dashboard
# Settings → Environment Variables
# Copy all variables from your .env file
```

**Important**: When deploying to Vercel, ensure:
- All environment variables are added to the Vercel project settings
- AWS_REGION is set to a Bedrock-supported region
- IAM credentials have all required permissions
- Stripe webhook endpoint is updated to your production URL

## 🔌 Enterprise API Usage

Enterprise tier users get API access for programmatic document processing.

### Generate API Key

1. Log in to the application
2. Upgrade to Enterprise tier
3. Navigate to Settings → API Keys
4. Click "Generate New Key"
5. Copy and save the key (shown only once)

### API Endpoints

#### 1. Analyze Document
```bash
POST /api/v1/analyze
Authorization: Bearer YOUR_API_KEY
Content-Type: multipart/form-data

# Parameters:
# - file: Document file (PDF or image)
# - analysis_type: general|invoice|contract|form (optional)
# - enable_llm: true|false (optional, default: true)

# Example with curl:
curl -X POST https://your-app.vercel.app/api/v1/analyze \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@document.pdf" \
  -F "analysis_type=invoice" \
  -F "enable_llm=true"

# Response:
{
  "job_id": "abc123",
  "status": "processing",
  "status_url": "https://your-app.vercel.app/api/v1/status/abc123"
}
```

#### 2. Check Status
```bash
GET /api/v1/status/{job_id}
Authorization: Bearer YOUR_API_KEY

# Response:
{
  "job_id": "abc123",
  "status": "completed",
  "result_url": "https://your-app.vercel.app/api/v1/result/abc123"
}
```

#### 3. Get Results
```bash
GET /api/v1/result/{job_id}
Authorization: Bearer YOUR_API_KEY

# Response:
{
  "job_id": "abc123",
  "csv_url": "https://s3.amazonaws.com/...",
  "json_url": "https://s3.amazonaws.com/...",
  "analysis": {
    "vendor": "Acme Corp",
    "invoice_number": "INV-001",
    "total_amount": "1234.56",
    ...
  }
}
```

### Rate Limits
- 100 requests per hour per API key
- Returns `429 Too Many Requests` when exceeded

## 📊 Example Analysis Outputs

### General Document Analysis
```json
{
  "summary": "Employment agreement between TechCorp and John Doe for Software Engineer position starting January 2024.",
  "key_points": [
    "Full-time employment as Software Engineer",
    "Annual salary of $120,000",
    "Standard benefits package included",
    "90-day probation period"
  ],
  "document_type": "employment_contract",
  "entities": {
    "people": ["John Doe"],
    "organizations": ["TechCorp Inc."],
    "dates": ["2024-01-15", "2024-04-15"],
    "locations": ["San Francisco, CA"]
  }
}
```

### Invoice Analysis
```json
{
  "vendor": "Office Supplies Co.",
  "invoice_number": "INV-2024-001",
  "date": "2024-01-15",
  "due_date": "2024-02-15",
  "total_amount": "1,234.56",
  "currency": "USD",
  "line_items": [
    {
      "description": "Printer Paper (10 reams)",
      "quantity": 10,
      "unit_price": "25.00",
      "total": "250.00"
    },
    {
      "description": "Ink Cartridges",
      "quantity": 5,
      "unit_price": "45.00",
      "total": "225.00"
    }
  ],
  "subtotal": "1,134.56",
  "tax": "100.00"
}
```

### Contract Analysis
```json
{
  "contract_type": "Service Agreement",
  "parties": ["ABC Corp", "XYZ Services LLC"],
  "effective_date": "2024-01-01",
  "expiration_date": "2025-01-01",
  "key_terms": [
    {
      "term": "Payment Terms",
      "details": "Net 30 days from invoice date"
    },
    {
      "term": "Termination",
      "details": "Either party may terminate with 30 days written notice"
    }
  ],
  "obligations": {
    "ABC Corp": [
      "Pay monthly service fee of $5,000",
      "Provide access to necessary systems"
    ],
    "XYZ Services LLC": [
      "Deliver monthly reports",
      "Maintain 99.9% uptime SLA"
    ]
  },
  "important_clauses": [
    "Confidentiality agreement",
    "Limitation of liability",
    "Dispute resolution through arbitration"
  ]
}
```

## 💰 Cost Analysis

### Per-Document Processing Costs

| Service | Cost per Document | Notes |
|---------|------------------|-------|
| AWS Textract | $0.0015 | 1 page average |
| Amazon Bedrock | $0.0001 | ~400 tokens |
| S3 Storage | $0.000023 | Per MB per month |
| **Total** | **~$0.0016** | Per LLM analysis |

### Profitability by Tier

| Tier | Monthly Price | Max LLM Analyses | AWS Cost | Margin |
|------|--------------|------------------|----------|--------|
| Free | $0 | 2 | $0.0032 | -100% (acquisition) |
| Pro | $10 | 50 | $0.08 | 99.2% |
| Enterprise | $99 | 500 | $0.80 | 99.2% |

## 🎨 User Interface

### Upload Interface
- Clean, modern design with drag-and-drop support
- Real-time quota display
- Analysis type selector (General, Invoice, Contract, Form)
- Enable/disable AI analysis toggle
- Tier comparison table

### Results Display
- Tabbed interface: "Text" and "Analysis" views
- Formatted JSON display with syntax highlighting
- Download buttons for CSV and JSON
- Analysis type badge
- Processing time display

### Document History
- Table view of all processed documents
- Sortable by date, filename, type
- Quick access to previous results
- Download links for CSV and JSON
- Pagination for large histories

## 🔧 Troubleshooting

### Common Issues

#### Bedrock Access Denied
**Error**: `AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel`

**Solutions**:
1. Verify IAM policy includes Bedrock permissions (see `.iampolicyaws.json`)
2. Check that model access is enabled in AWS Console → Bedrock → Model access
3. Ensure your AWS region supports Bedrock
4. Wait a few minutes after enabling model access for permissions to propagate

#### Bedrock Model Not Found
**Error**: `ValidationException: The provided model identifier is invalid`

**Solutions**:
1. Verify you're using the correct model ID: `anthropic.claude-3-haiku-20240307-v1:0`
2. Check that Claude 3 Haiku is available in your region
3. Ensure model access is granted in the Bedrock console

#### Region Not Supported
**Error**: `InvalidSignatureException` or connection timeouts

**Solutions**:
1. Change `AWS_REGION` to a Bedrock-supported region:
   - us-east-1 (N. Virginia) - Recommended
   - us-west-2 (Oregon)
   - ap-southeast-1 (Singapore)
   - eu-central-1 (Frankfurt)
2. Update your S3 bucket to the same region for optimal performance

#### LLM Analysis Not Working
**Symptoms**: Documents process but no JSON analysis appears

**Solutions**:
1. Check browser console for JavaScript errors
2. Verify "Enable AI Analysis" checkbox is selected during upload
3. Check that you haven't exceeded your LLM quota
4. Review Flask logs for Bedrock API errors
5. Ensure `api/llm_service.py` exists and is properly imported

#### Database Migration Issues
**Error**: `OperationalError: no such table: document_history`

**Solutions**:
1. Run database initialization: `flask --app api.index:create_app init-db`
2. If using Flask-Migrate: `flask db upgrade`
3. Check DATABASE_URL is correct and accessible

## 🧪 Testing

### Manual Testing Checklist

- [ ] Upload document with LLM analysis enabled
- [ ] Verify both CSV and JSON results generated
- [ ] Test each analysis type (general, invoice, contract, form)
- [ ] Verify quota enforcement for Free tier
- [ ] Test monthly quota reset
- [ ] Upload document exceeding page limit
- [ ] Test history page display
- [ ] View historical document results
- [ ] Test download links from history
- [ ] Test Enterprise API authentication
- [ ] Verify API rate limiting

### Sample Test Documents

Include test documents in `test_documents/` directory:
- `sample_letter.pdf` - General document
- `sample_invoice.pdf` - Invoice with line items
- `sample_contract.pdf` - Service agreement
- `sample_form.pdf` - Application form

## 🔒 Security Considerations

- **API Keys**: Cryptographically secure random generation
- **S3 Access**: Presigned URLs with 5-minute expiration
- **Authentication**: Google OAuth 2.0 with HTTPS required
- **Rate Limiting**: 100 requests/hour for API endpoints
- **Input Validation**: File type and size restrictions
- **SQL Injection**: SQLAlchemy ORM with parameterized queries
- **XSS Protection**: Jinja2 auto-escaping enabled

## 📈 Future Enhancements

- Multi-language OCR support
- Batch document processing
- Webhook notifications for async results
- Custom LLM prompts for Enterprise users
- Document comparison and diff analysis
- Integration with Slack, email, and business tools
- Advanced analytics dashboard
- Multi-model support (GPT-4, Gemini)

## 📄 License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 🙏 Acknowledgments

- **AWS**: For providing Textract, Bedrock, and S3 services
- **Anthropic**: For Claude 3 Haiku model
- **Vercel**: For seamless Python hosting
- **Flask Community**: For excellent web framework
- **Open Source Community**: For supporting libraries

## 📞 Support

For questions, issues, or feature requests:
- Open an issue on GitHub
- Email: support@example.com
- Documentation: https://docs.example.com

---

**Built for the AWS AI Agent Global Hackathon 2024**

Demonstrating autonomous AI agents that combine multiple AWS services to deliver intelligent document processing without human intervention.
