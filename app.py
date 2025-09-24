import os
import boto3
import time
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, jsonify
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
            # Redirect to the new status page instead of the old result page
            return redirect(url_for('status', job_id=response['JobId'], original_filename=file.filename))
        except Exception as e:
            return f"An error occurred: {str(e)}", 500
    
    return redirect(url_for('index'))

# NEW: Page that shows the spinner and polls the status
@app.route('/status/<job_id>/<original_filename>')
def status(job_id, original_filename):
    return render_template('status.html', job_id=job_id, original_filename=original_filename)

# NEW: API endpoint for the JavaScript to call
@app.route('/api/check_status/<job_id>')
def check_status(job_id):
    try:
        response = textract.get_document_text_detection(JobId=job_id)
        status = response.get('JobStatus')
        return jsonify({'status': status})
    except Exception as e:
        return jsonify({'status': 'FAILED', 'error': str(e)})

# NEW: Final processing route, called only when the job is done
@app.route('/process_result/<job_id>/<original_filename>')
def process_result(job_id, original_filename):
    try:
        response = textract.get_document_text_detection(JobId=job_id)
        if response.get('JobStatus') == 'SUCCEEDED':
            blocks = get_all_textract_blocks(job_id, response)
            csv_filename = create_and_upload_csv(blocks, original_filename)
            # Redirect to the final success page
            return redirect(url_for('success', csv_filename=csv_filename))
        else:
            return "Job did not succeed. Status: " + response.get('JobStatus'), 500
    except Exception as e:
        return f"An error occurred during final processing: {str(e)}", 500

# NEW: The final success page (renamed from result.html)
@app.route('/success/<csv_filename>')
def success(csv_filename):
    return render_template('result.html', csv_filename=csv_filename, bucket_name=S3_BUCKET)


# --- Helper Functions (No changes here) ---
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
    s3.upload_fileobj(
        bytes_buffer,
        S3_BUCKET,
        csv_filename,
        ExtraArgs={'ContentType': 'text/csv'}
    )
    return csv_filename

if __name__ == '__main__':
    app.run(debug=True)