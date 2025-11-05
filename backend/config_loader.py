"""
集中配置加載模塊
優先級：環境變量 > AWS Secrets Manager > 配置文件
"""

import os
import json
import boto3
import logging
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# 加載 .env 文件 - 支持按環境加載 (優先級: .env.<ENV> -> .env)
env_name = os.getenv("ENVIRONMENT") or os.getenv("DATABASE_ENV")
candidate_paths = []
if env_name:
    candidate_paths.extend([
        # Centralized project env directory (primary location)
        os.path.join(os.path.dirname(__file__), "..", "..", "env", f".env.{env_name}"),
        # Project root env directory (when running from project root)
        os.path.join("env", f".env.{env_name}"),
        # Legacy backend env directory (fallback)
        os.path.join(os.path.dirname(__file__), "env", f".env.{env_name}"),
        # Dotfile next to CWD (legacy)
        f".env.{env_name}",
    ])

# 回退到通用 .env
candidate_paths.extend([
    # Centralized project env directory (primary location)
    os.path.join(os.path.dirname(__file__), "..", "..", "env", ".env"),
    # Project root env directory
    os.path.join("env", ".env"),
    # Legacy backend env directory (fallback)
    os.path.join(os.path.dirname(__file__), "env", ".env"),
    # Dotfile next to CWD (legacy)
    ".env",
])

for env_path in candidate_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ 加載環境變量文件: {env_path}")
        break
else:
    print("⚠️  未找到 .env 文件，使用系統環境變量")

logger = logging.getLogger(__name__)


