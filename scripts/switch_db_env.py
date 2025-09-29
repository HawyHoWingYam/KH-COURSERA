#!/usr/bin/env python3
"""
Database Environment Switcher for GeminiOCR
数据库环境切换工具

Usage:
    python scripts/switch_db_env.py --env local
    python scripts/switch_db_env.py --env sandbox
    python scripts/switch_db_env.py --env uat  
    python scripts/switch_db_env.py --env production
    
    # 显示当前环境
    python scripts/switch_db_env.py --status
    
    # 测试连接
    python scripts/switch_db_env.py --test
    
    # 显示配置信息
    python scripts/switch_db_env.py --info
"""

import os
import sys
import argparse
import asyncio
import json
from pathlib import Path

# 添加项目根目录和backend目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "GeminiOCR" / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from database_manager import DatabaseManager, switch_environment, health_check


class DatabaseEnvironmentSwitcher:
    """数据库环境切换器"""
    
    SUPPORTED_ENVIRONMENTS = ['local', 'sandbox', 'uat', 'production']
    ENV_FILE = project_root / '.db_env'
    
    def __init__(self):
        self.current_env = self.get_current_environment()
        
    def get_current_environment(self) -> str:
        """获取当前环境"""
        # 1. 从环境变量获取
        env_var = os.getenv('DATABASE_ENV')
        if env_var:
            return env_var
            
        # 2. 从文件获取
        if self.ENV_FILE.exists():
            return self.ENV_FILE.read_text().strip()
            
        # 3. 默认值
        return 'local'
        
    def set_environment(self, environment: str):
        """设置环境"""
        if environment not in self.SUPPORTED_ENVIRONMENTS:
            raise ValueError(f"Unsupported environment: {environment}")
            
        # 写入文件
        self.ENV_FILE.write_text(environment)
        
        # 设置环境变量
        os.environ['DATABASE_ENV'] = environment
        
        self.current_env = environment
        print(f"✅ Database environment switched to: {environment}")
        
    async def test_connection(self, environment: str = None):
        """测试数据库连接"""
        env = environment or self.current_env
        
        try:
            print(f"🔍 Testing connection to {env} environment...")
            
            # 创建临时数据库管理器
            temp_manager = DatabaseManager(env)
            await temp_manager.initialize()
            
            # 健康检查
            health = await temp_manager.health_check()
            
            if health['status'] == 'healthy':
                print(f"✅ Connection successful!")
                print(f"   Environment: {health['environment']}")
                print(f"   Write latency: {health['write_latency_ms']}ms")
                if health['read_latency_ms']:
                    print(f"   Read latency: {health['read_latency_ms']}ms")
                    
                # 显示连接池信息
                pool_stats = health['pool_stats']
                print(f"   Write pool: {pool_stats['write_pool_size']} connections")
                if pool_stats['read_pool_size']:
                    print(f"   Read pool: {pool_stats['read_pool_size']} connections")
            else:
                print(f"❌ Connection failed: {health['error']}")
                return False
                
            await temp_manager.close()
            return True
            
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
            
    def show_status(self):
        """显示当前状态"""
        print(f"📊 Database Environment Status")
        print(f"   Current environment: {self.current_env}")
        print(f"   Supported environments: {', '.join(self.SUPPORTED_ENVIRONMENTS)}")
        print(f"   Environment file: {self.ENV_FILE}")
        print(f"   Environment variable: {os.getenv('DATABASE_ENV', 'Not set')}")
        
    async def show_info(self, environment: str = None):
        """显示环境信息"""
        env = environment or self.current_env
        
        try:
            config_path = project_root / "config" / "database" / f"{env}.yml"
            
            if not config_path.exists():
                print(f"❌ Configuration file not found: {config_path}")
                return
                
            print(f"📋 Database Configuration for {env} environment:")
            print(f"   Config file: {config_path}")
            
            # 创建数据库管理器来加载配置
            temp_manager = DatabaseManager(env)
            await temp_manager._load_config()
            
            config = temp_manager.config
            print(f"   Host: {config.host}")
            if config.readonly_host:
                print(f"   Read-only host: {config.readonly_host}")
            print(f"   Port: {config.port}")
            print(f"   Database: {config.database}")
            print(f"   Username: {config.username}")
            print(f"   SSL mode: {config.ssl_mode}")
            print(f"   Pool size: {config.pool_size}")
            print(f"   Max overflow: {config.max_overflow}")
            
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            
    def create_env_file_template(self):
        """创建环境文件模板"""
        template_path = project_root / '.env.template'
        
        template_content = f"""# Database Environment Configuration
# 复制此文件为 .env 并设置你的环境

# 数据库环境 (local, sandbox, uat, production)
DATABASE_ENV=local

# 本地开发数据库配置（示例）
LOCAL_DATABASE_URL=postgresql://hya_ocr_user:<password>@localhost:5432/hya_ocr_local

# AWS配置 (用于sandbox, uat, production环境)
AWS_DEFAULT_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=<your_access_key>
AWS_SECRET_ACCESS_KEY=<your_secret_key>

# Aurora连接信息 (由Terraform输出提供)
AURORA_WRITER_ENDPOINT=
AURORA_READER_ENDPOINT=
DATABASE_USERNAME=
DATABASE_PASSWORD=
DATABASE_SECRET_ARN=

# 开发者IP (用于sandbox环境访问)
DEVELOPER_IP_CIDR=
"""
        
        template_path.write_text(template_content)
        print(f"✅ Environment template created: {template_path}")
        print("   Please copy it to .env and configure your settings")
        
    def list_environments(self):
        """列出所有环境及其状态"""
        print("🌍 Available Database Environments:")
        
        for env in self.SUPPORTED_ENVIRONMENTS:
            config_path = project_root / "config" / "database" / f"{env}.yml"
            status = "✅ Configured" if config_path.exists() else "❌ Not configured"
            current = " (current)" if env == self.current_env else ""
            print(f"   {env}: {status}{current}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Database Environment Switcher for GeminiOCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--env', 
        choices=['local', 'sandbox', 'uat', 'production'],
        help="Switch to specified environment"
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help="Show current environment status"
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help="Test database connection"
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help="Show environment configuration info"
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help="List all available environments"
    )
    
    parser.add_argument(
        '--template',
        action='store_true',
        help="Create environment file template"
    )
    
    args = parser.parse_args()
    
    switcher = DatabaseEnvironmentSwitcher()
    
    try:
        if args.env:
            switcher.set_environment(args.env)
            # 测试新环境的连接
            success = await switcher.test_connection()
            if not success:
                print("⚠️  Environment switched but connection test failed")
                print("   Please check your configuration")
                
        elif args.status:
            switcher.show_status()
            
        elif args.test:
            await switcher.test_connection()
            
        elif args.info:
            await switcher.show_info()
            
        elif args.list:
            switcher.list_environments()
            
        elif args.template:
            switcher.create_env_file_template()
            
        else:
            # 默认显示状态
            switcher.show_status()
            print("\nUse --help for more options")
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
