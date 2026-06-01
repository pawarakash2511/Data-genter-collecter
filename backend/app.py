from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from models import insert_customer

app = Flask(__name__)
CORS(app)

REQUIRED_FIELDS = ["customer_id", "customer_name", "gender", "age", "some_number"]


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
