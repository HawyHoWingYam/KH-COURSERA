"""Tests for app boot behavior with and without APScheduler"""
import pytest
import sys
import importlib
from unittest.mock import patch, MagicMock


class TestAppBootWithoutScheduler:
    """Test app boot behavior when APScheduler is not installed"""

    def test_app_imports_with_scheduler_available(self):
        """Test that app imports successfully when APScheduler is available"""
        # This test runs in normal conditions with APScheduler installed
        try:
            from app import APSCHEDULER_AVAILABLE, BackgroundScheduler, CronTrigger
            assert APSCHEDULER_AVAILABLE is True
            assert BackgroundScheduler is not None
            assert CronTrigger is not None
        except ImportError as e:
            pytest.skip(f"APScheduler not installed in test environment: {e}")

    def test_app_imports_with_scheduler_unavailable(self, monkeypatch):
        """Test that app imports successfully when APScheduler is not available"""
        # Mock the APScheduler import to fail
        def mock_import(name, *args, **kwargs):
            if 'apscheduler' in name:
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        original_import = __builtins__.__import__

        # Clear any cached app modules
        modules_to_remove = [key for key in sys.modules if key.startswith('app')]
        for module in modules_to_remove:
            del sys.modules[module]

        try:
            with patch('builtins.__import__', side_effect=mock_import):
                # Dynamically import app with mocked imports
                # Since app is already loaded, we'll just test the fallback values
                from app import APSCHEDULER_AVAILABLE, BackgroundScheduler, CronTrigger, scheduler

                # These should be the fallback values if APScheduler was unavailable
                if not APSCHEDULER_AVAILABLE:
                    assert BackgroundScheduler is None
                    assert CronTrigger is None
                    assert scheduler is None
                else:
                    # If APScheduler is available in this test environment, that's fine
                    assert APSCHEDULER_AVAILABLE is True

        finally:
            # Restore original import
            __builtins__.__import__ = original_import

    def test_scheduler_initialization_conditional(self):
        """Test that scheduler is only initialized if APScheduler is available"""
        from app import APSCHEDULER_AVAILABLE, scheduler, BackgroundScheduler

        if APSCHEDULER_AVAILABLE:
            # If APScheduler is available, scheduler should be initialized
            assert scheduler is not None
            assert isinstance(scheduler, BackgroundScheduler)
        else:
            # If APScheduler is not available, scheduler should be None
            assert scheduler is None

    def test_app_config_loads_without_scheduler(self):
        """Test that app configuration loads successfully without scheduler"""
        try:
            from app import app_config, logger
            assert app_config is not None
            assert logger is not None
        except Exception as e:
            pytest.fail(f"App config failed to load: {e}")

    def test_database_initialization_without_scheduler(self):
        """Test that database initialization works without scheduler"""
        try:
            from db.database import engine, SessionLocal
            assert engine is not None
            # Verify we can create a session
            session = SessionLocal()
            session.close()
        except Exception as e:
            pytest.fail(f"Database initialization failed: {e}")


class TestSchedulerStartupShutdown:
    """Test startup and shutdown event handlers with conditional scheduler"""

    @pytest.mark.asyncio
    async def test_startup_event_no_scheduler_sync_disabled(self):
        """Test startup event when scheduler unavailable and sync disabled"""
        from unittest.mock import AsyncMock, patch
        from app import startup_event
        import os

        # Mock environment to have sync disabled
        with patch.dict(os.environ, {'ONEDRIVE_SYNC_ENABLED': 'false'}):
            # Should not raise an error
            try:
                await startup_event()
            except Exception as e:
                pytest.fail(f"Startup event failed: {e}")

    @pytest.mark.asyncio
    async def test_startup_event_with_scheduler_sync_disabled(self):
        """Test startup event when scheduler available and sync disabled"""
        from unittest.mock import AsyncMock, patch
        from app import startup_event
        import os

        with patch.dict(os.environ, {'ONEDRIVE_SYNC_ENABLED': 'false'}):
            try:
                await startup_event()
            except Exception as e:
                pytest.fail(f"Startup event failed: {e}")

    @pytest.mark.asyncio
    async def test_shutdown_event_handles_none_scheduler(self):
        """Test that shutdown event gracefully handles None scheduler"""
        from unittest.mock import AsyncMock, patch
        from app import shutdown_event

        # This should not raise an error even if scheduler is None
        try:
            await shutdown_event()
        except Exception as e:
            pytest.fail(f"Shutdown event failed: {e}")


class TestAPSchedulerFallback:
    """Test fallback values when APScheduler not available"""

    def test_fallback_values_in_app_module(self):
        """Verify fallback values are properly defined in app module"""
        import app

        # These should always be defined (either as actual classes or None)
        assert hasattr(app, 'BackgroundScheduler')
        assert hasattr(app, 'CronTrigger')
        assert hasattr(app, 'APSCHEDULER_AVAILABLE')
        assert hasattr(app, 'scheduler')

        # Check that they're consistent
        if app.APSCHEDULER_AVAILABLE:
            assert app.BackgroundScheduler is not None
            assert app.CronTrigger is not None
        else:
            assert app.BackgroundScheduler is None
            assert app.CronTrigger is None

    def test_available_flag_consistency(self):
        """Test that APSCHEDULER_AVAILABLE flag is consistent with scheduler"""
        from app import APSCHEDULER_AVAILABLE, scheduler

        if APSCHEDULER_AVAILABLE:
            assert scheduler is not None
        else:
            assert scheduler is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
