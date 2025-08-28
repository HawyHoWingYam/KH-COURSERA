from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
import urllib.parse
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_database_url() -> str:
    """
    獲取數據庫 URL
    優先級：環境變量 > AWS Secrets Manager > 配置文件
    """
    try:
        # 首先嘗試從配置加載器獲取
        from config_loader import config_loader
        return config_loader.get_database_url()
    except ImportError:
        logger.warning("Config loader not available, using fallback method")
        return _fallback_get_database_url()
    except Exception as e:
        logger.error(f"Failed to get database URL from config loader: {e}")
        return _fallback_get_database_url()

def _fallback_get_database_url() -> str:
    """備用方法：直接從環境變量或配置文件獲取數據庫 URL"""
    # 優先從環境變量獲取
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        logger.info("Using database URL from environment variable")
        return _encode_database_url(database_url)
    
    # 回退到配置文件
    config_paths = [
        'env/config.json',
        os.path.join(os.path.dirname(__file__), '..', 'env', 'config.json')
    ]
    
    for config_path in config_paths:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    database_url = config.get('database_url')
                    if database_url and not database_url.startswith('REPLACE_WITH_ENV_VAR'):
                        logger.warning("Using database URL from config file (fallback)")
                        return _encode_database_url(database_url)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read config file {config_path}: {e}")
            continue
    
    raise ValueError("Database URL not found in environment variables or config file")

def _encode_database_url(database_url: str) -> str:
    """編碼數據庫 URL 中的特殊字符"""
    try:
        # 解析 URL 以處理特殊字符
        parts = database_url.split('@')
        if len(parts) == 2:
            auth_part = parts[0]
            host_part = parts[1]
            
            # 提取用戶名和密碼
            auth_parts = auth_part.split('://', 1)[1].split(':', 1)
            if len(auth_parts) == 2:
                username = auth_parts[0]
                password = auth_parts[1]
                
                # URL 編碼密碼以處理特殊字符
                encoded_password = urllib.parse.quote_plus(password)
                
                # 重構 URL
                protocol = auth_part.split('://', 1)[0]
                return f"{protocol}://{username}:{encoded_password}@{host_part}"
        
        return database_url
    except Exception as e:
        logger.warning(f"Could not encode database URL: {e}")
        return database_url

def create_database_engine():
    """創建數據庫引擎"""
    try:
        database_url = get_database_url()
        
        # 創建引擎，添加連接池和重試機制
        engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 30,
                "application_name": "GeminiOCR_Backend"
            }
        )
        
        logger.info("✅ Database connection established successfully")
        return engine
        
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        raise

# 創建數據庫引擎
try:
    engine = create_database_engine()
except Exception as e:
    logger.critical(f"Cannot initialize database: {e}")
    # 在開發環境中，可能需要延遲初始化
    engine = None

# 創建會話工廠
if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None

# 定義 Base 類用於模型繼承
Base = declarative_base()

# 依賴注入函數：獲取 DB 會話
def get_db():
    """獲取數據庫會話"""
    global engine, SessionLocal
    
    if not SessionLocal:
        # 嘗試延遲初始化
        engine = create_database_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_database_info() -> dict:
    """獲取數據庫信息"""
    try:
        database_url = get_database_url()
        # 隱藏敏感信息
        safe_url = database_url.split('@')[1] if '@' in database_url else "unknown"
        return {
            "status": "connected" if engine else "disconnected",
            "host": safe_url,
            "pool_size": engine.pool.size() if engine else 0,
            "checked_in": engine.pool.checkedin() if engine else 0,
            "checked_out": engine.pool.checkedout() if engine else 0
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
