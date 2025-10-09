"""
配置统一的日志系统，支持本地开发环境和AWS CloudWatch生产环境
Provides unified logging configuration for local development and AWS CloudWatch production
"""

import logging
import json
import sys
import os
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger

# AWS CloudWatch imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False
    print("⚠️  boto3 not available - CloudWatch logging disabled", file=sys.stderr)


class CloudWatchHandler(logging.Handler):
    """
    自定义CloudWatch日志处理器，支持批量发送和错误重试
    Custom CloudWatch handler with batching and retry capabilities
    """

    def __init__(
        self,
        log_group_name: str,
        log_stream_name: str,
        batch_size: int = 20,
        flush_interval: float = 5.0,
        max_retries: int = 3
    ):
        super().__init__()
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries

        self.client = None
        self.sequence_token = None
        self.batch = []
        self.last_flush = time.time()
        self.lock = threading.Lock()

        # Initialize CloudWatch client
        self._init_client()

        # Setup periodic flush
        self._setup_timer()

    def _init_client(self):
        """初始化CloudWatch客户端 / Initialize CloudWatch client"""
        try:
            self.client = boto3.client('logs')

            # Ensure log group exists
            self._ensure_log_group_exists()

            # Create log stream if needed
            self._ensure_log_stream_exists()

            print(f"✅ CloudWatch handler initialized: {self.log_group_name}/{self.log_stream_name}")

        except (NoCredentialsError, ClientError) as e:
            print(f"⚠️  CloudWatch initialization failed: {e}", file=sys.stderr)
            self.client = None

    def _ensure_log_group_exists(self):
        """确保日志组存在 / Ensure log group exists"""
        try:
            self.client.create_log_group(logGroupName=self.log_group_name)
        except self.client.exceptions.ResourceAlreadyExistsException:
            pass  # Log group already exists
        except Exception as e:
            print(f"⚠️  Failed to create log group: {e}", file=sys.stderr)

    def _ensure_log_stream_exists(self):
        """确保日志流存在 / Ensure log stream exists"""
        try:
            response = self.client.describe_log_streams(
                logGroupName=self.log_group_name,
                logStreamNamePrefix=self.log_stream_name
            )

            existing_streams = response.get('logStreams', [])
            for stream in existing_streams:
                if stream['logStreamName'] == self.log_stream_name:
                    self.sequence_token = stream.get('uploadSequenceToken')
                    return

            # Create new log stream
            self.client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name
            )

        except Exception as e:
            print(f"⚠️  Failed to ensure log stream exists: {e}", file=sys.stderr)

    def _setup_timer(self):
        """设置定时刷新 / Setup periodic flush timer"""
        if self.client:
            timer = threading.Timer(self.flush_interval, self._periodic_flush)
            timer.daemon = True
            timer.start()

    def _periodic_flush(self):
        """定时刷新日志 / Periodic flush logs"""
        try:
            self.flush()
        except Exception as e:
            print(f"⚠️  Periodic flush failed: {e}", file=sys.stderr)
        finally:
            # Schedule next flush
            if self.client:
                timer = threading.Timer(self.flush_interval, self._periodic_flush)
                timer.daemon = True
                timer.start()

    def emit(self, record):
        """发送日志记录 / Emit log record"""
        if not self.client:
            return  # CloudWatch not available

        try:
            # Format log message
            log_message = self.format(record)

            # Add to batch
            with self.lock:
                self.batch.append({
                    'timestamp': int(record.created * 1000),
                    'message': log_message
                })

                # Flush if batch is full
                if len(self.batch) >= self.batch_size:
                    self._flush_batch()

        except Exception as e:
            print(f"⚠️  Failed to emit log: {e}", file=sys.stderr)

    def flush(self):
        """手动刷新缓冲区 / Manual flush buffer"""
        if self.client and self.batch:
            with self.lock:
                self._flush_batch()

    def _flush_batch(self):
        """刷新日志批次到CloudWatch / Flush batch to CloudWatch"""
        if not self.batch:
            return

        try:
            # Prepare log events
            log_events = sorted(self.batch, key=lambda x: x['timestamp'])

            # Send to CloudWatch
            params = {
                'logGroupName': self.log_group_name,
                'logStreamName': self.log_stream_name,
                'logEvents': log_events
            }

            if self.sequence_token:
                params['sequenceToken'] = self.sequence_token

            response = self.client.put_log_events(**params)

            # Update sequence token
            self.sequence_token = response.get('nextSequenceToken')

            # Clear batch
            self.batch.clear()
            self.last_flush = time.time()

        except Exception as e:
            print(f"⚠️  Failed to send batch to CloudWatch: {e}", file=sys.stderr)
            # Don't clear batch on failure, will retry

    def close(self):
        """关闭处理器 / Close handler"""
        self.flush()
        super().close()


