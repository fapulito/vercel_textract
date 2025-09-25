# Vercel - Python Client for AWS Textract
## OCR SaaS with Development Roadmap

### Setup and Deployment Instructions

1.  **AWS Setup:**
    *   Create an AWS account if you don't have one.
    *   Create an S3 bucket to store your uploaded files.
    *   Create an IAM user with programmatic access and attach the following policies:
        *   `AmazonS3FullAccess`
        *   `AmazonTextractFullAccess`
    *   Note down the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

2.  **Vercel Setup:**
    *   Create a Vercel account.
    *   Install the Vercel CLI: `npm install -g vercel`

3.  Of course. Here are the updated instructions and code to manage your environment variables using a `.env` file, which will be ignored by Git for security.

We will use the `python-dotenv` library to load the variables from a `.env` file into the application's environment.

### Updated Project Structure

The project structure will now include a `.env` file for your secrets and a `.gitignore` file to keep them out of your version control.

```
/
|-- app.py
|-- requirements.txt
|-- vercel.json
|-- .env
|-- .gitignore
|-- templates/
|   |-- index.html
|   |-- result.html
```

### File Modifications and Additions

Here are the updated and new files:

**1. `.env` (New File)**

Create this file in the root of your project. It will hold your secret keys and configuration. **Never commit this file to Git.**

```
AWS_ACCESS_KEY_ID="your_access_key_here"
AWS_SECRET_ACCESS_KEY="your_secret_key_here"
AWS_REGION="your_aws_region_here"
S3_BUCKET="your_s3_bucket_name_here"
```

**2. `.gitignore` (New File)**

Create this file to prevent Git from tracking sensitive files and unnecessary directories.

```
# Environment variables
.env

# Python virtual environment
venv/
__pycache__/
*.pyc

# Vercel deployment artifacts
.vercel/
```

**3. `requirements.txt` (Updated)**

We need to add `python-dotenv` to the list of dependencies.

```
Flask
boto3
python-dotenv
```

**4. `app.py` (Updated)**

The application code is updated to load the variables from the `.env` file at startup.

```python
import os
import boto3
from flask import Flask, render_template, request, redirect, url_for
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# AWS Configuration - loaded from environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION')
S3_BUCKET = os.environ.get('S3_BUCKET')

# Initialize AWS clients
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

textract = boto3.client(
    'textract',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        return redirect(request.url)

    if file:
        s3.upload_fileobj(
            file,
            S3_BUCKET,
            file.filename,
            ExtraArgs={'ContentType': file.content_type}
        )

        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': S3_BUCKET,
                    'Name': file.filename
                }
            }
        )

        job_id = response['JobId']
        return redirect(url_for('result', job_id=job_id))

@app.route('/result/<job_id>')
def result(job_id):
    response = textract.get_document_text_detection(JobId=job_id)

    while response['JobStatus'] == 'IN_PROGRESS':
        time.sleep(5)
        response = textract.get_document_text_detection(JobId=job_id)

    if response['JobStatus'] == 'SUCCEEDED':
        blocks = []
        pages = [response]

        while 'NextToken' in pages[-1]:
            pages.append(textract.get_document_text_detection(JobId=job_id, NextToken=pages[-1]['NextToken']))

        for page in pages:
            blocks.extend(page['Blocks'])

        extracted_text = ''
        for block in blocks:
            if block['BlockType'] == 'LINE':
                extracted_text += block['Text'] + '\n'
        return render_template('result.html', text=extracted_text)

    return "Error processing document."

if __name__ == '__main__':
    app.run()
```

### Updated Setup and Deployment Instructions

The deployment process remains largely the same, but the local development setup is now easier.

1.  **AWS Setup:** (No changes)
    *   Create an S3 bucket and an IAM user with `AmazonS3FullAccess` and `AmazonTextractFullAccess` policies.

2.  **Local Development (Updated):**
    *   Create your project directory with the files listed above.
    *   Create and populate the **`.env`** file with your actual AWS credentials and S3 bucket name.
    *   Create a virtual environment: `python -m venv venv`
    *   Activate it: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows).
    *   Install dependencies: `pip install -r requirements.txt`
    *   Run the app: `flask run`. The `load_dotenv()` function will automatically load the variables from your `.env` file.

