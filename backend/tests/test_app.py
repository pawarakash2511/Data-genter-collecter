"""
Unit tests for backend/app.py.
The database layer is mocked — no real MySQL connection needed.
"""
import sys
import os
import pytest
from unittest.mock import patch
from datetime import datetime

# Make sure `app` is importable from the backend root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ── Happy-path ────────────────────────────────────────────────────────────────

class TestSuccessfulSubmission:
    def test_returns_201_and_success_status(self, client):
        with patch("app.insert_customer", return_value=1):
            resp = client.post("/api/customers", json={
                "customer_id": "CUST001",
                "customer_name": "John Doe",
                "gender": "Male",
                "age": 25,
                "some_number": 20,
            })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["status"] == "success"
        assert "message" in body

    def test_age_incremented_by_one(self, client):
        """Backend must store age + 1 regardless of what frontend sends."""
        captured = {}
        def capture(record):
            captured.update(record)
            return 1

        with patch("app.insert_customer", side_effect=capture):
            client.post("/api/customers", json={
                "customer_id": "CUST002",
                "customer_name": "Jane",
                "gender": "Female",
                "age": 25,
                "some_number": 10,
            })
        assert captured["age"] == 26

    def test_some_number_stored_as_received(self, client):
        """Frontend doubles some_number before sending; backend stores the value as-is."""
        captured = {}
        def capture(record):
            captured.update(record)
            return 1

        with patch("app.insert_customer", side_effect=capture):
            client.post("/api/customers", json={
                "customer_id": "CUST003",
                "customer_name": "Alex",
                "gender": "Other",
                "age": 30,
                "some_number": 20,   # 10 * 2 already applied by JS
            })
        assert captured["some_number"] == 20

    def test_submitted_at_is_a_datetime(self, client):
        captured = {}
        def capture(record):
            captured.update(record)
            return 1

        with patch("app.insert_customer", side_effect=capture):
            client.post("/api/customers", json={
                "customer_id": "CUST004",
                "customer_name": "Test User",
                "gender": "Male",
                "age": 20,
                "some_number": 5,
            })
        assert isinstance(captured.get("submitted_at"), datetime)

    def test_whitespace_in_strings_is_stripped(self, client):
        captured = {}
        def capture(record):
            captured.update(record)
            return 1

        with patch("app.insert_customer", side_effect=capture):
            client.post("/api/customers", json={
                "customer_id": "  CUST005  ",
                "customer_name": "  Bob  ",
                "gender": "Male",
                "age": 40,
                "some_number": 8,
            })
        assert captured["customer_id"] == "CUST005"
        assert captured["customer_name"] == "Bob"

    @pytest.mark.parametrize("gender", ["Male", "Female", "Other"])
    def test_all_gender_options_accepted(self, client, gender):
        with patch("app.insert_customer", return_value=1):
            resp = client.post("/api/customers", json={
                "customer_id": "CUST006",
                "customer_name": "Test",
                "gender": gender,
                "age": 25,
                "some_number": 10,
            })
        assert resp.status_code == 201

    def test_age_zero_is_valid(self, client):
        captured = {}
        def capture(record):
            captured.update(record)
            return 1

        with patch("app.insert_customer", side_effect=capture):
            resp = client.post("/api/customers", json={
                "customer_id": "CUST007",
                "customer_name": "Baby",
                "gender": "Male",
                "age": 0,
                "some_number": 2,
            })
        assert resp.status_code == 201
        assert captured["age"] == 1  # 0 + 1


# ── Validation errors ─────────────────────────────────────────────────────────

class TestValidation:
    def test_missing_customer_id_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_name": "John",
            "gender": "Male",
            "age": 25,
            "some_number": 10,
        })
        assert resp.status_code == 400
        assert "customer_id" in resp.get_json()["message"]

    def test_missing_customer_name_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_id": "CUST001",
            "gender": "Male",
            "age": 25,
            "some_number": 10,
        })
        assert resp.status_code == 400

    def test_missing_gender_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_id": "CUST001",
            "customer_name": "John",
            "age": 25,
            "some_number": 10,
        })
        assert resp.status_code == 400

    def test_missing_age_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_id": "CUST001",
            "customer_name": "John",
            "gender": "Male",
            "some_number": 10,
        })
        assert resp.status_code == 400

    def test_missing_some_number_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_id": "CUST001",
            "customer_name": "John",
            "gender": "Male",
            "age": 25,
        })
        assert resp.status_code == 400

    def test_empty_string_customer_id_returns_400(self, client):
        resp = client.post("/api/customers", json={
            "customer_id": "",
            "customer_name": "John",
            "gender": "Male",
            "age": 25,
            "some_number": 10,
        })
        assert resp.status_code == 400

    def test_empty_json_body_returns_400(self, client):
        resp = client.post("/api/customers", json={})
        assert resp.status_code == 400

    def test_invalid_json_returns_400(self, client):
        resp = client.post(
            "/api/customers",
            data="not-valid-json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_no_body_returns_400(self, client):
        resp = client.post("/api/customers")
        assert resp.status_code == 400

    def test_missing_all_fields_returns_400(self, client):
        resp = client.post("/api/customers", json={"extra_field": "value"})
        assert resp.status_code == 400


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_db_exception_returns_500(self, client):
        with patch("app.insert_customer", side_effect=Exception("DB connection failed")):
            resp = client.post("/api/customers", json={
                "customer_id": "CUST001",
                "customer_name": "John",
                "gender": "Male",
                "age": 25,
                "some_number": 10,
            })
        assert resp.status_code == 500
        body = resp.get_json()
        assert body["status"] == "error"
