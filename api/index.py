import os
import boto3
import time
import csv
import io
import requests
import json
import datetime
import stripe
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from botocore.client import Config

# --- 1. Initialize Extensions (globally) ---
db = SQLAlchemy()
login_manager = LoginManager()

# --- 2. Define the Database Model (globally) ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    tier = db.Column(db.String(20), nullable=False, default='free')
    usage_reset_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    documents_processed_this_month = db.Column(db.Integer, nullable=False, default=0)

    def get_id(self):
        return self.id

# --- 3. The Application Factory Function ---
def create_app():
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    app = Flask(__name__, template_folder='../templates')

    # --- CONFIGURATIONS ---
    app.secret_key = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID')
    PLAN_LIMITS = {
        'free': {'documents': 5, 'pages': 3, 'filesize': 2 * 1024 * 1024},
        'pro': {'documents': 200, 'pages': 50, 'filesize': 20 * 1024 * 1024}
    }

    # --- INITIALIZE EXTENSIONS WITH THE APP ---
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login_page'

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
        google_provider_cfg = requests.get(os.environ.get('GOOGLE_DISCOVERY_URL')).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        request_uri = requests.Request("GET", authorization_endpoint, params={"client_id": os.environ.get('GOOGLE_CLIENT_ID'), "redirect_uri": url_for('callback', _external=True, _scheme='https'), "response_type": "code", "scope": "openid email profile"}).prepare().url
        return redirect(request_uri)

    @app.route("/login/callback")
    def callback():
        code = request.args.get("code")
        google_provider_cfg = requests.get(os.environ.get('GOOGLE_DISCOVERY_URL')).json()
        token_endpoint = google_provider_cfg["token_endpoint"]
        token_response = requests.post(token_endpoint, data={"client_id": os.environ.get('GOOGLE_CLIENT_ID'), "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'), "grant_type": "authorization_code", "code": code, "redirect_uri": url_for('callback', _external=True, _scheme='https')}).json()
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        userinfo_response = requests.get(userinfo_endpoint, headers={"Authorization": f"Bearer {token_response['access_token']}"}).json()
        if userinfo_response.get("email_verified"):
            unique_id = userinfo_response["sub"]
            users_email = userinfo_response["email"]
            users_name = userinfo_response["given_name"]
            user = User.query.filter_by(google_id=unique_id).first()
            if not user:
                user = User(google_id=unique_id, name=users_name, email=users_email)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for("index"))
        return "User email not available or not verified by Google.", 400

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
                flash(f"You've reached your monthly limit of {limit} documents. Please upgrade to Pro to continue.", "warning")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function

    # --- Core Application Routes ---
    @app.route('/')
    @login_required
    def index():
        return render_template('index.html', plan_limits=PLAN_LIMITS)

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
                return redirect(url_for('success', csv_filename=csv_filename))
            else:
                return "Job did not succeed. Status: " + response.get('JobStatus'), 500
        except Exception as e:
            return f"An error occurred during final processing: {str(e)}", 500

    @app.route('/success/<csv_filename>')
    @login_required
    def success(csv_filename):
        s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION'), config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        try:
            download_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': os.environ.get('S3_BUCKET'), 'Key': csv_filename},
                ExpiresIn=300
            )
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            download_url = None
        return render_template(
            'result.html',
            csv_filename=csv_filename,
            bucket_name=os.environ.get('S3_BUCKET'),
            download_url=download_url
        )

    # --- Stripe Payment Routes ---
    @app.route('/create-checkout-session')
    @login_required
    def create_checkout_session():
        try:
            session = stripe.checkout.Session.create(
                customer_email=current_user.email,
                line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
                mode='subscription',
                success_url=url_for('index', _external=True, _scheme='https') + '?payment=success',
                cancel_url=url_for('index', _external=True, _scheme='https'),
            )
            return redirect(session.url, code=303)
        except Exception as e:
            return str(e)

    @app.route('/stripe-webhook', methods=['POST'])
    def stripe_webhook():
        payload = request.data
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        event = None
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            return 'Invalid payload or signature', 400
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            customer_email = session.get('customer_email')
            if customer_email:
                user = User.query.filter_by(email=customer_email).first()
                if user:
                    user.tier = 'pro'
                    db.session.commit()
        return jsonify(success=True)

    return app

# --- 4. Create the App for Vercel/Gunicorn to Find ---
app = create_app()