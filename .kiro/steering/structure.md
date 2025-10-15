# Project Structure

## Directory Organization

```
/
├── api/                    # Flask application module
│   ├── index.py           # Main application factory and routes
│   └── __pycache__/       # Python bytecode cache
├── templates/             # Jinja2 HTML templates
│   ├── index.html         # Main upload interface
│   ├── login.html         # Google OAuth login page
│   ├── result.html        # Processing results and download
│   ├── status.html        # Real-time processing status
│   └── vercel.json        # Vercel configuration (misplaced)
├── venv/                  # Python virtual environment
├── __pycache__/           # Python bytecode cache
├── .env                   # Environment variables (local only)
├── .flaskenv              # Flask-specific environment config
├── .gitignore             # Git ignore rules
├── .iampolicyaws.json     # AWS IAM policy configuration
├── README.md              # Project documentation
└── requirements.txt       # Python dependencies
```

## Code Organization Patterns

### Application Factory Pattern
- Main app created via `create_app()` function in `api/index.py`
- Extensions initialized globally, then bound to app instance
- All routes and configurations defined within factory function

### Route Organization
- **Authentication**: `/login`, `/login/callback`, `/logout`
- **Core App**: `/` (upload), `/upload`, `/status/<job_id>/<filename>`
- **Processing**: `/process_result/<job_id>/<filename>`, `/success/<csv_filename>`
- **API**: `/api/check_status/<job_id>`
- **Payments**: `/create-checkout-session`, `/stripe-webhook`

### Template Structure
- Consistent styling with inline CSS
- Font Awesome icons for UI elements
- JavaScript for client-side interactions and AJAX polling
- Logout links positioned absolutely in top-right corner

### Database Models
- Single `User` model with SQLAlchemy ORM
- Usage tracking fields for freemium limits
- Google OAuth integration fields

## File Naming Conventions
- Snake_case for Python files and variables
- Kebab-case for HTML templates and CSS classes
- Environment files prefixed with dot (`.env`, `.flaskenv`)

## Security Considerations
- Sensitive files excluded via `.gitignore`
- Environment variables for all secrets
- HTTPS required for OAuth redirects
- Presigned URLs for secure S3 downloads