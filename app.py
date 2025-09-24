import os
import boto3
import time
import csv
import io
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- Configuration and AWS Clients ---
S3_BUCKET = os.environ.get('S3_BUCKET')
AWS_REGION = os.environ.get('AWS_REGION')
if not all([S3_BUCKET, AWS_REGION, os.environ.get('AWS_ACCESS_KEY_ID'), os.environ.get('AWS_SECRET_ACCESS_KEY')]):
    raise ValueError("One or more essential environment variables are missing.")

s3 = boto3.client('s3', region_name=AWS_REGION)
textract = boto3.client('textract', region_name=AWS_REGION)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return "No file part in the request.", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No file selected.", 400

    if file:
        try:
            s3.upload_fileobj(
                file,
                S3_BUCKET,
                file.filename,
                ExtraArgs={'ContentType': file.content_type}
            )
            response = textract.start_document_text_detection(
                DocumentLocation={'S3Object': {'Bucket': S3_BUCKET, 'Name': file.filename}}
            )
            return redirect(url_for('result', job_id=response['JobId'], original_filename=file.filename))
        except Exception as e:
            return f"An error occurred: {str(e)}", 500
    
    return redirect(url_for('index'))

@app.route('/result/<job_id>/<original_filename>')
def result(job_id, original_filename):
    max_retries = 3 
    retries = 0
    
    while retries < max_retries:
        try:
            response = textract.get_document_text_detection(JobId=job_id)
            status = response.get('JobStatus')

            if status == 'SUCCEEDED':
                blocks = get_all_textract_blocks(job_id, response)
                csv_filename = create_and_upload_csv(blocks, original_filename)
                return render_template('result.html', csv_filename=csv_filename, bucket_name=S3_BUCKET)
            
            elif status == 'FAILED':
                return f"Textract job failed: {response.get('StatusMessage')}", 500

            time.sleep(5)
            retries += 1
            
        except Exception as e:
            return f"An error occurred while checking job status: {str(e)}", 500

    return "The document processing timed out. Please try again with a smaller document.", 504

# --- Helper Functions ---
def get_all_textract_blocks(job_id, initial_response):
    """Paginates through Textract results to get all blocks."""
    blocks = initial_response['Blocks']
    next_token = initial_response.get('NextToken')
    
    while next_token:
        response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        blocks.extend(response['Blocks'])
        next_token = response.get('NextToken')
        
    return blocks

def create_and_upload_csv(blocks, original_filename):
    """Generates a CSV in memory from Textract blocks and uploads it to S3."""
    # Step 1: Use StringIO to build the CSV in a text buffer
    string_buffer = io.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerow(['DetectedText']) # Header

    for block in blocks:
        if block['BlockType'] == 'LINE':
            writer.writerow([block['Text']])
    
    # Step 2: Get the string content and encode it to UTF-8 bytes
    csv_string = string_buffer.getvalue()
    csv_bytes = csv_string.encode('utf-8')

    # Step 3: Create a BytesIO object (in-memory binary buffer)
    bytes_buffer = io.BytesIO(csv_bytes)

    base_filename = os.path.splitext(original_filename)[0]
    csv_filename = f"{base_filename}_result.csv"
    
    # Step 4: Upload the binary buffer to S3
    s3.upload_fileobj(
        bytes_buffer,
        S3_BUCKET,
        csv_filename,
        ExtraArgs={'ContentType': 'text/csv'}
    )
    return csv_filename

if __name__ == '__main__':
    app.run(debug=True)