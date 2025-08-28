import os
import json
from typing import List, Optional

class Config:
    """安全的配置管理類"""
    
    def __init__(self):
        # 嘗試從環境變數加載，如果沒有則從 config.json 加載
        self._load_config()
    
    def _load_config(self):
        """加載配置，優先使用環境變數"""
        
        # API Keys - 支援多個 API key 用於負載均衡
        self.api_keys = self._get_api_keys()
        
        # Database
        self.database_url = os.getenv('DATABASE_URL') or self._get_from_config('database_url')
        
        # AWS Configuration
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID') or self._get_from_config('aws_access_key_id')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY') or self._get_from_config('aws_secret_access_key')
        self.aws_default_region = os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-1')
        self.aws_secret_name = os.getenv('AWS_SECRET_NAME') or self._get_from_config('aws_secret_name')
        
        # Application Configuration
        self.api_base_url = os.getenv('API_BASE_URL', '52.220.245.213')
        self.port = int(os.getenv('PORT', '8000'))
        self.model_name = os.getenv('MODEL_NAME', 'gemini-2.5-flash-preview-05-20')
        self.environment = os.getenv('ENVIRONMENT', 'development')
        
        # Document Types (from config.json)
        self.document_types = self._get_from_config('document_type', {})
    
    def _get_api_keys(self) -> List[str]:
        """獲取 API keys，支援環境變數和配置文件"""
        # 從環境變數獲取
        env_keys = []
        for i in range(1, 6):  # 支援最多5個API key
            key = os.getenv(f'GEMINI_API_KEY_{i}')
            if key:
                env_keys.append(key)
        
        if env_keys:
            return env_keys
        
        # 從配置文件獲取
        config_keys = self._get_from_config('api_keys', [])
        if isinstance(config_keys, list):
            return config_keys
        elif isinstance(config_keys, str):
            return [config_keys]
        
        # 舊格式支援
        single_key = self._get_from_config('api_key')
        if single_key:
            return [single_key]
        
        return []
    
    def _get_from_config(self, key: str, default=None):
        """從配置文件獲取值"""
        try:
            config_path = os.path.join("env", "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get(key, default)
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")
        return default
    
    def get_api_key(self, index: int = 0) -> Optional[str]:
        """獲取指定索引的 API key"""
        if 0 <= index < len(self.api_keys):
            return self.api_keys[index]
        return self.api_keys[0] if self.api_keys else None
    
    def get_next_api_key(self, current_index: int = 0) -> tuple[str, int]:
        """獲取下一個 API key（用於負載均衡）"""
        if not self.api_keys:
            return None, 0
        
        next_index = (current_index + 1) % len(self.api_keys)
        return self.api_keys[next_index], next_index
    
    def validate_config(self) -> List[str]:
        """驗證配置的完整性"""
        errors = []
        
        if not self.api_keys:
            errors.append("No Gemini API keys configured")
        
        if not self.database_url:
            errors.append("Database URL not configured")
        
        if self.environment == 'production':
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                errors.append("AWS credentials not configured for production")
        
        return errors

# 全域配置實例
config = Config()

# 驗證配置
config_errors = config.validate_config()
if config_errors:
    print("⚠️  Configuration warnings:")
    for error in config_errors:
        print(f"  - {error}")