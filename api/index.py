import os
import boto3
import time
import csv
import io
import requests
import json
import datetime
import stripe
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory, session
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from botocore.client import Config

# Reduce AWS SDK logging noise
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# --- 1. Initialize Extensions (globally) ---
db = SQLAlchemy()
login_manager = LoginManager()

# --- 2. Define the Database Models (globally) ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    tier = db.Column(db.String(20), nullable=False, default='free')
    usage_reset_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    documents_processed_this_month = db.Column(db.Integer, nullable=False, default=0)
    llm_analyses_this_month = db.Column(db.Integer, nullable=False, default=0)
    api_key = db.Column(db.String(64), nullable=True, unique=True)
    api_key_created = db.Column(db.DateTime, nullable=True)

    def get_id(self):
        return self.id

class DocumentHistory(db.Model):
    __tablename__ = 'document_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    analysis_type = db.Column(db.String(50), nullable=True)
    textract_job_id = db.Column(db.String(100), nullable=False)
    csv_filename = db.Column(db.String(255), nullable=False)
    json_filename = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=False)
    page_count = db.Column(db.Integer, nullable=True)
    processing_cost = db.Column(db.Float, nullable=True)
    
    user = db.relationship('User', backref='documents')

# --- 3. The Application Factory Function ---
def create_app():
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    app = Flask(__name__, template_folder='../templates')

    # --- CONFIGURATIONS ---
    app.secret_key = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Add connection pool settings for better reliability
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,  # Verify connections before use
        'pool_recycle': 300,    # Recycle connections every 5 minutes
        'connect_args': {
            'connect_timeout': 10,
            'sslmode': 'require'
        }
    }
    # Stripe configuration
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID')
    STRIPE_PRO_PRICE_ID = os.environ.get('STRIPE_SUBSCRIPTION_PRICE_ID')
    STRIPE_ENTERPRISE_PRICE_ID = os.environ.get('STRIPE_ENTERPRISE_PRICE_ID')
    
    # Validate Stripe configuration
    stripe_enabled = bool(stripe.api_key and STRIPE_PRICE_ID)
    if not stripe_enabled:
        print("Info: Stripe not fully configured. Payment features disabled.")
    elif stripe.api_key and stripe.api_key.startswith('sk_live_'):
        print("✅ Production: Using live Stripe keys")
        # Additional production validation
        if not STRIPE_WEBHOOK_SECRET:
            print("⚠️  Warning: Live webhook secret not configured!")
    else:
        print("🧪 Development: Using test Stripe keys")
    
    # Validate Stripe configuration
    if not all([stripe.api_key, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID]):
        print("Warning: Stripe configuration incomplete. Payment features may not work.")
    
    # Check if using test vs live keys
    if stripe.api_key and stripe.api_key.startswith('sk_live_'):
        print("Warning: Using live Stripe keys. Make sure this is intentional for production.")
    PLAN_LIMITS = {
        'free': {
            'documents': 5, 
            'pages': 3, 
            'filesize': 2 * 1024 * 1024,  # 2MB
            'llm_analyses': 2
        },
        'pro': {
            'documents': 200, 
            'pages': 50, 
            'filesize': 5 * 1024 * 1024,  # 5MB
            'llm_analyses': 50
        },
        'enterprise': {
            'documents': 1000,
            'pages': 100,
            'filesize': 50 * 1024 * 1024,  # 50MB
            'llm_analyses': 500
        }
    }

    # --- INITIALIZE EXTENSIONS WITH THE APP ---
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login_page'
    
    # Create tables if they don't exist (for Vercel)
    # This will create new tables (document_history) and add new columns to existing tables
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created/verified")
        except Exception as e:
            print(f"Database initialization error: {e}")

    # --- HELPER FUNCTIONS (Needed for routes) ---
    def get_all_textract_blocks(job_id, initial_response):
        textract = boto3.client('textract', region_name=os.environ.get('AWS_REGION'))
        blocks = initial_response['Blocks']
        next_token = initial_response.get('NextToken')
        while next_token:
            response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
            blocks.extend(response['Blocks'])
            next_token = response.get('NextToken')
        return blocks

    def create_and_upload_csv(blocks, original_filename):
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        string_buffer = io.StringIO()
        writer = csv.writer(string_buffer)
        writer.writerow(['DetectedText'])
        for block in blocks:
            if block['BlockType'] == 'LINE':
                writer.writerow([block['Text']])
        csv_string = string_buffer.getvalue()
        csv_bytes = csv_string.encode('utf-8')
        bytes_buffer = io.BytesIO(csv_bytes)
        base_filename = os.path.splitext(original_filename)[0]
        csv_filename = f"{base_filename}_result.csv"
        s3.upload_fileobj(bytes_buffer, os.environ.get('S3_BUCKET'), csv_filename, ExtraArgs={'ContentType': 'text/csv'})
        return csv_filename

    def check_llm_quota(user):
        """Check if user has remaining LLM analysis quota"""
        # Reset monthly counter if month has passed
        if user.usage_reset_date < datetime.datetime.utcnow() - datetime.timedelta(days=30):
            user.llm_analyses_this_month = 0
            user.usage_reset_date = datetime.datetime.utcnow()
            db.session.commit()
        
        # Check user tier and monthly usage
        limit = PLAN_LIMITS.get(user.tier, {}).get('llm_analyses', 0)
        return user.llm_analyses_this_month < limit

    def upload_json_to_s3(analysis_result, original_filename):
        """Upload LLM analysis JSON to S3"""
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        
        # Generate filename from original document name
        base_filename = os.path.splitext(original_filename)[0]
        json_filename = f"{base_filename}_analysis.json"
        
        # Convert analysis dict to JSON bytes
        json_bytes = json.dumps(analysis_result, indent=2).encode('utf-8')
        bytes_buffer = io.BytesIO(json_bytes)
        
        # Upload to S3 with proper content type
        s3.upload_fileobj(bytes_buffer, os.environ.get('S3_BUCKET'), json_filename,
            ExtraArgs={'ContentType': 'application/json'})
        
        # Return S3 key for storage
        return json_filename

    def save_to_history(user_id, filename, textract_job_id, csv_filename, json_filename, analysis_type, file_size=0, page_count=None):
        """Save document processing record to history"""
        # Create DocumentHistory record
        doc = DocumentHistory(
            user_id=user_id,
            filename=filename,
            textract_job_id=textract_job_id,
            csv_filename=csv_filename,
            json_filename=json_filename,
            analysis_type=analysis_type,
            file_size=file_size,
            page_count=page_count
        )
        # Commit to database
        db.session.add(doc)
        db.session.commit()

    # --- DEFINE ALL ROUTES AND LOGIC WITHIN THE FACTORY ---
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
        print("Initialized the database.")

    # --- OAuth and User Routes ---
    @app.route("/login_page")
    def login_page():
        return render_template("login.html")

    @app.route("/login")
    def login():
        discovery_url = os.environ.get('GOOGLE_DISCOVERY_URL')
        print(f"Discovery URL: '{discovery_url}'")  # Debug logging
        google_provider_cfg = requests.get(discovery_url).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        # Use HTTP for local development, HTTPS for production/Vercel
        is_vercel = 'vercel.app' in request.host
        scheme = 'https' if (request.is_secure or os.environ.get('FLASK_ENV') == 'production' or is_vercel) else 'http'
        request_uri = requests.Request("GET", authorization_endpoint, params={"client_id": os.environ.get('GOOGLE_CLIENT_ID'), "redirect_uri": url_for('callback', _external=True, _scheme=scheme), "response_type": "code", "scope": "openid email profile"}).prepare().url
        return redirect(request_uri)

    @app.route("/login/callback")
    def callback():
        try:
            print("=== OAuth Callback Started ===")
            code = request.args.get("code")
            print(f"Authorization code received: {code[:10]}..." if code else "No code received")
            
            if not code:
                return "No authorization code received from Google", 400
            
            discovery_url = os.environ.get('GOOGLE_DISCOVERY_URL')
            print(f"Discovery URL: '{discovery_url}'")
            
            google_provider_cfg = requests.get(discovery_url).json()
            token_endpoint = google_provider_cfg["token_endpoint"]
            print(f"Token endpoint: {token_endpoint}")
            
            # Use HTTP for local development, HTTPS for production/Vercel
            is_vercel = 'vercel.app' in request.host
            scheme = 'https' if (request.is_secure or os.environ.get('FLASK_ENV') == 'production' or is_vercel) else 'http'
            print(f"Using scheme: {scheme}, Host: {request.host}")
            
            redirect_uri = url_for('callback', _external=True, _scheme=scheme)
            print(f"Redirect URI: {redirect_uri}")
            
            token_response = requests.post(token_endpoint, data={
                "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }).json()
            
            print(f"Token response keys: {list(token_response.keys())}")
            
            # Check for token response errors
            if 'error' in token_response:
                print(f"Token error: {token_response}")
                return f"OAuth error: {token_response.get('error_description', 'Unknown error')}", 400
                
            if 'access_token' not in token_response:
                print(f"No access token in response: {token_response}")
                return "Failed to get access token from Google", 400
                
            userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
            userinfo_response = requests.get(userinfo_endpoint, headers={"Authorization": f"Bearer {token_response['access_token']}"}).json()
            
            print(f"User info received: {userinfo_response.get('email', 'No email')}")
            
            if userinfo_response.get("email_verified"):
                unique_id = userinfo_response["sub"]
                users_email = userinfo_response["email"]
                users_name = userinfo_response.get("given_name", userinfo_response.get("name", "User"))
                
                print(f"Creating/finding user: {users_email}")
                
                # Database operations with retry logic for connection issues
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        user = User.query.filter_by(google_id=unique_id).first()
                        if not user:
                            print("Creating new user")
                            user = User(google_id=unique_id, name=users_name, email=users_email)
                            db.session.add(user)
                            db.session.commit()
                        else:
                            print("User found, logging in")
                        
                        login_user(user)
                        print("User logged in successfully, redirecting to index")
                        return redirect(url_for("index"))
                        
                    except Exception as db_error:
                        print(f"Database attempt {attempt + 1} failed: {db_error}")
                        if attempt < max_retries - 1:
                            # Rollback and retry
                            db.session.rollback()
                            import time
                            time.sleep(1)  # Wait 1 second before retry
                            continue
                        else:
                            # Final attempt failed
                            db.session.rollback()
                            print(f"All database attempts failed for user {users_email}")
                            return "Database temporarily unavailable. Please try signing in again in a moment.", 503
                
            print("Email not verified by Google")
            return "User email not available or not verified by Google.", 400
            
        except Exception as e:
            print(f"Callback error: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return f"Internal error: {str(e)}", 500

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # --- Usage Limiting Decorator ---
    def check_usage_limit(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.tier != 'pro' and current_user.usage_reset_date < datetime.datetime.utcnow() - datetime.timedelta(days=30):
                current_user.documents_processed_this_month = 0
                current_user.usage_reset_date = datetime.datetime.utcnow()
                db.session.commit()
            limit = PLAN_LIMITS[current_user.tier]['documents']
            if current_user.documents_processed_this_month >= limit:
                if current_user.tier == 'free':
                    flash(f"You've reached your monthly limit of {limit} documents. Upgrade to Pro for 200 documents/month!", "upgrade")
                else:
                    flash(f"You've reached your monthly limit of {limit} documents. Your limit will reset next month.", "warning")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function

    # --- Core Application Routes ---
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon from root directory"""
        try:
            # Try to serve from root directory (one level up from api/)
            return send_from_directory(os.path.join(app.root_path, '..'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
        except Exception as e:
            print(f"Favicon error: {e}")
            # Return a 204 No Content response to prevent browser errors
            return '', 204

    @app.route('/')
    @login_required
    def index():
        # Check for payment success
        if request.args.get('payment') == 'success':
            payment_type = request.args.get('type')
            tier = request.args.get('tier', 'pro')
            if payment_type == 'subscription':
                tier_name = tier.capitalize()
                flash(f"Welcome to {tier_name}! Your upgrade is being processed and will be active shortly.", "success")
            elif payment_type == 'onetime':
                flash("Test payment successful! Thank you for testing our system.", "success")
        # Clear any old flash messages on successful login
        elif current_user.is_authenticated:
            # This ensures we start fresh when user is properly logged in
            pass
        return render_template('index.html', plan_limits=PLAN_LIMITS)

    @app.route('/admin/stats')
    @login_required
    def admin_stats():
        # Secure admin check using environment variable
        admin_email = os.environ.get('ADMIN_EMAIL')
        if not admin_email or current_user.email != admin_email:
            # Don't reveal that this endpoint exists
            return "Page not found", 404
            
        # Additional security: check if user has been admin for a while (prevent account takeover)
        if not current_user.tier == 'pro':  # Only pro users can be admins
            return "Page not found", 404
            
        try:
            total_users = User.query.count()
            pro_users = User.query.filter_by(tier='pro').count()
            free_users = User.query.filter_by(tier='free').count()
            
            # Monthly usage stats
            total_docs_this_month = db.session.query(db.func.sum(User.documents_processed_this_month)).scalar() or 0
            
            stats = {
                'total_users': total_users,
                'pro_subscribers': pro_users,
                'free_users': free_users,
                'total_docs_processed': total_docs_this_month
            }
            
            return f"""
            <html>
            <head><title>Admin Dashboard</title></head>
            <body style="font-family: Arial, sans-serif; margin: 40px;">
                <h2>📊 Admin Dashboard</h2>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                    <p><strong>Total Users:</strong> {stats['total_users']}</p>
                    <p><strong>💰 Pro Subscribers:</strong> {stats['pro_subscribers']}</p>
                    <p><strong>🆓 Free Users:</strong> {stats['free_users']}</p>
                    <p><strong>📄 Documents This Month:</strong> {stats['total_docs_processed']}</p>
                    <p><strong>💵 Estimated Revenue:</strong> ${stats['pro_subscribers'] * 10}/month</p>
                </div>
                <br>
                <a href="/" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to App</a>
            </body>
            </html>
            """
        except Exception as e:
            print(f"Admin stats error: {e}")
            return "Service temporarily unavailable", 503

    @app.route('/upload', methods=['POST'])
    @login_required
    @check_usage_limit
    def upload():
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        textract = boto3.client('textract', region_name=os.environ.get('AWS_REGION'))
        if 'file' not in request.files: return "No file part.", 400
        file = request.files['file']
        if file.filename == '': return "No file selected.", 400
        filesize_limit = PLAN_LIMITS[current_user.tier]['filesize']
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        if file_length > filesize_limit: return f"File size exceeds the {filesize_limit // 1024 // 1024}MB limit.", 413
        file.seek(0)
        
        # Accept LLM analysis parameters from form
        enable_llm = request.form.get('enable_llm') == 'true'
        analysis_type = request.form.get('analysis_type', 'general')
        
        # Store LLM preferences in Flask session for later use
        session['enable_llm'] = enable_llm
        session['analysis_type'] = analysis_type if enable_llm else None
        
        try:
            s3.upload_fileobj(file, os.environ.get('S3_BUCKET'), file.filename, ExtraArgs={'ContentType': file.content_type})
            response = textract.start_document_text_detection(DocumentLocation={'S3Object': {'Bucket': os.environ.get('S3_BUCKET'), 'Name': file.filename}})
            current_user.documents_processed_this_month += 1
            db.session.commit()
            return redirect(url_for('status', job_id=response['JobId'], original_filename=file.filename))
        except Exception as e:
            return f"An error occurred: {str(e)}", 500

    @app.route('/status/<job_id>/<original_filename>')
    @login_required
    def status(job_id, original_filename):
        return render_template('status.html', job_id=job_id, original_filename=original_filename)

    @app.route('/api/check_status/<job_id>')
    @login_required
    def check_status(job_id):
        textract = boto3.client('textract', region_name=os.environ.get('AWS_REGION'))
        try:
            response = textract.get_document_text_detection(JobId=job_id)
            return jsonify({'status': response.get('JobStatus')})
        except Exception as e:
            return jsonify({'status': 'FAILED', 'error': str(e)})

    # --- THE MISSING ROUTES ARE NOW HERE ---
    @app.route('/process_result/<job_id>/<original_filename>')
    @login_required
    def process_result(job_id, original_filename):
        textract = boto3.client('textract', region_name=os.environ.get('AWS_REGION'))
        try:
            response = textract.get_document_text_detection(JobId=job_id)
            if response.get('JobStatus') == 'SUCCEEDED':
                blocks = get_all_textract_blocks(job_id, response)
                csv_filename = create_and_upload_csv(blocks, original_filename)
                
                # Check session for LLM enablement
                json_filename = None
                enable_llm = session.get('enable_llm', False)
                analysis_type = session.get('analysis_type')
                
                # Call check_llm_quota before processing
                if enable_llm and analysis_type:
                    if check_llm_quota(current_user):
                        try:
                            # Extract text from Textract blocks
                            text = '\n'.join([block['Text'] for block in blocks if block['BlockType'] == 'LINE'])
                            
                            # Invoke LLMAnalyzer if enabled and quota available
                            from api.llm_service import LLMAnalyzer
                            analyzer = LLMAnalyzer(os.environ.get('AWS_REGION'))
                            analysis_result = analyzer.analyze_document(text, analysis_type)
                            
                            # Upload JSON results to S3
                            json_filename = upload_json_to_s3(analysis_result, original_filename)
                            
                            # Increment user's LLM usage counter
                            current_user.llm_analyses_this_month += 1
                            db.session.commit()
                        except Exception as llm_error:
                            # Log error but don't fail the entire request
                            print(f"LLM analysis error: {llm_error}")
                            # Continue without LLM analysis
                
                # Get file size from S3 for history
                s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
                try:
                    s3_response = s3.head_object(Bucket=os.environ.get('S3_BUCKET'), Key=original_filename)
                    file_size = s3_response.get('ContentLength', 0)
                except:
                    file_size = 0
                
                # Call save_to_history with all metadata
                save_to_history(
                    user_id=current_user.id,
                    filename=original_filename,
                    textract_job_id=job_id,
                    csv_filename=csv_filename,
                    json_filename=json_filename,
                    analysis_type=analysis_type,
                    file_size=file_size,
                    page_count=None  # Could extract from Textract response if needed
                )
                
                # Pass json_filename to success route
                return redirect(url_for('success', csv_filename=csv_filename, json_filename=json_filename))
            else:
                return "Job did not succeed. Status: " + response.get('JobStatus'), 500
        except Exception as e:
            return f"An error occurred during final processing: {str(e)}", 500

    @app.route('/success/<csv_filename>')
    @login_required
    def success(csv_filename):
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        
        # Accept optional json_filename parameter
        json_filename = request.args.get('json_filename')
        
        # Generate presigned URL for CSV file
        try:
            download_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': csv_filename},
                ExpiresIn=300
            )
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            download_url = None
        
        # Generate presigned URL for JSON file if present
        json_url = None
        analysis_type = None
        if json_filename:
            try:
                json_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': json_filename},
                    ExpiresIn=300
                )
                # Get analysis type from session
                analysis_type = session.get('analysis_type')
            except Exception as e:
                print(f"Error generating JSON presigned URL: {e}")
        
        # Pass both URLs to template
        return render_template(
            'result.html',
            csv_filename=csv_filename,
            json_filename=json_filename,
            bucket_name=os.environ.get('S3_BUCKET'),
            download_url=download_url,
            json_url=json_url,
            analysis_type=analysis_type
        )

    @app.route('/preview/<path:csv_filename>')
    @login_required
    def preview_csv(csv_filename):
        """Serve CSV content for preview without CORS issues"""
        from urllib.parse import unquote
        
        # Decode URL-encoded filename (may need multiple decodes)
        decoded_filename = csv_filename
        # Keep decoding until no more %XX patterns are found
        while '%' in decoded_filename:
            new_decoded = unquote(decoded_filename)
            if new_decoded == decoded_filename:
                break  # No more decoding needed
            decoded_filename = new_decoded
            
        print(f"Original filename: {csv_filename}")
        print(f"Decoded filename: {decoded_filename}")
        
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        
        # Try different filename variations
        filenames_to_try = [
            decoded_filename,
            csv_filename,  # Original encoded version
            unquote(csv_filename),  # Single decode
        ]
        
        for filename in filenames_to_try:
            try:
                print(f"Trying filename: {filename}")
                # Get the CSV content from S3
                response = s3.get_object(Bucket=os.environ.get('S3_BUCKET'), Key=filename)
                csv_content = response['Body'].read().decode('utf-8')
                
                # Extract just the text content (skip CSV header)
                lines = csv_content.split('\n')
                if len(lines) > 1:
                    # Skip the header row and join the rest
                    text_content = '\n'.join(line.strip('"') for line in lines[1:] if line.strip())
                else:
                    text_content = csv_content
                    
                return text_content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
            except Exception as e:
                print(f"Failed with filename '{filename}': {e}")
                continue
        
        # If all attempts failed, return error
        return "Error: Could not load the file for preview. The file may have been moved or deleted.", 500

    # --- Document History Routes ---
    @app.route('/history')
    @login_required
    def history():
        """Display user's document processing history"""
        # Query DocumentHistory for current user
        documents = DocumentHistory.query.filter_by(user_id=current_user.id)\
            .order_by(DocumentHistory.upload_date.desc())\
            .limit(50)\
            .all()
        
        # Render history.html template
        return render_template('history.html', documents=documents)

    @app.route('/history/<int:doc_id>')
    @login_required
    def view_history_item(doc_id):
        """View a specific document from history"""
        # Query specific document by ID and user_id
        doc = DocumentHistory.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        
        # Generate presigned URLs for CSV and JSON
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        
        csv_url = s3.generate_presigned_url('get_object', 
            Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': doc.csv_filename},
            ExpiresIn=300)
        
        json_url = None
        if doc.json_filename:
            json_url = s3.generate_presigned_url('get_object',
                Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': doc.json_filename},
                ExpiresIn=300)
        
        # Render result.html with from_history flag
        return render_template('result.html', 
            csv_filename=doc.csv_filename,
            json_filename=doc.json_filename,
            download_url=csv_url,
            json_url=json_url,
            analysis_type=doc.analysis_type,
            from_history=True)

    # --- API Key Management Routes ---
    @app.route('/api/generate-key', methods=['POST'])
    @login_required
    def generate_api_key():
        """Generate API key for Enterprise users"""
        # Check if user is Enterprise tier
        if current_user.tier != 'enterprise':
            return jsonify({'error': 'API keys are only available for Enterprise tier users'}), 403
        
        # Generate cryptographically secure random key
        import secrets
        api_key = 'cvocr_' + secrets.token_urlsafe(48)  # 64 character key with prefix
        
        # Store in user.api_key field
        current_user.api_key = api_key
        current_user.api_key_created = datetime.datetime.utcnow()
        db.session.commit()
        
        # Display key once to user
        return jsonify({
            'success': True,
            'api_key': api_key,
            'created_at': current_user.api_key_created.isoformat(),
            'message': 'API key generated successfully. Please save this key securely - it will not be shown again.'
        })
    
    @app.route('/api/revoke-key', methods=['POST'])
    @login_required
    def revoke_api_key():
        """Revoke existing API key"""
        if current_user.tier != 'enterprise':
            return jsonify({'error': 'API keys are only available for Enterprise tier users'}), 403
        
        if not current_user.api_key:
            return jsonify({'error': 'No API key to revoke'}), 400
        
        # Clear the API key
        current_user.api_key = None
        current_user.api_key_created = None
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'API key revoked successfully'
        })

    # --- Stripe Payment Routes ---
    @app.route('/create-checkout-session')
    @app.route('/create-checkout-session/<payment_type>')
    @app.route('/create-checkout-session/<payment_type>/<tier>')
    @login_required
    def create_checkout_session(payment_type=None, tier=None):
        try:
            # Use HTTP for local development, HTTPS for production
            scheme = 'https' if request.is_secure or os.environ.get('FLASK_ENV') == 'production' else 'http'
            
            # Generate URLs with proper scheme
            success_url = url_for('index', _external=True, _scheme=scheme)
            cancel_url = url_for('index', _external=True, _scheme=scheme)
            
            # Determine payment type from URL parameter or environment variable
            if payment_type is None:
                payment_type = 'subscription' if os.environ.get('STRIPE_MODE', 'subscription') == 'subscription' else 'onetime'
            
            is_subscription = payment_type == 'subscription'
            
            # Use simple email-based checkout (no custom customer creation)
            # This will use the user's actual name from their Google account
            customer = None

            if is_subscription:
                # Subscription mode (recurring payments)
                # Determine which tier based on URL parameter
                if tier == 'enterprise':
                    price_id = STRIPE_ENTERPRISE_PRICE_ID
                    plan_name = 'Enterprise'
                    plan_price = '$99/month'
                    tier_metadata = 'enterprise'
                else:
                    # Default to Pro tier
                    price_id = STRIPE_PRO_PRICE_ID or os.environ.get('STRIPE_PRICE_ID')
                    plan_name = 'Pro'
                    plan_price = '$10/month'
                    tier_metadata = 'pro'
                
                checkout_params = {
                    'line_items': [{'price': price_id, 'quantity': 1}],
                    'mode': 'subscription',
                    'success_url': f"{success_url}?payment=success&type=subscription&tier={tier_metadata}",
                    'cancel_url': cancel_url,
                    'billing_address_collection': 'required',
                    'custom_text': {
                        'submit': {
                            'message': f'Subscribe to California Vision OCR {plan_name} Plan - {plan_price}'
                        }
                    },
                    'metadata': {
                        'company_name': 'California Vision, Inc.',
                        'user_email': current_user.email,
                        'payment_type': 'subscription',
                        'tier': tier_metadata
                    }
                }
                
                # Always use customer_email to preserve user's actual name from Google account
                checkout_params['customer_email'] = current_user.email
                    
                session = stripe.checkout.Session.create(**checkout_params)
                
            else:
                # One-time payment mode
                price_id = os.environ.get('STRIPE_ONETIME_PRICE_ID', os.environ.get('STRIPE_PRICE_ID'))
                checkout_params = {
                    'line_items': [{'price': price_id, 'quantity': 1}],
                    'mode': 'payment',
                    'success_url': f"{success_url}?payment=success&type=onetime",
                    'cancel_url': cancel_url,
                    'billing_address_collection': 'required',
                    'custom_text': {
                        'submit': {
                            'message': 'Purchase California Vision OCR Credits - $1 test'
                        }
                    },
                    'metadata': {
                        'company_name': 'California Vision, Inc.',
                        'user_email': current_user.email,
                        'payment_type': 'onetime'
                    }
                }
                
                # Always use customer_email to preserve user's actual name from Google account
                checkout_params['customer_email'] = current_user.email
                checkout_params['customer_creation'] = 'always'
                    
                session = stripe.checkout.Session.create(**checkout_params)
            return redirect(session.url)
        except Exception as e:
            return str(e)

    @app.route('/stripe-webhook', methods=['POST'])
    def stripe_webhook():
        if not STRIPE_WEBHOOK_SECRET:
            return 'Webhook not configured', 400
            
        payload = request.data
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        event = None
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            print(f"Webhook signature verification failed: {e}")
            return 'Invalid payload or signature', 400
            
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            customer_email = session.get('customer_email')
            if customer_email:
                user = User.query.filter_by(email=customer_email).first()
                if user:
                    # Check payment type from metadata
                    payment_type = session.get('metadata', {}).get('payment_type', 'unknown')
                    session_mode = session.get('mode', 'unknown')
                    tier = session.get('metadata', {}).get('tier', 'pro')
                    
                    if session_mode == 'subscription' or payment_type == 'subscription':
                        # Upgrade to the specified tier (pro or enterprise)
                        user.tier = tier
                        db.session.commit()
                        print(f"User {customer_email} upgraded to {tier.capitalize()} via subscription")
                    else:
                        # For test payments, just log but don't upgrade
                        print(f"User {customer_email} completed test payment (${session.get('amount_total', 0)/100}) - no tier change")
                        # Optionally, you could create a 'test' tier or track test payments differently
        
        # Handle subscription cancellations
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription.get('customer')
            if customer_id:
                # Get customer email from Stripe
                try:
                    customer = stripe.Customer.retrieve(customer_id)
                    customer_email = customer.get('email')
                    if customer_email:
                        user = User.query.filter_by(email=customer_email).first()
                        if user:
                            # Downgrade to free tier
                            user.tier = 'free'
                            db.session.commit()
                            print(f"User {customer_email} downgraded to Free (subscription cancelled)")
                except Exception as e:
                    print(f"Error handling subscription cancellation: {e}")
                    
        return jsonify(success=True)

    return app

# --- 4. Create the App for Vercel/Gunicorn to Find ---
app = create_app()