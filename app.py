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
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from botocore.client import Config

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# --- Database Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Stripe Configuration ---
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID')

# --- Plan Limits Definition ---
PLAN_LIMITS = {
    'free': {'documents': 5, 'pages': 3, 'filesize': 2 * 1024 * 1024}, # 2MB
    'pro': {'documents': 200, 'pages': 50, 'filesize': 20 * 1024 * 1024} # 20MB
}

# --- OAuth and Login Configuration ---
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# --- User Database Model ---
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- NEW: Custom Flask CLI Command to Create Database Tables ---
@app.cli.command("init-db")
def init_db_command():
    """Initializes the database by creating all tables."""
    with app.app_context():
        db.create_all()
    print("Initialized the database and created all tables.")

# --- AWS Configuration ---
S3_BUCKET = os.environ.get('S3_BUCKET')
AWS_REGION = os.environ.get('AWS_REGION')
s3_config = Config(signature_version='s3v4', s3={'addressing_style': 'path'})
s3 = boto3.client('s3', region_name=AWS_REGION, config=s3_config)
textract = boto3.client('textract', region_name=AWS_REGION)

# --- OAuth Routes ---
@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = requests.Request("GET", authorization_endpoint, params={"client_id": GOOGLE_CLIENT_ID, "redirect_uri": request.base_url + "/callback", "response_type": "code", "scope": "openid email profile"}).prepare().url
    return redirect(request_uri)

@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_response = requests.post(token_endpoint, data={"client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": request.base_url}).json()
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    userinfo_response = requests.get(userinfo_endpoint, headers={"Authorization": f"Bearer {token_response['access_token']}"}).json()

    if userinfo_response.get("email_verified"):
        unique_id = userinfo_response["sub"]
        users_email = userinfo_response["email"]
        users_name = userinfo_response["given_name"]

        # --- UPDATED: Database lookup and creation logic ---
        user = User.query.filter_by(google_id=unique_id).first()
        if not user:
            user = User(google_id=unique_id, name=users_name, email=users_email)
            db.session.add(user)
            db.session.commit()
            print(f"New user '{users_email}' added to the database.")
        else:
            print(f"Existing user '{users_email}' logged in.")
        
        login_user(user)
        return redirect(url_for("index"))

    return "User email not available or not verified by Google.", 400

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))

# --- NEW: Usage Limit Decorator ---
def check_usage_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.usage_reset_date < datetime.datetime.utcnow() - datetime.timedelta(days=30):
            current_user.documents_processed_this_month = 0
            current_user.usage_reset_date = datetime.datetime.utcnow()
            db.session.commit()
        
        limit = PLAN_LIMITS[current_user.tier]['documents']
        if current_user.documents_processed_this_month >= limit:
            # TODO: Redirect to an upgrade page with a flash message
            return "You have reached your monthly document limit.", 403
        return f(*args, **kwargs)
    return decorated_function

# --- Protected Application Routes ---
@app.route('/')
@login_required
def index():
    # NEW: Pass plan limits to the template so it can display usage info
    return render_template('index.html', plan_limits=PLAN_LIMITS)

@app.route('/upload', methods=['POST'])
@login_required
@check_usage_limit # <-- Apply the usage limit decorator
def upload():
    # ... (existing file checks) ...
    if 'file' not in request.files: return "No file part in the request.", 400
    file = request.files['file']
    if file.filename == '': return "No file selected.", 400

    # NEW: Check file size against plan limits
    filesize_limit = PLAN_LIMITS[current_user.tier]['filesize']
    if len(file.read()) > filesize_limit:
        file.seek(0) # Reset file pointer
        return f"File size exceeds the {filesize_limit // 1024 // 1024}MB limit for your plan.", 413
    file.seek(0)
    
    # NOTE: You would need a library like PyPDF2 to check page count before uploading.
    # This is a complex step, so we'll omit it for now but acknowledge it's needed.

    if file:
        try:
            s3.upload_fileobj(file, S3_BUCKET, file.filename, ExtraArgs={'ContentType': file.content_type})
            response = textract.start_document_text_detection(DocumentLocation={'S3Object': {'Bucket': S3_BUCKET, 'Name': file.filename}})
            
            # --- UPDATED: Increment usage counter after successful submission ---
            current_user.documents_processed_this_month += 1
            db.session.commit()

            return redirect(url_for('status', job_id=response['JobId'], original_filename=file.filename))
        except Exception as e:
            return f"An error occurred: {str(e)}", 500
    return redirect(url_for('index'))

# ... (other routes like /status, /api/check_status remain the same but are protected by @login_required) ...

# --- NEW: Stripe Payment Routes ---
@app.route('/create-checkout-session')
@login_required
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('index', _external=True) + '?payment=success',
            cancel_url=url_for('index', _external=True) + '?payment=cancelled',
        )
        return redirect(session.url, code=303)
    except Exception as e:
        return str(e)

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']
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
                print(f"User '{user.email}' upgraded to Pro tier.")

    return jsonify(success=True)

# --- Main Execution Block (Now Simplified) ---
if __name__ == '__main__':
    app.run(ssl_context="adhoc", debug=True)