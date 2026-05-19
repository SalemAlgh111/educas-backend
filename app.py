# app.py
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from models import db
from routes.analysis import analysis_bp
from routes.auth import auth_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///educas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

CORS(app, resources={r"/api/*": {"origins": "*"}})
jwt = JWTManager(app)
db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(analysis_bp, url_prefix='/api')

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

