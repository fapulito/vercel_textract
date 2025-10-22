#!/usr/bin/env python3
"""Simple Bedrock test to check exact error"""

import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

region = os.environ.get('AWS_REGION', 'us-east-1')
print(f"Testing Bedrock in region: {region}")

try:
    # Try to invoke with minimal request
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
    
    model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 50,
        "messages": [
            {
                "role": "user",
                "content": "Hello"
            }
        ]
    }
    
    print(f"Attempting to invoke: {model_id}")
    
    response = bedrock_runtime.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    print("✅ SUCCESS!")
    print(f"Response: {response_body['content'][0]['text']}")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    print(f"\nError type: {type(e).__name__}")
    
    # Check if it's an access denied error
    if 'AccessDeniedException' in str(e):
        print("\n🔍 This is an access/permission error.")
        print("Possible causes:")
        print("1. First-time Anthropic user - need to submit use case")
        print("2. Payment method validation pending")
        print("3. IAM policy missing bedrock:InvokeModel permission")
        
        if 'INVALID_PAYMENT_INSTRUMENT' in str(e):
            print("\n💳 PAYMENT ISSUE DETECTED")
            print("Action required:")
            print("1. Go to AWS Bedrock Console → Playgrounds")
            print("2. Try to use Claude 3 Haiku in the playground")
            print("3. Fill out the use case form that appears")
            print("4. Wait for approval (usually instant)")
