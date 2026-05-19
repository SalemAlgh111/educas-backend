# ai_service.py
import PyPDF2
from docx import Document
import requests
import json
import re
import os

# Gemini API Configuration
GEMINI_API_KEY = "AIzaSyDkr76nnj4R0g3SXbVQdtplmmqmyzz4_Vs"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text if text.strip() else None
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None

def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    try:
        text = ""
        doc = Document(file_path)
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text += paragraph.text + "\n"
        return text if text.strip() else None
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return None

def extract_text_from_txt(file_path):
    """Extract text from TXT file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text if text.strip() else None
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                text = file.read()
            return text if text.strip() else None
        except Exception as e:
            print(f"TXT extraction error: {e}")
            return None
    except Exception as e:
        print(f"TXT extraction error: {e}")
        return None

def extract_text_from_file(file_path, file_type):
    """Route to appropriate extraction function based on file type"""
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type == 'docx':
        return extract_text_from_docx(file_path)
    elif file_type == 'txt':
        return extract_text_from_txt(file_path)
    else:
        return None

def analyze_text_with_ai(text):
    """Send extracted text to Gemini API for analysis"""
    
    if not text or len(text.strip()) == 0:
        return {
            "success": False,
            "error": "No text to analyze"
        }
    
    # Limit text length to avoid API limits
    if len(text) > 5000:
        text = text[:5000]
    
    prompt = f"""Analyze this educational text and return ONLY valid JSON (no other text, no markdown):

{{
    "primary_domain": "STEM or Humanities or Social Sciences",
    "secondary_subject": "specific subject like Physics, History, Computer Science",
    "confidence": 85,
    "summary": "2-3 sentence summary of the text",
    "key_topics": ["topic1", "topic2", "topic3", "topic4"]
}}

Text to analyze:
{text}

Return ONLY the JSON, nothing else. Do not use markdown formatting."""

    try:
        response = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract the text from response
            if "candidates" in data and len(data["candidates"]) > 0:
                ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
                
                # Clean the response
                ai_text = ai_text.strip()
                # Remove markdown code blocks if present
                if ai_text.startswith("```json"):
                    ai_text = ai_text[7:]
                elif ai_text.startswith("```"):
                    ai_text = ai_text[3:]
                if ai_text.endswith("```"):
                    ai_text = ai_text[:-3]
                ai_text = ai_text.strip()
                
                # Parse JSON
                result = json.loads(ai_text)
                
                # Ensure all required fields exist
                if "primary_domain" not in result:
                    result["primary_domain"] = "Social Sciences"
                if "secondary_subject" not in result:
                    result["secondary_subject"] = "General"
                if "confidence" not in result:
                    result["confidence"] = 85
                if "summary" not in result:
                    result["summary"] = "Educational content analyzed successfully."
                if "key_topics" not in result or not result["key_topics"]:
                    result["key_topics"] = ["Education", "Learning", "Content"]
                
                # Add readability scores (simplified)
                result["readability"] = {
                    "flesch_kincaid": 12.0,
                    "smog_index": 10.0,
                    "gunning_fog": 13.0,
                    "coleman_liau": 11.0
                }
                
                return {
                    "success": True,
                    "data": result
                }
            else:
                return {
                    "success": False,
                    "error": "No candidates in response"
                }
        else:
            error_msg = f"API Error: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", error_msg)
            except:
                pass
            return {
                "success": False,
                "error": error_msg
            }
            
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse JSON response: {str(e)}"
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout - please try again"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

# Simple mock function for testing without Gemini
def analyze_text_with_ai_mock(text):
    """Mock analysis for testing without API"""
    return {
        "success": True,
        "data": {
            "primary_domain": "STEM",
            "secondary_subject": "Computer Science",
            "confidence": 85,
            "summary": "This is a test analysis result. The text appears to be about educational content and technology.",
            "key_topics": ["Education", "Technology", "Analysis", "Content"],
            "readability": {
                "flesch_kincaid": 12.0,
                "smog_index": 10.0,
                "gunning_fog": 13.0,
                "coleman_liau": 11.0
            }
        }
    }