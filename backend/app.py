import os
from functools import wraps
from datetime import datetime, timedelta

import jwt
from flask import Flask, request, jsonify
from flask_cors import CORS

from models import insert_customer, get_all_customers

app = Flask(__name__)
CORS(app)

REQUIRED_FIELDS = ["customer_id", "customer_name", "gender", "age", "some_number"]

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "AkashPawar")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Akash34567")
JWT_SECRET = os.getenv("JWT_SECRET", "customer-app-admin-secret-2024")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if not token:
            return jsonify({"status": "error", "message": "Token required"}), 401
        try:
            jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Session expired — please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"status": "error", "message": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/customers", methods=["POST"])
def create_customer():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] == ""]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        record = {
            "customer_id": str(data["customer_id"]).strip(),
            "customer_name": str(data["customer_name"]).strip(),
            "gender": str(data["gender"]).strip(),
            "age": int(data["age"]) + 1,          # business logic: age + 1
            "some_number": int(data["some_number"]),
            "submitted_at": datetime.utcnow(),
        }
        insert_customer(record)
        return jsonify({"status": "success", "message": "Customer data saved successfully"}), 201
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
    if data.get("username") != ADMIN_USERNAME or data.get("password") != ADMIN_PASSWORD:
        return jsonify({"status": "error", "message": "Invalid username or password"}), 401
    token = jwt.encode(
        {"sub": ADMIN_USERNAME, "exp": datetime.utcnow() + timedelta(hours=8)},
        JWT_SECRET,
        algorithm="HS256",
    )
    return jsonify({"status": "success", "token": token}), 200


@app.route("/api/admin/customers", methods=["GET"])
@token_required
def admin_get_customers():
    try:
        customers = get_all_customers()
        return jsonify({"status": "success", "data": customers, "count": len(customers)}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