class CloudWatchMiddleware:
    """
    FastAPI中间件，用于记录HTTP请求和响应
    FastAPI middleware for HTTP request/response logging
    """

    def __init__(self, app, logger_name: str = "fastapi"):
        self.app = app
        self.logger = logging.getLogger(logger_name)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        start_time = time.time()

        # Get request details
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client", ["unknown", 0])[0]
        user_agent = ""

        # Extract user agent from headers
        headers = dict(scope.get("headers", []))
        user_agent = headers.get(b"user-agent", b"").decode("utf-8", errors="ignore")

        # Generate request ID
        import uuid
        request_id = str(uuid.uuid4())[:8]

        # Log request
        self.logger.info(
            "HTTP_REQUEST",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client,
                "user_agent": user_agent,
                "event_type": "http_request"
            }
        )

        # Process request
        response_status = 500
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            self.logger.error(
                "HTTP_ERROR",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "event_type": "http_error"
                }
            )
            raise
        finally:
            # Send response with logging
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    response_status = message.get("status", 500)

                    # Log response
                    duration = (time.time() - start_time) * 1000
                    self.logger.info(
                        "HTTP_RESPONSE",
                        extra={
                            "request_id": request_id,
                            "method": method,
                            "path": path,
                            "status_code": response_status,
                            "duration_ms": round(duration, 2),
                            "event_type": "http_response"
                        }
                    )

                await send(message)

            # Replace send with wrapper
            original_send = send
            send = send_wrapper


def setup_logger(
    name: str = "geminiocr",
    level: str = "INFO",
    enable_cloudwatch: bool = None,
    log_group_name: str = None,
    log_stream_name: str = None
) -> logging.Logger:
    """
    设置统一的日志器 / Setup unified logger

    Args:
        name: 日志器名称 / Logger name
        level: 日志级别 / Log level
        enable_cloudwatch: 是否启用CloudWatch / Enable CloudWatch
        log_group_name: CloudWatch日志组名称 / Log group name
        log_stream_name: CloudWatch日志流名称 / Log stream name
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Check if we're in production
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    is_production = environment in ['production', 'staging']

    # Auto-detect CloudWatch availability
    if enable_cloudwatch is None:
        enable_cloudwatch = is_production and CLOUDWATCH_AVAILABLE

    # Console formatter
    if is_production:
        # JSON format for production
        console_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )
    else:
        # Human readable format for development
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # CloudWatch handler (production only)
    if enable_cloudwatch and CLOUDWATCH_AVAILABLE:
        if not log_group_name:
            log_group_name = f"/aws/ecs/geminiocr-{environment}"

        if not log_stream_name:
            import socket
            hostname = socket.gethostname()
            log_stream_name = f"{hostname}-backend-{int(time.time())}"

        # CloudWatch formatter (JSON)
        cloudwatch_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )

        cloudwatch_handler = CloudWatchHandler(
            log_group_name=log_group_name,
            log_stream_name=log_stream_name
        )
        cloudwatch_handler.setFormatter(cloudwatch_formatter)
        logger.addHandler(cloudwatch_handler)

        logger.info(f"CloudWatch logging enabled: {log_group_name}/{log_stream_name}")

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """获取日志器 / Get logger"""
    if name is None:
        name = "geminiocr"
    return logging.getLogger(name)


# Log configuration for different components
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "json",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "geminiocr": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "fastapi": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    }
}


# 初始化默认日志器 / Initialize default logger
default_logger = setup_logger()