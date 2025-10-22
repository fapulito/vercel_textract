import boto3
import json
from typing import Dict, Optional


class LLMAnalyzer:
    """Service for analyzing OCR text using Amazon Bedrock with Claude 3 Haiku"""
    
    def __init__(self, region_name: str):
        """
        Initialize the LLM analyzer with Bedrock client
        
        Args:
            region_name: AWS region where Bedrock is available (e.g., 'us-east-1')
        """
        self.bedrock = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
        
    def analyze_document(self, text: str, analysis_type: str) -> Dict:
        """
        Analyze extracted text using Claude 3 Haiku
        
        Args:
            text: OCR extracted text from Textract
            analysis_type: One of 'general', 'invoice', 'contract', 'form'
            
        Returns:
            Structured JSON dictionary with analysis results
        """
        prompt = self._build_prompt(text, analysis_type)
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1  # Low temperature for consistent extraction
        }
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            analysis_text = response_body['content'][0]['text']
            
            # Parse JSON from response
            return self._parse_analysis(analysis_text, analysis_type)
            
        except Exception as e:
            return {
                "error": f"Bedrock API error: {str(e)}",
                "analysis_type": analysis_type
            }
    
    def _build_prompt(self, text: str, analysis_type: str) -> str:
        """
        Build specialized prompts for different document types
        
        Args:
            text: Document text to analyze
            analysis_type: Type of analysis to perform
            
        Returns:
            Formatted prompt string for Claude
        """
        # Limit text to ~4000 characters to stay within token limits
        truncated_text = text[:4000]
        
        base_instruction = f"""Analyze the following document text and extract structured information.
Return your response as valid JSON only, with no additional text.

Document text:
{truncated_text}

"""
        
        prompts = {
            'general': base_instruction + """
Provide a JSON response with:
{
  "summary": "Brief 2-3 sentence summary",
  "key_points": ["point1", "point2", "point3"],
  "document_type": "detected type (e.g., letter, report, form)",
  "entities": {
    "people": [],
    "organizations": [],
    "dates": [],
    "locations": []
  }
}""",
            
            'invoice': base_instruction + """
Extract invoice information as JSON:
{
  "vendor": "Company name",
  "invoice_number": "INV-123",
  "date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "total_amount": "123.45",
  "currency": "USD",
  "line_items": [
    {"description": "Item", "quantity": 1, "unit_price": "10.00", "total": "10.00"}
  ],
  "tax": "0.00",
  "subtotal": "123.45"
}""",
            
            'contract': base_instruction + """
Extract contract information as JSON:
{
  "contract_type": "Type of agreement",
  "parties": ["Party A", "Party B"],
  "effective_date": "YYYY-MM-DD",
  "expiration_date": "YYYY-MM-DD",
  "key_terms": [
    {"term": "Payment terms", "details": "Net 30"},
    {"term": "Termination", "details": "30 days notice"}
  ],
  "obligations": {
    "party_a": ["obligation1", "obligation2"],
    "party_b": ["obligation1", "obligation2"]
  },
  "important_clauses": ["clause1", "clause2"]
}""",
            
            'form': base_instruction + """
Extract form fields as JSON:
{
  "form_type": "Type of form",
  "fields": [
    {"label": "Name", "value": "John Doe"},
    {"label": "Date", "value": "2024-01-01"},
    {"label": "Signature", "value": "Present/Absent"}
  ],
  "checkboxes": [
    {"label": "Option A", "checked": true},
    {"label": "Option B", "checked": false}
  ],
  "completeness": "Complete/Incomplete/Partially Complete"
}"""
        }
        
        return prompts.get(analysis_type, prompts['general'])
    
    def _parse_analysis(self, analysis_text: str, analysis_type: str) -> Dict:
        """
        Parse and validate JSON response from Claude
        
        Args:
            analysis_text: Raw text response from Claude
            analysis_type: Type of analysis performed
            
        Returns:
            Parsed JSON dictionary or error dictionary
        """
        try:
            # Extract JSON from response (Claude might add explanation text)
            start = analysis_text.find('{')
            end = analysis_text.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = analysis_text[start:end]
                parsed_result = json.loads(json_str)
                
                # Add metadata
                parsed_result['analysis_type'] = analysis_type
                
                return parsed_result
            else:
                # Fallback if no JSON found
                return {
                    "error": "Could not parse JSON from response",
                    "raw_response": analysis_text,
                    "analysis_type": analysis_type
                }
                
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON: {str(e)}",
                "raw_response": analysis_text,
                "analysis_type": analysis_type
            }
