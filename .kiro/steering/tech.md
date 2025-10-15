# Technology Stack

## Backend Framework
- **Flask**: Python web framework with application factory pattern
- **Flask-Login**: User session management
- **Flask-SQLAlchemy**: Database ORM with PostgreSQL
- **python-dotenv**: Environment variable management

## Cloud Services
- **AWS Textract**: OCR document processing service
- **AWS S3**: File storage with presigned URLs for secure downloads
- **PostgreSQL (Neon)**: Database hosting
- **Vercel**: Application hosting and deployment

## Authentication & Payments
- **Google OAuth 2.0**: User authentication via Google accounts
- **Stripe**: Subscription payment processing

## Frontend
- **Jinja2 Templates**: Server-side rendering
- **Font Awesome**: Icons and UI elements
- **Vanilla JavaScript**: Client-side interactions and AJAX

## Development Environment

### Local Setup Commands
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
flask --app api.index:create_app init-db

# Run development server
flask --app api.index:create_app run --debug
```

### Environment Configuration
- Use `.env` file for local development (never commit to git)
- Configure environment variables in Vercel dashboard for production
- Required variables: AWS credentials, Google OAuth, Stripe keys, database URL

### Deployment
- **Vercel CLI**: `vercel` command for deployment
- **Entry Point**: `api/index.py` with `create_app()` factory function
- **Build**: No build step required, direct Python deployment