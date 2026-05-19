from flask import Blueprint, request, jsonify
from models import User
from database import db

from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()


# =========================
# 📝 SIGNUP
# =========================
@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.json

    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')

    # validation
    if not full_name or not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already exists"}), 400

    # password rule (like your UI 🔥)
    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400

    # hash password
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role=role
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Account created successfully"
    }), 201


# =========================
# 🔐 LOGIN
# =========================
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json

    email = data.get('email')
    password = data.get('password')

    # find user
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"message": "Invalid email or password"}), 401

    # check password
    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({"message": "Invalid email or password"}), 401

    # create token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
    "message": "Login successful",
    "token": access_token,
    "user": {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role
    }
})