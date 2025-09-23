import os
import boto3
from flask import Flask, render_template, request, redirect, url_for
import time

app = Flask(__name__)

# AWS Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION')
S3_BUCKET = os.environ.get('S3_BUCKET')

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