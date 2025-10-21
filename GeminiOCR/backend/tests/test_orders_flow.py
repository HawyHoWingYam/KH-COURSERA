"""
Tests for the new Orders processing pipeline

This test suite verifies:
1. OCR Order creation and management
2. File upload and attachment to orders
3. AWB monthly processing with S3 invoice discovery
4. Orders redirect from deprecated batch-jobs system
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Test fixtures and utilities
@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    from app import app
    return TestClient(app)

@pytest.fixture
def db_session():
    """Create a database session for tests"""
    from db.database import SessionLocal
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_company(db_session):
    """Create a sample company for testing"""
    from db.models import Company

    company = Company(
        company_name="Test Company",
        company_code="TST_001",
        active=True
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company

@pytest.fixture
def sample_doc_type(db_session):
    """Create a sample document type for testing"""
    from db.models import DocumentType

    doc_type = DocumentType(
        type_name="Air Waybill",
        type_code="AWB",
        description="Air Waybill documents",
        has_template=False
    )
    db_session.add(doc_type)
    db_session.commit()
    db_session.refresh(doc_type)
    return doc_type

@pytest.fixture
def sample_config(db_session, sample_company, sample_doc_type):
    """Create a sample configuration for testing"""
    from db.models import CompanyDocumentConfig

    config = CompanyDocumentConfig(
        company_id=sample_company.company_id,
        doc_type_id=sample_doc_type.doc_type_id,
        prompt_path="prompts/awb.txt",
        schema_path="schemas/awb.json",
        active=True
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


class TestOrderCreation:
    """Test OCR Order creation via API"""

    def test_create_order(self, client, db_session, sample_company, sample_doc_type, sample_config):
        """Test creating a new OCR order"""
        response = client.post(
            "/orders",
            json={
                "order_name": "Test Order 1",
                "primary_doc_type_id": sample_doc_type.doc_type_id
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "order_id" in data
        assert data["order_name"] == "Test Order 1"
        assert data["status"] == "DRAFT"

    def test_create_order_with_invalid_doc_type(self, client, db_session):
        """Test creating order with non-existent document type"""
        response = client.post(
            "/orders",
            json={
                "order_name": "Invalid Order",
                "primary_doc_type_id": 99999
            }
        )

        assert response.status_code == 404

    def test_list_orders(self, client, db_session, sample_doc_type):
        """Test listing orders"""
        # Create a test order first
        create_response = client.post(
            "/orders",
            json={
                "order_name": "Order for listing",
                "primary_doc_type_id": sample_doc_type.doc_type_id
            }
        )
        assert create_response.status_code == 201

        # List orders
        response = client.get("/orders")
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data or isinstance(data, list)


class TestOrderItems:
    """Test OCR Order Item creation and file attachment"""

    def test_create_order_item(self, client, db_session, sample_doc_type, sample_company, sample_config):
        """Test creating an order item"""
        # Create order first
        order_response = client.post(
            "/orders",
            json={
                "order_name": "Test Order with Items",
                "primary_doc_type_id": sample_doc_type.doc_type_id
            }
        )
        order_id = order_response.json()["order_id"]

        # Create order item
        item_response = client.post(
            f"/orders/{order_id}/items",
            json={
                "company_id": sample_company.company_id,
                "doc_type_id": sample_doc_type.doc_type_id,
                "item_name": "Test Item 1"
            }
        )

        assert item_response.status_code == 201
        item_data = item_response.json()
        assert "item_id" in item_data
        assert item_data["item_name"] == "Test Item 1"

    def test_attach_file_to_item(self, client, db_session, sample_doc_type, sample_company, sample_config):
        """Test attaching a file to an order item"""
        # Create order
        order_response = client.post(
            "/orders",
            json={
                "order_name": "Order with Files",
                "primary_doc_type_id": sample_doc_type.doc_type_id
            }
        )
        order_id = order_response.json()["order_id"]

        # Create order item
        item_response = client.post(
            f"/orders/{order_id}/items",
            json={
                "company_id": sample_company.company_id,
                "doc_type_id": sample_doc_type.doc_type_id,
                "item_name": "Item with File"
            }
        )
        item_id = item_response.json()["item_id"]

        # Mock file upload
        from db.models import File as DBFile
        test_file = DBFile(
            file_name="test.pdf",
            file_path="s3://bucket/test.pdf",
            file_category="document",
            file_size=1024,
            file_type="application/pdf"
        )
        db_session.add(test_file)
        db_session.commit()
        db_session.refresh(test_file)

        # Attach file to item
        attach_response = client.post(
            f"/orders/{order_id}/items/{item_id}/files",
            json={"file_id": test_file.file_id}
        )

        assert attach_response.status_code == 200


class TestAWBMonthlyProcessing:
    """Test AWB monthly processing endpoint"""

    @patch('utils.s3_storage.S3StorageManager.list_awb_invoices_for_month')
    @patch('utils.s3_storage.S3StorageManager.upload_file')
    def test_awb_monthly_processing_creates_order(
        self,
        mock_upload,
        mock_list_invoices,
        client,
        db_session,
        sample_company,
        sample_doc_type,
        sample_config
    ):
        """Test that AWB monthly processing creates an OCR order"""
        # Mock S3 operations
        mock_upload.return_value = True
        mock_list_invoices.return_value = [
            {
                'key': 'invoice1.pdf',
                'full_key': 'upload/onedrive/airway-bills/2025/01/invoice1.pdf',
                'size': 102400,
                'last_modified': '2025-01-15T10:00:00Z'
            }
        ]

        # Create test files
        from io import BytesIO
        from fastapi import UploadFile

        summary_file = BytesIO(b"test pdf content")
        summary_file.name = "summary.pdf"

        employees_file = BytesIO(b"name,department\nJohn Doe,Sales")
        employees_file.name = "employees.csv"

        # Submit AWB monthly processing
        response = client.post(
            "/api/awb/process-monthly",
            data={
                "company_id": sample_company.company_id,
                "month": "2025-01"
            },
            files={
                "summary_pdf": ("summary.pdf", summary_file, "application/pdf"),
                "employees_csv": ("employees.csv", employees_file, "text/csv")
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "order_id" in data
        assert data["invoices_found"] >= 0

    @patch('utils.s3_storage.S3StorageManager.list_awb_invoices_for_month')
    def test_awb_monthly_with_no_invoices(
        self,
        mock_list_invoices,
        client,
        db_session,
        sample_company,
        sample_doc_type,
        sample_config
    ):
        """Test AWB processing when no invoices are found in S3"""
        # Mock empty invoice list
        mock_list_invoices.return_value = []

        from io import BytesIO

        summary_file = BytesIO(b"test pdf content")
        summary_file.name = "summary.pdf"

        # Submit AWB monthly processing with no invoices
        response = client.post(
            "/api/awb/process-monthly",
            data={
                "company_id": sample_company.company_id,
                "month": "2025-01"
            },
            files={
                "summary_pdf": ("summary.pdf", summary_file, "application/pdf")
            }
        )

        # Should still succeed - OneDrive sync will be triggered as fallback
        assert response.status_code in [200, 202]


class TestUploadPageIntegration:
    """Test Upload page integration with Orders API"""

    def test_upload_creates_order_and_items(self, client, db_session, sample_company, sample_doc_type, sample_config):
        """Test that upload page correctly creates order and items"""
        from io import BytesIO

        # First, verify /api/orders endpoint exists
        order_response = client.post(
            "/orders",
            json={
                "order_name": "Upload Test",
                "primary_doc_type_id": sample_doc_type.doc_type_id
            }
        )
        assert order_response.status_code == 201
        order_id = order_response.json()["order_id"]

        # Verify we can create items
        item_response = client.post(
            f"/orders/{order_id}/items",
            json={
                "company_id": sample_company.company_id,
                "doc_type_id": sample_doc_type.doc_type_id,
                "item_name": "Uploaded Document 1"
            }
        )
        assert item_response.status_code == 201

        # Verify order details are retrievable
        get_response = client.get(f"/orders/{order_id}")
        assert get_response.status_code == 200
        assert get_response.json()["order_id"] == order_id


class TestMigrationFromBatchJobs:
    """Test that the system has successfully migrated from batch-jobs"""

    def test_batch_jobs_endpoints_removed(self, client):
        """Verify old batch-jobs endpoints no longer exist"""
        # These endpoints should return 404 or 405
        endpoints_to_check = [
            "/process",
            "/process-zip",
            "/process-batch",
            "/batch-jobs",
            "/batch-jobs/1"
        ]

        for endpoint in endpoints_to_check:
            # GET request
            get_response = client.get(endpoint)
            assert get_response.status_code in [404, 405], f"GET {endpoint} should not exist"

            # POST request
            post_response = client.post(endpoint, json={})
            assert post_response.status_code in [404, 405], f"POST {endpoint} should not exist"

    def test_orders_endpoints_exist(self, client):
        """Verify new Orders endpoints are available"""
        # These endpoints should be accessible (may return 200 or 404 for specific resources)
        endpoints_to_check = [
            ("/orders", "POST"),
            ("/orders", "GET"),
        ]

        for endpoint, method in endpoints_to_check:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})

            # Should not be 405 Method Not Allowed (which would mean endpoint doesn't exist)
            assert response.status_code != 405, f"{method} {endpoint} should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