3.  **Deploy to Vercel (Updated):**
    *   From your project directory, run `vercel`.
    *   The `.env` file will be ignored by Git and will not be uploaded to Vercel. You **must** still configure the environment variables in the Vercel project settings for the deployed application to work.
    *   In your Vercel project's dashboard, go to **Settings > Environment Variables** and add:
        *   `AWS_ACCESS_KEY_ID`
        *   `AWS_SECRET_ACCESS_KEY`
        *   `AWS_REGION`
        *   `S3_BUCKET`

Of course. Adding a lightweight OAuth layer is an excellent way to secure your app and start building a user base. We'll use **Google OAuth** for this, as it's universally trusted and simple to integrate.

This implementation will use `Flask-Login` for session management, which is a robust and standard way to handle user sessions in Flask.

### Summary of Changes

1.  **Google Cloud Project:** You'll create OAuth 2.0 credentials to get a Client ID and Secret.
2.  **Dependencies:** We'll add `Flask-Login` and `requests` to your `requirements.txt`.
3.  **Environment Variables:** You'll add your new Google credentials and a Flask `SECRET_KEY` to your `.env` file.
4.  **`app.py` Refactor:**
    *   Integrate `Flask-Login` to manage user sessions.
    *   Create a simple in-memory "user store" (a dictionary) to hold logged-in user data.
    *   Add new routes: `/login`, `/callback` (for Google's redirect), and `/logout`.
    *   Protect your existing application routes (`/`, `/upload`, etc.) so they require a login.
5.  **New Template:** A new `login.html` page will be created.
6.  **Template Updates:** Your existing templates will get a "Logout" button.

---

### Step 1: Get Google OAuth 2.0 Credentials

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project (or use an existing one).
3.  Navigate to **APIs & Services -> Credentials**.
4.  Click **+ CREATE CREDENTIALS** and choose **OAuth client ID**.
5.  If prompted, configure the **OAuth consent screen**.
    *   Choose **External** for User Type.
    *   Fill in the required fields (App name, User support email, Developer contact information).
    *   On the "Scopes" page, you don't need to add any scopes for now.
6.  Back on the Credentials screen, create the OAuth client ID:
    *   **Application type:** Web application.
    *   **Name:** Give it a name, like "Vercel Textract App".
    *   **Authorized redirect URIs:** This is critical. You must add both your local development URL and your future Vercel URL.
        *   `http://127.0.0.1:5000/callback`
        *   `https://YOUR_APP_NAME.vercel.app/callback` (Add this after you deploy)
7.  Click **Create**. A window will pop up with your **Client ID** and **Client Secret**. Copy these immediately.

---

### Step 2: Update Project Files

#### 1. `.env` (Updated)
Add your new Google credentials and a **new Flask Secret Key**. You can generate a good secret key by running `python -c 'import secrets; print(secrets.token_hex())'` in your terminal.

```

```

#### 2. `requirements.txt` (Updated)
```

```

#### 4. `templates/index.html` (Updated)
Add a logout button.

```html
<!-- Add this snippet somewhere convenient, like the top right or bottom -->
<div style="position: absolute; top: 20px; right: 20px;">
    <a href="/logout" style="text-decoration: none; color: #7f8c8d;">Logout</a>
</div>
```

*(You should add a similar logout link to `result.html` and `status.html` for a consistent experience.)*

#### 5. `app.py` (Fully Refactored)

```
**Important Note:** Google OAuth now requires HTTPS for all redirect URIs, even for `localhost`. The `ssl_context="adhoc"` argument in `app.run` creates a temporary, self-signed SSL certificate for local development. When you first run it and go to `https://127.0.0.1:5000`, your browser will give you a security warning. You must click "Advanced" and "Proceed to 127.0.0.1 (unsafe)" to continue. This is only necessary for local testing. Vercel will provide a valid SSL certificate for your production app automatically.