class ConfigLoader:
    """集中配置加載器"""

    def __init__(self):
        self._secrets_cache = {}
        self._config_file_cache = None
        self._aws_client = None

    def get_database_url(self) -> str:
        """獲取數據庫連接URL"""
        # 優先級：環境變量 > AWS Secrets > 配置文件
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            logger.info("Using database URL from environment variable")
            return database_url

        # 嘗試從 AWS Secrets Manager 獲取
        secret = self._get_aws_secret("database")
        if secret and "database_url" in secret:
            logger.info("Using database URL from AWS Secrets Manager")
            return secret["database_url"]

        # 回退到配置文件
        config = self._get_config_file()
        if config and "database_url" in config:
            logger.warning("Using database URL from config file (fallback)")
            return config["database_url"]

        raise ValueError(
            "Database URL not found in environment variables, AWS Secrets, or config file"
        )

    def get_gemini_api_keys(self) -> List[str]:
        """獲取 Gemini API 密鑰列表"""
        api_keys = []

        # 從環境變量獲取多個 API keys
        for i in range(1, 10):  # 支援最多9個 API key
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                api_keys.append(key)

        if api_keys:
            logger.info(
                f"Using {len(api_keys)} Gemini API keys from environment variables"
            )
            return api_keys

        # 單個 API key 環境變量（向後兼容）
        single_key = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
        if single_key:
            logger.info("Using single Gemini API key from environment variable")
            return [single_key]

        # 從 AWS Secrets Manager 獲取
        secret = self._get_aws_secret("gemini")
        if secret:
            if "api_keys" in secret and isinstance(secret["api_keys"], list):
                logger.info(
                    f"Using {len(secret['api_keys'])} Gemini API keys from AWS Secrets"
                )
                return secret["api_keys"]
            elif "api_key" in secret:
                logger.info("Using single Gemini API key from AWS Secrets")
                return [secret["api_key"]]

        # 回退到配置文件
        config = self._get_config_file()
        if config:
            if "api_keys" in config and isinstance(config["api_keys"], list):
                logger.warning(
                    f"Using {len(config['api_keys'])} Gemini API keys from config file (fallback)"
                )
                return config["api_keys"]
            elif "api_key" in config:
                logger.warning(
                    "Using single Gemini API key from config file (fallback)"
                )
                return [config["api_key"]]

        # 在測試環境下允許無 API key 運行
        if os.getenv("ENVIRONMENT") == "test":
            logger.warning("Running in test mode without Gemini API keys")
            return ["test-api-key-mock"]

        raise ValueError(
            "No Gemini API keys found in environment variables, AWS Secrets, or config file"
        )

    def get_aws_credentials(self) -> Dict[str, str]:
        """獲取 AWS 憑證"""
        credentials = {}

        # 從環境變量獲取
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1")
        aws_secret_name = os.getenv("AWS_SECRET_NAME")

        if aws_access_key and aws_secret_key:
            logger.info("Using AWS credentials from environment variables")
            return {
                "aws_access_key_id": aws_access_key,
                "aws_secret_access_key": aws_secret_key,
                "aws_default_region": aws_region,
                "aws_secret_name": aws_secret_name,
            }

        # 回退到配置文件
        config = self._get_config_file()
        if config:
            for key in [
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_default_region",
                "aws_secret_name",
            ]:
                if key in config:
                    credentials[key] = config[key]

            if credentials.get("aws_access_key_id") and credentials.get(
                "aws_secret_access_key"
            ):
                logger.warning("Using AWS credentials from config file (fallback)")
                return credentials

        logger.warning("No AWS credentials found, using default boto3 credential chain")
        return {"aws_default_region": aws_region or "ap-southeast-1"}

    def get_app_config(self) -> Dict[str, Any]:
        """獲取應用配置"""
        return {
            "api_base_url": os.getenv(
                "API_BASE_URL", self._get_from_config("API_BASE_URL", "localhost")
            ),
            "port": int(os.getenv("PORT", self._get_from_config("port", 8000))),
            "model_name": os.getenv(
                "MODEL_NAME",
                self._get_from_config("model_name", "gemini-2.5-flash-preview-05-20"),
            ),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "document_types": self._get_from_config("document_type", {}),
        }

    def get_prompt_schema_config(self) -> Dict[str, Any]:
        """獲取prompt和schema管理配置"""
        default_config = {
            "storage_backend": "auto",
            "cache": {
                "enabled": True,
                "max_size": 100,
                "ttl_minutes": 30
            },
            "s3": {
                "enabled": True,
                "bucket_name": None,
                "region": "ap-southeast-1",
                "prompt_prefix": "prompts/",
                "schema_prefix": "schemas/",
                "auto_backup": True,
                "encryption": True
            },
            "local_backup": {
                "enabled": True,
                "path": "uploads/prompt_schema_backup",
                "auto_sync": True
            },
            "validation": {
                "strict_mode": True,
                "prompt_min_length": 10,
                "prompt_max_length": 50000,
                "required_prompt_keywords": ["extract", "analyze", "identify", "process"],
                "schema_required_fields": ["type", "properties"]
            },
            "performance": {
                "thread_pool_size": 4,
                "concurrent_uploads": 3,
                "retry_attempts": 3,
                "timeout_seconds": 30
            }
        }

        # 從配置文件加載
        config_data = self._get_from_config("prompt_schema_management", default_config)

        # 環境變量覆蓋
        if os.getenv("PROMPT_SCHEMA_STORAGE_BACKEND"):
            config_data["storage_backend"] = os.getenv("PROMPT_SCHEMA_STORAGE_BACKEND")

        if os.getenv("PROMPT_SCHEMA_CACHE_ENABLED"):
            config_data["cache"]["enabled"] = os.getenv("PROMPT_SCHEMA_CACHE_ENABLED").lower() == "true"

        if os.getenv("PROMPT_SCHEMA_CACHE_SIZE"):
            config_data["cache"]["max_size"] = int(os.getenv("PROMPT_SCHEMA_CACHE_SIZE"))

        if os.getenv("PROMPT_SCHEMA_S3_ENABLED"):
            config_data["s3"]["enabled"] = os.getenv("PROMPT_SCHEMA_S3_ENABLED").lower() == "true"

        if os.getenv("PROMPT_SCHEMA_S3_BUCKET"):
            config_data["s3"]["bucket_name"] = os.getenv("PROMPT_SCHEMA_S3_BUCKET")

        if os.getenv("PROMPT_SCHEMA_LOCAL_BACKUP_PATH"):
            config_data["local_backup"]["path"] = os.getenv("PROMPT_SCHEMA_LOCAL_BACKUP_PATH")

        # 如果沒有明確設置bucket_name，使用主S3配置的bucket
        if not config_data["s3"]["bucket_name"]:
            config_data["s3"]["bucket_name"] = os.getenv("S3_BUCKET_NAME")

        # 如果storage_backend是auto，根據S3可用性自動決定
        if config_data["storage_backend"] == "auto":
            config_data["storage_backend"] = "s3" if (
                config_data["s3"]["enabled"] and 
                config_data["s3"]["bucket_name"] and 
                os.getenv("S3_BUCKET_NAME")
            ) else "local"

        return config_data

    def _get_aws_secret(self, secret_type: str) -> Optional[Dict[str, Any]]:
        """從 AWS Secrets Manager 獲取機密"""
        if secret_type in self._secrets_cache:
            return self._secrets_cache[secret_type]

        try:
            if not self._aws_client:
                aws_creds = self.get_aws_credentials()
                if (
                    "aws_access_key_id" in aws_creds
                    and "aws_secret_access_key" in aws_creds
                ):
                    self._aws_client = boto3.client(
                        "secretsmanager",
                        region_name=aws_creds.get(
                            "aws_default_region", "ap-southeast-1"
                        ),
                        aws_access_key_id=aws_creds["aws_access_key_id"],
                        aws_secret_access_key=aws_creds["aws_secret_access_key"],
                    )
                else:
                    # 使用默認憑證鏈
                    self._aws_client = boto3.client(
                        "secretsmanager",
                        region_name=aws_creds.get(
                            "aws_default_region", "ap-southeast-1"
                        ),
                    )

            # 根據 secret_type 決定 secret 名稱
            secret_name_map = {
                "database": os.getenv("DATABASE_SECRET_NAME", "prod/database"),
                "gemini": os.getenv("GEMINI_SECRET_NAME", "prod/gemini"),
                "default": os.getenv("AWS_SECRET_NAME"),
            }

            secret_name = secret_name_map.get(secret_type, secret_name_map["default"])
            if not secret_name:
                return None

            response = self._aws_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])
            self._secrets_cache[secret_type] = secret_data
            return secret_data

        except (ClientError, NoCredentialsError, json.JSONDecodeError) as e:
            logger.warning(f"Could not retrieve AWS secret for {secret_type}: {e}")
            return None

    def _get_config_file(self) -> Optional[Dict[str, Any]]:
        """從配置文件獲取配置"""
        if self._config_file_cache is not None:
            return self._config_file_cache

        config_paths = [
            # Centralized project env directory (primary location)
            os.path.join(os.path.dirname(__file__), "..", "..", "env", "config.json"),
            # Project root env directory
            os.path.join("env", "config.json"),
            # Legacy backend env directory (fallback)
            os.path.join(os.path.dirname(__file__), "env", "config.json"),
            # Current directory (legacy)
            "config.json",
        ]

        for config_path in config_paths:
            try:
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        self._config_file_cache = json.load(f)
                        return self._config_file_cache
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not read config file {config_path}: {e}")
                continue

        logger.warning("No config file found")
        self._config_file_cache = {}
        return self._config_file_cache

    def _get_from_config(self, key: str, default=None) -> Any:
        """從配置文件獲取特定值"""
        config = self._get_config_file()
        return config.get(key, default) if config else default

    def validate_configuration(self) -> List[str]:
        """驗證配置的完整性"""
        errors = []

        try:
            # 檢查數據庫配置
            self.get_database_url()
        except ValueError as e:
            errors.append(f"Database configuration: {e}")

        try:
            # 檢查 Gemini API keys
            api_keys = self.get_gemini_api_keys()
            if not api_keys:
                errors.append("No Gemini API keys configured")
        except ValueError as e:
            errors.append(f"Gemini API configuration: {e}")

        # 檢查應用配置
        app_config = self.get_app_config()
        if not app_config.get("port"):
            errors.append("Application port not configured")

        return errors


