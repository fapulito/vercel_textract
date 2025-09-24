import os
import boto3
import time
import csv
import io
from flask import Flask, render_template, request, redirect, url_for
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
        # Pass the original filename to the result route
        return redirect(url_for('result', job_id=job_id, original_filename=file.filename))

@app.route('/result/<job_id>/<original_filename>')
def result(job_id, original_filename):
    response = textract.get_document_text_detection(JobId=job_id)

    while response['JobStatus'] == 'IN_PROGRESS':
        time.sleep(5)
        response = textract.get_document_text_detection(JobId=job_id)

    if response['JobStatus'] == 'SUCCEEDED':
        # Collect all blocks from all pages
        blocks = []
        pages = [response]
        while 'NextToken' in pages[-1]:
            pages.append(textract.get_document_text_detection(JobId=job_id, NextToken=pages[-1]['NextToken']))
        for page in pages:
            blocks.extend(page['Blocks'])

        # --- CSV Generation Logic ---
        # Create a file-like object in memory
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)

        # Write header
        writer.writerow(['DetectedText'])

        # Filter for LINE blocks and write the text to the CSV
        for block in blocks:
            if block['BlockType'] == 'LINE':
                writer.writerow([block['Text']])
        
        # --- S3 Upload Logic ---
        # Determine the output CSV filename
        base_filename = os.path.splitext(original_filename)[0]
        csv_filename = f"{base_filename}_result.csv"

        # Rewind the buffer to the beginning
        csv_buffer.seek(0)
        
        # Upload the in-memory CSV file to S3
        s3.upload_fileobj(
            csv_buffer,
            S3_BUCKET,
            csv_filename,
            ExtraArgs={'ContentType': 'text/csv'}
        )
        
        return render_template('result.html', csv_filename=csv_filename, bucket_name=S3_BUCKET)

    return "Error processing document. Please try again."

if __name__ == '__main__':
    app.run()