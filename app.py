import os
import boto3
import time
import csv
import io
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from dotenv import load_dotenv
from botocore.client import Config

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# --- OAuth and Login Configuration ---
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

user_db = {}

class User(UserMixin):
    def __init__(self, id_, name, email):
        self.id = id_
        self.name = name
        self.email = email

    @staticmethod
    def get(user_id):
        return user_db.get(user_id)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

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
    
    request_uri = requests.Request(
        "GET", authorization_endpoint,
        params={
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": request.base_url + "/callback",
            "response_type": "code",
            "scope": "openid email profile",
        }
    ).prepare().url
    return redirect(request_uri)

# --- UPDATED CALLBACK FUNCTION ---
@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # FIX 1: Make the request and get the json directly.
    token_response = requests.post(
        token_endpoint,
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": request.base_url,
        }
    ).json()

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    
    # FIX 2: Make the userinfo request and get the json directly.
    userinfo_response = requests.get(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {token_response['access_token']}"}
    ).json()

    if userinfo_response.get("email_verified"):
        unique_id = userinfo_response["sub"]
        users_email = userinfo_response["email"]
        users_name = userinfo_response["given_name"]

        print(f"New login: Email='{users_email}', Name='{users_name}'")

        user = User(id_=unique_id, name=users_name, email=users_email)
        if not User.get(unique_id):
            user_db[unique_id] = user
        
        login_user(user)
        return redirect(url_for("index"))

    return "User email not available or not verified by Google.", 400

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))

# --- Protected Application Routes (No changes below) ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return "No file part in the request.", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected.", 400
    if file:
        try:
            s3.upload_fileobj(file, S3_BUCKET, file.filename, ExtraArgs={'ContentType': file.content_type})
            response = textract.start_document_text_detection(DocumentLocation={'S3Object': {'Bucket': S3_BUCKET, 'Name': file.filename}})
            return redirect(url_for('status', job_id=response['JobId'], original_filename=file.filename))
        except Exception as e:
            return f"An error occurred: {str(e)}", 500
    return redirect(url_for('index'))

@app.route('/status/<job_id>/<original_filename>')
@login_required
def status(job_id, original_filename):
    return render_template('status.html', job_id=job_id, original_filename=original_filename)

@app.route('/api/check_status/<job_id>')
@login_required
def check_status(job_id):
    try:
        response = textract.get_document_text_detection(JobId=job_id)
        status = response.get('JobStatus')
        return jsonify({'status': status})
    except Exception as e:
        return jsonify({'status': 'FAILED', 'error': str(e)})

@app.route('/process_result/<job_id>/<original_filename>')
@login_required
def process_result(job_id, original_filename):
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
    try:
        download_url = s3.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': csv_filename}, ExpiresIn=300)
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        download_url = None
    return render_template('result.html', csv_filename=csv_filename, bucket_name=S3_BUCKET, download_url=download_url)

def get_all_textract_blocks(job_id, initial_response):
    blocks = initial_response['Blocks']
    next_token = initial_response.get('NextToken')
    while next_token:
        response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        blocks.extend(response['Blocks'])
        next_token = response.get('NextToken')
    return blocks

def create_and_upload_csv(blocks, original_filename):
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
    s3.upload_fileobj(bytes_buffer, S3_BUCKET, csv_filename, ExtraArgs={'ContentType': 'text/csv'})
    return csv_filename

if __name__ == '__main__':
    app.run(ssl_context="adhoc", debug=True)