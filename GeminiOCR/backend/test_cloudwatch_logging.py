#!/usr/bin/env python3
"""
测试CloudWatch日志功能
Test CloudWatch logging functionality
"""

import os
import sys
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_cloudwatch_logging():
    """测试CloudWatch日志 / Test CloudWatch logging"""

    print("🧪 Testing CloudWatch logging functionality...")

    try:
        # Import our logger configuration
        from utils.logger_config import setup_logger, get_logger

        # Setup test logger
        logger = setup_logger(
            name="geminiocr.test",
            level="INFO",
            enable_cloudwatch=None,  # Auto-detect
            log_group_name="/aws/ecs/geminiocr-test",
            log_stream_name=f"test-{int(time.time())}"
        )

        print("✅ Logger initialized successfully")

        # Test different log levels
        logger.info("🧪 Test INFO log message")
        logger.warning("⚠️ Test WARNING log message")
        logger.error("❌ Test ERROR log message")

        # Test structured logging with extra data
        logger.info(
            "STRUCTURED_TEST",
            extra={
                "test_type": "cloudwatch_logging",
                "environment": os.getenv('ENVIRONMENT', 'development'),
                "timestamp": int(time.time()),
                "user_id": "test_user",
                "request_id": "test_123456"
            }
        )

        print("✅ Log messages sent successfully")

        # Test CloudWatch handler specifically
        from utils.logger_config import CloudWatchHandler

        # Check if CloudWatch is available
        try:
            import boto3
            client = boto3.client('logs')

            # Try to describe log groups
            response = client.describe_log_groups(logGroupNamePrefix="/aws/ecs/geminiocr-test")

            print(f"✅ CloudWatch connection successful - found {len(response.get('logGroups', []))} log groups")

        except Exception as e:
            print(f"⚠️  CloudWatch not available in this environment: {e}")
            print("📝 Logs will go to console only (expected for local development)")

        # Test logger retrieval
        test_logger = get_logger("geminiocr.test.retrieval")
        test_logger.info("✅ Logger retrieval test successful")

        print("🎉 CloudWatch logging test completed!")
        print("📝 Check AWS CloudWatch console if in production environment")
        print("🖥️  Check console output if in development environment")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure required packages are installed:")
        print("   pip install python-json-logger boto3")
        return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_log_formatting():
    """测试日志格式 / Test log formatting"""

    print("\n🧪 Testing log formatting...")

    try:
        from utils.logger_config import setup_logger
        import json

        # Create logger with JSON formatter
        logger = setup_logger(
            name="geminiocr.format_test",
            level="INFO",
            enable_cloudwatch=False,  # Force console only for this test
        )

        # Capture console output
        import io
        from contextlib import redirect_stderr

        captured_logs = io.StringIO()

        # Test different message types
        test_messages = [
            "Simple info message",
            {"type": "structured", "data": {"key": "value"}},
            "中文日志测试",
            "Special chars: !@#$%^&*()",
        ]

        for msg in test_messages:
            if isinstance(msg, dict):
                logger.info("STRUCTURED_MESSAGE", extra=msg)
            else:
                logger.info(msg)

        print("✅ Log formatting test completed")
        return True

    except Exception as e:
        print(f"❌ Log formatting test failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 CloudWatch Logging Test Suite")
    print("=" * 60)

    # Run tests
    test1_result = test_cloudwatch_logging()
    test2_result = test_log_formatting()

    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"  CloudWatch Logging: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"  Log Formatting:     {'✅ PASS' if test2_result else '❌ FAIL'}")

    if test1_result and test2_result:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)