#!/usr/bin/env python3
"""
Test script to verify Amazon Bedrock connectivity and permissions.
Run this after setting up your AWS credentials to ensure everything is configured correctly.

Usage:
    python test_bedrock_connection.py
"""

import os
import sys
import json
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_aws_credentials():
    """Test that AWS credentials are configured"""
    print("🔍 Testing AWS credentials...")
    
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_REGION')
    
    if not access_key or not secret_key:
        print("❌ AWS credentials not found in environment variables")
        print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file")
        return False
    
    if not region:
        print("⚠️  AWS_REGION not set, defaulting to us-east-1")
        region = 'us-east-1'
    
    print(f"✅ AWS credentials found")
    print(f"   Region: {region}")
    print(f"   Access Key: {access_key[:10]}...")
    return True

def test_bedrock_access():
    """Test Bedrock API access"""
    print("\n🔍 Testing Amazon Bedrock access...")
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    try:
        bedrock = boto3.client('bedrock', region_name=region)
        
        # List foundation models
        response = bedrock.list_foundation_models(byProvider='anthropic')
        
        models = response.get('modelSummaries', [])
        print(f"✅ Successfully connected to Bedrock in {region}")
        print(f"   Found {len(models)} Anthropic models")
        
        # Check for Claude 3 Haiku
        haiku_model = None
        for model in models:
            if 'claude-3-haiku' in model['modelId']:
                haiku_model = model
                break
        
        if haiku_model:
            print(f"✅ Claude 3 Haiku is available")
            print(f"   Model ID: {haiku_model['modelId']}")
        else:
            print("⚠️  Claude 3 Haiku not found in available models")
            print("   You may need to enable model access in the Bedrock console")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to connect to Bedrock: {str(e)}")
        print("\n   Possible solutions:")
        print("   1. Enable Bedrock model access in AWS Console")
        print("   2. Verify IAM permissions include bedrock:ListFoundationModels")
        print("   3. Check that your region supports Bedrock")
        print("   4. Supported regions: us-east-1, us-west-2, ap-southeast-1, eu-central-1")
        return False

def test_bedrock_invoke():
    """Test invoking Claude 3 Haiku model"""
    print("\n🔍 Testing Claude 3 Haiku invocation...")
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
    
    try:
        bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        
        # Simple test prompt
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'Hello, Bedrock!' and nothing else."
                }
            ],
            "temperature": 0.1
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text']
        
        print(f"✅ Successfully invoked Claude 3 Haiku")
        print(f"   Response: {response_text}")
        print(f"   Input tokens: {response_body.get('usage', {}).get('input_tokens', 'N/A')}")
        print(f"   Output tokens: {response_body.get('usage', {}).get('output_tokens', 'N/A')}")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Failed to invoke Claude 3 Haiku: {error_msg}")
        print("\n   Possible solutions:")
        
        if 'AccessDeniedException' in error_msg:
            print("   1. Add bedrock:InvokeModel permission to your IAM policy")
            print("   2. Enable model access in AWS Console → Bedrock → Model access")
            print("   3. Wait a few minutes for permissions to propagate")
        elif 'ValidationException' in error_msg:
            print("   1. Verify the model ID is correct")
            print("   2. Check that Claude 3 Haiku is available in your region")
        else:
            print("   1. Check your IAM permissions")
            print("   2. Verify your AWS credentials are valid")
            print("   3. Ensure your region supports Bedrock")
        
        return False

def test_s3_access():
    """Test S3 bucket access"""
    print("\n🔍 Testing S3 bucket access...")
    
    bucket = os.environ.get('S3_BUCKET')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not bucket:
        print("⚠️  S3_BUCKET not set in environment variables")
        return False
    
    try:
        s3 = boto3.client('s3', region_name=region)
        
        # Try to list objects (will work even if bucket is empty)
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        
        print(f"✅ Successfully accessed S3 bucket: {bucket}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to access S3 bucket: {str(e)}")
        print("\n   Possible solutions:")
        print("   1. Verify the bucket name is correct")
        print("   2. Check IAM permissions include s3:ListBucket and s3:GetObject")
        print("   3. Ensure the bucket exists in your AWS account")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Amazon Bedrock Connection Test")
    print("=" * 60)
    
    results = []
    
    # Test 1: AWS Credentials
    results.append(("AWS Credentials", test_aws_credentials()))
    
    if not results[0][1]:
        print("\n❌ Cannot proceed without AWS credentials")
        sys.exit(1)
    
    # Test 2: S3 Access
    results.append(("S3 Access", test_s3_access()))
    
    # Test 3: Bedrock Access
    results.append(("Bedrock Access", test_bedrock_access()))
    
    # Test 4: Bedrock Invoke (only if access test passed)
    if results[-1][1]:
        results.append(("Bedrock Invoke", test_bedrock_invoke()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Your Bedrock setup is ready.")
        print("   You can now run the application with LLM analysis enabled.")
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        print("   Refer to README-2.md for detailed setup instructions.")
        sys.exit(1)

if __name__ == '__main__':
    main()
