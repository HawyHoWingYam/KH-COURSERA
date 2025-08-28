#!/usr/bin/env python3
"""
配置系統測試腳本
"""

import os
import sys
import json
import logging

# 添加當前目錄到Python路徑
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_loading():
    """測試配置加載功能"""
    print("🔧 測試配置系統...")
    
    try:
        from config_loader import config_loader, api_key_manager, validate_and_log_config
        print("✅ 配置加載器導入成功")
    except ImportError as e:
        print(f"❌ 配置加載器導入失敗: {e}")
        return False
    
    # 測試配置驗證
    print("\n📋 驗證配置...")
    try:
        validate_and_log_config()
        print("✅ 配置驗證完成")
    except Exception as e:
        print(f"⚠️  配置驗證警告: {e}")
    
    # 測試數據庫配置
    print("\n💾 測試數據庫配置...")
    try:
        database_url = config_loader.get_database_url()
        print(f"✅ 數據庫URL獲取成功: {database_url[:20]}...")
    except Exception as e:
        print(f"❌ 數據庫配置錯誤: {e}")
    
    # 測試API keys
    print("\n🔑 測試API keys...")
    try:
        api_keys = config_loader.get_gemini_api_keys()
        print(f"✅ API keys獲取成功: {len(api_keys)} 個key")
        
        # 測試API key管理器
        current_key = api_key_manager.get_current_key()
        print(f"✅ 當前API key: {current_key[:10]}...")
        
        next_key = api_key_manager.get_next_key()
        print(f"✅ 下一個API key: {next_key[:10]}...")
        
        stats = api_key_manager.get_usage_stats()
        print(f"✅ 使用統計: {stats}")
        
    except Exception as e:
        print(f"❌ API keys配置錯誤: {e}")
    
    # 測試應用配置
    print("\n⚙️ 測試應用配置...")
    try:
        app_config = config_loader.get_app_config()
        print(f"✅ 應用配置獲取成功:")
        print(f"   - API Base URL: {app_config['api_base_url']}")
        print(f"   - Port: {app_config['port']}")
        print(f"   - Model: {app_config['model_name']}")
        print(f"   - Environment: {app_config['environment']}")
    except Exception as e:
        print(f"❌ 應用配置錯誤: {e}")
    
    return True

def test_database_connection():
    """測試數據庫連接"""
    print("\n🗄️  測試數據庫連接...")
    
    try:
        from db.database import test_database_connection, get_database_info
        
        # 測試連接
        if test_database_connection():
            print("✅ 數據庫連接測試通過")
            
            # 獲取數據庫信息
            db_info = get_database_info()
            print(f"✅ 數據庫信息: {db_info}")
        else:
            print("❌ 數據庫連接測試失敗")
            
    except Exception as e:
        print(f"❌ 數據庫測試錯誤: {e}")

def test_main_functions():
    """測試main.py中的功能"""
    print("\n🧠 測試main.py功能...")
    
    try:
        from main import get_api_key_and_model, configure_gemini_with_retry
        
        # 測試API key獲取
        api_key, model_name = get_api_key_and_model()
        print(f"✅ API key和模型獲取成功: {model_name}")
        
        # 測試Gemini配置
        configure_gemini_with_retry(api_key)
        print("✅ Gemini API配置成功")
        
    except Exception as e:
        print(f"❌ main.py功能測試錯誤: {e}")

def show_environment_status():
    """顯示環境變量狀態"""
    print("\n🌍 環境變量狀態:")
    
    env_vars = [
        'DATABASE_URL',
        'GEMINI_API_KEY_1',
        'GEMINI_API_KEY_2',
        'GEMINI_API_KEY',
        'API_KEY',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'API_BASE_URL',
        'PORT',
        'MODEL_NAME',
        'ENVIRONMENT'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # 隱藏敏感信息
            if 'key' in var.lower() or 'secret' in var.lower() or 'url' in var.lower():
                display_value = f"{value[:10]}..." if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: 未設置")

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 GeminiOCR 配置系統測試")
    print("=" * 60)
    
    # 顯示環境狀態
    show_environment_status()
    
    # 測試配置加載
    test_config_loading()
    
    # 測試數據庫
    test_database_connection()
    
    # 測試main函數
    test_main_functions()
    
    print("\n" + "=" * 60)
    print("🎉 測試完成!")
    print("=" * 60)