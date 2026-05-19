from database import db
from datetime import datetime

# =========================
# 👤 Users Table
# =========================
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    role = db.Column(db.String(50), default="Educator")
    started_at=datetime.utcnow()

    # relationships
    sessions = db.relationship('AnalysisSession', backref='user', lazy=True)


# models.py - Add these fields to your existing models

class ClassificationResult(db.Model):
    __tablename__ = 'classification_results'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('analysis_sessions.id'))
    primary_domain = db.Column(db.String(50))
    secondary_subject = db.Column(db.String(100))
    confidence = db.Column(db.Integer)
    key_topics = db.Column(db.Text)  # Comma-separated topics
    summary = db.Column(db.Text)
    started_at=datetime.utcnow()

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    file_type = db.Column(db.String(50))
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    started_at=datetime.utcnow()

class AnalysisSession(db.Model):
    __tablename__ = 'analysis_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    status = db.Column(db.String(20))  # processing, completed, failed
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class ReadabilityMetric(db.Model):
    __tablename__ = 'readability_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('analysis_sessions.id'))
    flesch_kincaid = db.Column(db.Float)
    smog_index = db.Column(db.Float)
    gunning_fog = db.Column(db.Float)
    coleman_liau = db.Column(db.Float)