# 全局配置實例
config_loader = ConfigLoader()


# API Key 管理類
class APIKeyManager:
    """API Key 輪換管理器"""

    def __init__(self):
        self.api_keys = config_loader.get_gemini_api_keys()
        self.current_index = 0
        self.usage_count = {}

        # 初始化使用計數
        for i, key in enumerate(self.api_keys):
            self.usage_count[i] = 0

    def get_current_key(self) -> str:
        """獲取當前 API key"""
        if not self.api_keys:
            raise ValueError("No API keys available")
        return self.api_keys[self.current_index]

    def get_next_key(self) -> str:
        """獲取下一個 API key（輪換）"""
        if not self.api_keys:
            raise ValueError("No API keys available")

        self.current_index = (self.current_index + 1) % len(self.api_keys)
        self.usage_count[self.current_index] += 1
        return self.api_keys[self.current_index]

    def get_least_used_key(self) -> str:
        """獲取使用次數最少的 API key"""
        if not self.api_keys:
            raise ValueError("No API keys available")

        # 找到使用次數最少的 key
        min_usage = min(self.usage_count.values())
        for index, usage in self.usage_count.items():
            if usage == min_usage:
                self.current_index = index
                self.usage_count[index] += 1
                return self.api_keys[index]

    def mark_key_error(self, key: str):
        """標記 API key 出現錯誤"""
        try:
            key_index = self.api_keys.index(key)
            # 增加錯誤權重，降低該 key 的優先級
            self.usage_count[key_index] += 10
            logger.warning(
                f"API key {key_index} marked with error, usage count increased"
            )
        except ValueError:
            logger.warning(f"API key not found in list: {key[:10]}...")

    def mark_key_invalid(self, key: str):
        """將無效的 API key 快速降級，避免再次選用。

        將其 usage 設為當前最⼤值+1000，實現強烈的降權效果。
        """
        try:
            key_index = self.api_keys.index(key)
            max_usage = max(self.usage_count.values()) if self.usage_count else 0
            self.usage_count[key_index] = max_usage + 1000
            logger.warning(
                f"API key {key_index} marked INVALID; deprioritized with usage={self.usage_count[key_index]}"
            )
        except ValueError:
            logger.warning(f"API key not found in list: {key[:10]}...")

    def get_usage_stats(self) -> Dict[int, int]:
        """獲取使用統計"""
        return self.usage_count.copy()


# 全局 API Key 管理器 (延遲初始化)
api_key_manager = None

def get_api_key_manager():
    """獲取 API Key 管理器 (延遲初始化)"""
    global api_key_manager
    if api_key_manager is None:
        api_key_manager = APIKeyManager()
    return api_key_manager


# 驗證配置
def validate_and_log_config():
    """驗證並記錄配置狀態"""
    errors = config_loader.validate_configuration()
    if errors:
        logger.warning("⚠️  Configuration issues found:")
        for error in errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("✅ Configuration validation passed")

    # 記錄配置來源
    app_config = config_loader.get_app_config()
    logger.info("🔧 Configuration loaded:")
    logger.info(f"  - API Base URL: {app_config['api_base_url']}")
    logger.info(f"  - Port: {app_config['port']}")
    logger.info(f"  - Model: {app_config['model_name']}")
    logger.info(f"  - Environment: {app_config['environment']}")
    logger.info(
        f"  - Gemini API Keys: {len(config_loader.get_gemini_api_keys())} configured"
    )


if __name__ == "__main__":
    validate_and_log_config()
