# analysis_routes.py
import os
import uuid
import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from datetime import datetime
import logging as logger
from models import db, Document, AnalysisSession, ClassificationResult, ReadabilityMetric
from ai_service import extract_text_from_file, analyze_text_with_ai

analysis_bp = Blueprint('analysis', __name__)

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create upload folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper functions for text statistics
def count_words(text):
    """Count number of words in text"""
    if not text:
        return 0
    # Split on whitespace and filter out empty strings
    words = re.findall(r'\b\w+\b', text)
    return len(words)

def count_sentences(text):
    """Count number of sentences in text"""
    if not text:
        return 0
    # Split on sentence endings: ., !, ?
    sentences = re.split(r'[.!?]+', text)
    # Filter out empty strings
    sentences = [s for s in sentences if s.strip()]
    return len(sentences)

def calculate_avg_word_length(text):
    """Calculate average word length in characters"""
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text)
    if not words:
        return 0
    total_length = sum(len(word) for word in words)
    return round(total_length / len(words), 2)

# analysis_routes.py - Updated analyze_file function
@analysis_bp.route('/analyze/file', methods=['POST'])
@jwt_required()
def analyze_file():
    """
    Analyze uploaded file (PDF, DOCX, TXT)
    """
    file_path = None
    
    try:
        logger.info("=" * 50)
        logger.info("Starting file analysis request")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.error("No file in request")
            return jsonify({"message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.error("Empty filename")
            return jsonify({"message": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            logger.error(f"File type not allowed: {file.filename}")
            return jsonify({"message": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
        # Get user ID
        user_id = int(get_jwt_identity())
        logger.info(f"User ID: {user_id}")
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save file temporarily
        file.save(file_path)
        logger.info(f"File saved to: {file_path}")
        logger.info(f"File size: {os.path.getsize(file_path)} bytes")
        
        # Extract text from file
        extracted_text = extract_text_from_file(file_path, file_ext)
        
        if not extracted_text:
            logger.error("Failed to extract text from file")
            return jsonify({
                "message": "Could not extract text from file. File may be empty, corrupted, or contain only images.",
                "error": "Text extraction failed"
            }), 400
        
        logger.info(f"Successfully extracted {len(extracted_text)} characters")
        
        # Calculate text statistics
        word_count = count_words(extracted_text)
        char_count = len(extracted_text)
        sentence_count = count_sentences(extracted_text)
        avg_word_length = calculate_avg_word_length(extracted_text)
        
        logger.info(f"Text statistics: {word_count} words, {char_count} chars, {sentence_count} sentences, avg word length: {avg_word_length}")
        
        # Save document to database
        document = Document(
            filename=original_filename,
            file_type=file_ext,
            content=extracted_text[:10000],
            user_id=user_id,
            # created_at=datetime.utcnow()
        )
        db.session.add(document)
        db.session.flush()
        logger.info(f"Document saved with ID: {document.id}")
        
        # Create analysis session
        session = AnalysisSession(
            user_id=user_id,
            document_id=document.id,
            status="processing",
            started_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.flush()
        logger.info(f"Analysis session created with ID: {session.id}")
        
        # Analyze with AI
        logger.info("Calling AI analysis...")
        ai_result = analyze_text_with_ai(extracted_text)
        
        if not ai_result["success"]:
            logger.error(f"AI analysis failed: {ai_result.get('error')}")
            session.status = "failed"
            db.session.commit()
            return jsonify({
                "message": "AI analysis failed",
                "error": ai_result.get("error", "Unknown error")
            }), 500
        
        result_data = ai_result["data"]
        logger.info(f"AI analysis successful: {result_data.get('primary_domain')}")
        
        # Save classification results
        classification = ClassificationResult(
            session_id=session.id,
            primary_domain=result_data.get("primary_domain"),
            secondary_subject=result_data.get("secondary_subject"),
            confidence=result_data.get("confidence", 0),
            key_topics=",".join(result_data.get("key_topics", [])),
            summary=result_data.get("summary", "")
        )
        db.session.add(classification)
        
        # Save readability metrics
        readability_data = result_data.get("readability", {})
        readability = ReadabilityMetric(
            session_id=session.id,
            flesch_kincaid=readability_data.get("flesch_kincaid"),
            smog_index=readability_data.get("smog_index"),
            gunning_fog=readability_data.get("gunning_fog"),
            coleman_liau=readability_data.get("coleman_liau")
        )
        db.session.add(readability)
        
        # Update session
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        
        db.session.commit()
        logger.info("All data saved successfully")
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Temporary file cleaned up")
        
        return jsonify({
            "message": "Analysis completed successfully",
            "session_id": session.id,
            "result": {
                "primary_domain": classification.primary_domain,
                "secondary_subject": classification.secondary_subject,
                "confidence": classification.confidence,
                "key_topics": result_data.get("key_topics", []),
                "summary": classification.summary,
                "readability": {
                    "flesch_kincaid": readability.flesch_kincaid,
                    "smog_index": readability.smog_index,
                    "gunning_fog": readability.gunning_fog,
                    "coleman_liau": readability.coleman_liau
                },
                "text_statistics": {
                    "word_count": word_count,
                    "character_count": char_count,
                    "sentence_count": sentence_count,
                    "average_word_length": avg_word_length
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"File analysis error: {str(e)}", exc_info=True)
        db.session.rollback()
        
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("Temporary file cleaned up after error")
            except:
                pass
        
        return jsonify({
            "message": "Server error during file analysis",
            "error": str(e)
        }), 500


@analysis_bp.route('/analyze', methods=['POST'])
@jwt_required()
def analyze_text():
    """
    Analyze text content directly
    Expects JSON: {"text": "content to analyze"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"message": "Invalid request body"}), 400
        
        text = data.get('text')
        
        if not text or not text.strip():
            return jsonify({"message": "Text content is required"}), 400
        
        if len(text) > 50000:
            return jsonify({"message": "Text too long. Maximum 50,000 characters"}), 400
        
        user_id = int(get_jwt_identity())
        
        # Calculate text statistics
        word_count = count_words(text)
        char_count = len(text)
        sentence_count = count_sentences(text)
        avg_word_length = calculate_avg_word_length(text)
        
        # Save document
        document = Document(
            filename="manual_input.txt",
            file_type="text",
            content=text[:10000],
            user_id=user_id,
            # created_at=datetime.utcnow()
        )
        db.session.add(document)
        db.session.flush()
        
        # Create session
        session = AnalysisSession(
            user_id=user_id,
            document_id=document.id,
            status="processing",
            started_at=datetime.utcnow()
        )
        db.session.add(session)
        db.session.flush()
        
        # Analyze with AI
        ai_result = analyze_text_with_ai(text)
        
        if not ai_result["success"]:
            session.status = "failed"
            db.session.commit()
            return jsonify({
                "message": "AI analysis failed",
                "error": ai_result.get("error", "Unknown error")
            }), 500
        
        result_data = ai_result["data"]
        
        # Save classification
        classification = ClassificationResult(
            session_id=session.id,
            primary_domain=result_data.get("primary_domain"),
            secondary_subject=result_data.get("secondary_subject"),
            confidence=result_data.get("confidence", 0),
            key_topics=",".join(result_data.get("key_topics", [])),
            summary=result_data.get("summary", "")
        )
        db.session.add(classification)
        
        # Save readability
        readability_data = result_data.get("readability", {})
        readability = ReadabilityMetric(
            session_id=session.id,
            flesch_kincaid=readability_data.get("flesch_kincaid"),
            smog_index=readability_data.get("smog_index"),
            gunning_fog=readability_data.get("gunning_fog"),
            coleman_liau=readability_data.get("coleman_liau")
        )
        db.session.add(readability)
        
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            "message": "Analysis completed successfully",
            "session_id": session.id,
            "result": {
                "primary_domain": classification.primary_domain,
                "secondary_subject": classification.secondary_subject,
                "confidence": classification.confidence,
                "key_topics": result_data.get("key_topics", []),
                "summary": classification.summary,
                "readability": {
                    "flesch_kincaid": readability.flesch_kincaid,
                    "smog_index": readability.smog_index,
                    "gunning_fog": readability.gunning_fog,
                    "coleman_liau": readability.coleman_liau
                },
                "text_statistics": {
                    "word_count": word_count,
                    "character_count": char_count,
                    "sentence_count": sentence_count,
                    "average_word_length": avg_word_length
                }
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Text analysis error: {str(e)}", exc_info=True)
        return jsonify({
            "message": "Server error during analysis",
            "error": str(e)
        }), 500


@analysis_bp.route('/results/<int:session_id>', methods=['GET'])
@jwt_required()
def get_analysis_results(session_id):
    """Get analysis results by session ID"""
    try:
        user_id = int(get_jwt_identity())
        
        session = AnalysisSession.query.filter_by(id=session_id, user_id=user_id).first()
        
        if not session:
            return jsonify({"message": "Session not found"}), 404
        
        document = Document.query.get(session.document_id)
        classification = ClassificationResult.query.filter_by(session_id=session.id).first()
        readability = ReadabilityMetric.query.filter_by(session_id=session.id).first()
        
        if not classification or not readability:
            return jsonify({"message": "Analysis results not found"}), 404
        
        # Note: text_statistics are not stored in database, so they are not included in GET results
        # If you need them, you would need to recalculate from document.content
        return jsonify({
            "session_id": session.id,
            "document": {
                "name": document.filename,
                "type": document.file_type,
                "size": len(document.content or "") if document.content else 0,
                "text": document.content[:3000] if document.content else "",
"timestamp": session.started_at.isoformat() if session.started_at else None            },
            "classification": {
                "primary_domain": classification.primary_domain,
                "secondary_subject": classification.secondary_subject,
                "confidence": classification.confidence,
                "key_topics": classification.key_topics.split(",") if classification.key_topics else [],
                "summary": classification.summary
            },
            "readability": {
                "flesch_kincaid": readability.flesch_kincaid,
                "smog_index": readability.smog_index,
                "gunning_fog": readability.gunning_fog,
                "coleman_liau": readability.coleman_liau
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get analysis results error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500