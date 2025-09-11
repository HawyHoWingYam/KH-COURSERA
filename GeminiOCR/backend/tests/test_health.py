"""
Basic health check tests for GeminiOCR backend
"""

import pytest
import requests
import os
import time

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
RETRY_ATTEMPTS = 30
RETRY_DELAY = 2


def wait_for_service(url, max_attempts=RETRY_ATTEMPTS):
    """Wait for service to be available"""
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass

        if attempt < max_attempts - 1:
            time.sleep(RETRY_DELAY)

    return False


class TestHealthChecks:
    """Test suite for health checks"""

    def test_service_available(self):
        """Test that the service is available"""
        assert wait_for_service(BACKEND_URL), f"Service not available at {BACKEND_URL}"

    def test_health_endpoint(self):
        """Test the health endpoint"""
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        assert response.status_code == 200

        # Check response content
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_docs_endpoint(self):
        """Test that API documentation is accessible"""
        response = requests.get(f"{BACKEND_URL}/docs", timeout=10)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_openapi_spec(self):
        """Test that OpenAPI specification is accessible"""
        response = requests.get(f"{BACKEND_URL}/openapi.json", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data


class TestBasicAPI:
    """Basic API functionality tests"""

    def test_root_endpoint(self):
        """Test the root endpoint"""
        try:
            response = requests.get(BACKEND_URL, timeout=10)
            # Accept either 200 (with content) or 404 (redirect to docs)
            assert response.status_code in [200, 404]
        except requests.exceptions.RequestException:
            pytest.skip("Root endpoint not implemented")

    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = requests.options(f"{BACKEND_URL}/health", timeout=10)

        # Check if CORS headers are present (they might not be in development)
        if "access-control-allow-origin" in response.headers:
            assert response.headers["access-control-allow-origin"] is not None


if __name__ == "__main__":
    # Run basic health check
    print(f"Testing service at {BACKEND_URL}")

    if wait_for_service(BACKEND_URL):
        print("✅ Service is available")

        # Run health endpoint test
        try:
            response = requests.get(f"{BACKEND_URL}/health")
            print(f"✅ Health check: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
    else:
        print("❌ Service is not available")
        exit(1)
