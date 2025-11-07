"""
集中配置加載模組（嚴格環境變數版）
— 僅從 backend.env/系統環境讀取；不再從 AWS Secrets 或 config.json 提供隱式預設/回退。

原則：
- 唯一配置來源：backend.env（或同名環境變數）；代碼內不提供默認值。
- 缺失關鍵變數時，及早報錯（啟動時可見），避免靜默回退。
"""

import os
import json
import boto3
import logging
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

backend_dir = os.path.dirname(__file__)
env_path = os.path.join(backend_dir, "backend.env")

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"✅ 加載環境變量文件: {env_path}")
else:
    print("⚠️  未找到 backend.env，將僅使用當前進程環境變量")

logger = logging.getLogger(__name__)


class ConfigLoader:
    """集中配置加載器"""

    def __init__(self):
        self._secrets_cache = {}
        self._config_file_cache = None
        self._aws_client = None

    def _require_env(self, name: str) -> str:
        value = os.getenv(name)
        if value is None or str(value).strip() == "":
            raise ValueError(f"Missing required environment variable: {name}")
        return value

    def get_database_url(self) -> str:
        """獲取數據庫連接URL（僅來源於環境變數）"""
        database_url = self._require_env("DATABASE_URL")
        logger.info("Using database URL from environment variable")
        return database_url

    def get_gemini_api_keys(self) -> List[str]:
        """獲取 Gemini API 密鑰列表（僅來源於環境變數）"""
        api_keys: List[str] = []
        for i in range(1, 10):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key and key.strip():
                api_keys.append(key.strip())
        # 單一鍵位於 GEMINI_API_KEY 亦接受
        single = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
        if single and single.strip():
            api_keys.append(single.strip())

        if not api_keys:
            raise ValueError("No Gemini API keys configured in environment (GEMINI_API_KEY_* or GEMINI_API_KEY)")

        logger.info(f"Using {len(api_keys)} Gemini API keys from environment variables")
        return api_keys

    def get_aws_credentials(self) -> Dict[str, str]:
        """獲取 AWS 憑證（僅環境變數；需要時必須存在）"""
        region = self._require_env("AWS_DEFAULT_REGION")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        # 有些環境可能走 IAM role；若設置了 STORAGE_BACKEND=s3 則必須顯式提供 Key/Secret
        storage_backend = os.getenv("STORAGE_BACKEND", "").lower()
        if storage_backend == "s3":
            if not access_key or not secret_key:
                raise ValueError("When STORAGE_BACKEND=s3, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in environment")
        creds: Dict[str, str] = {"aws_default_region": region}
        if access_key:
            creds["aws_access_key_id"] = access_key
        if secret_key:
            creds["aws_secret_access_key"] = secret_key
        return creds

    def get_app_config(self) -> Dict[str, Any]:
        """獲取應用配置（僅環境變數）"""
        api_base_url = self._require_env("API_BASE_URL")
        port_str = self._require_env("PORT")
        model_name = self._require_env("MODEL_NAME")
        environment = self._require_env("ENVIRONMENT")
        try:
            port = int(port_str)
        except Exception:
            raise ValueError("PORT must be an integer")
        return {
            "api_base_url": api_base_url,
            "port": port,
            "model_name": model_name,
            "environment": environment,
        }

    def get_prompt_schema_config(self) -> Dict[str, Any]:
        """獲取 prompt/schema 管理配置（僅環境變數）。
        最小化需求：強制聲明後端與必要參數，不做自動推斷。
        """
        storage_backend = self._require_env("STORAGE_BACKEND").lower()
        cfg: Dict[str, Any] = {
            "storage_backend": storage_backend,
            "cache": {},
            "s3": {},
            "local_backup": {},
            "validation": {},
            "performance": {},
        }

        # 可選：緩存與備份參數（如提供則使用，否則由上層模組自行處理默認或不啟用）
        if os.getenv("PROMPT_SCHEMA_CACHE_ENABLED") is not None:
            cfg.setdefault("cache", {})["enabled"] = os.getenv("PROMPT_SCHEMA_CACHE_ENABLED").lower() == "true"
        if os.getenv("PROMPT_SCHEMA_CACHE_SIZE"):
            cfg.setdefault("cache", {})["max_size"] = int(os.getenv("PROMPT_SCHEMA_CACHE_SIZE"))
        if os.getenv("PROMPT_SCHEMA_LOCAL_BACKUP_PATH"):
            cfg.setdefault("local_backup", {})["path"] = os.getenv("PROMPT_SCHEMA_LOCAL_BACKUP_PATH")

        if storage_backend == "s3":
            # 明確要求 S3 參數
            cfg.setdefault("s3", {})["bucket_name"] = self._require_env("S3_BUCKET_NAME")
            cfg["s3"]["region"] = self._require_env("AWS_DEFAULT_REGION")

        return cfg

    def _get_aws_secret(self, secret_type: str) -> Optional[Dict[str, Any]]:
        """（禁用）不再從 Secrets 提供回退，保持兼容接口但恒返 None。"""
        return None

    def _get_config_file(self) -> Optional[Dict[str, Any]]:
        """（禁用）不再使用 config.json 作為回退。"""
        return {}

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

        # 檢查應用配置與運營參數（嚴格模式）
        try:
            app_config = self.get_app_config()
        except Exception as e:
            errors.append(f"Application configuration: {e}")

        # 存儲後端校驗
        storage_backend = os.getenv("STORAGE_BACKEND")
        if not storage_backend:
            errors.append("Missing STORAGE_BACKEND (expected 's3' or 'local')")
        else:
            sb = storage_backend.lower()
            if sb not in ("s3", "local"):
                errors.append("STORAGE_BACKEND must be 's3' or 'local'")
            if sb == "s3":
                if not os.getenv("S3_BUCKET_NAME"):
                    errors.append("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3")
                for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"):
                    if not os.getenv(name):
                        errors.append(f"{name} is required when STORAGE_BACKEND=s3")
            if sb == "local":
                if not os.getenv("LOCAL_UPLOAD_DIR"):
                    errors.append("LOCAL_UPLOAD_DIR is required when STORAGE_BACKEND=local")

        # OneDrive 開關與必填
        onedrive_enabled = os.getenv("ONEDRIVE_SYNC_ENABLED")
        if onedrive_enabled is None:
            errors.append("Missing ONEDRIVE_SYNC_ENABLED (expected 'true' to enable)")
        elif onedrive_enabled.lower() == "true":
            for name in ("ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET", "ONEDRIVE_TENANT_ID", "ONEDRIVE_TARGET_USER_UPN"):
                if not os.getenv(name):
                    errors.append(f"{name} is required when ONEDRIVE_SYNC_ENABLED=true")

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
