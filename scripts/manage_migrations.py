#!/usr/bin/env python3
"""
Database Migration Manager for GeminiOCR
数据库迁移管理工具

支持的操作:
- 创建新迁移
- 应用迁移
- 回滚迁移
- 查看迁移状态
- 环境特定的迁移管理

Usage:
    # 创建新迁移
    python scripts/manage_migrations.py create --message "Add user table"
    
    # 应用所有迁移
    python scripts/manage_migrations.py upgrade
    
    # 应用到特定版本
    python scripts/manage_migrations.py upgrade --revision abc123
    
    # 回滚一个版本
    python scripts/manage_migrations.py downgrade
    
    # 回滚到特定版本
    python scripts/manage_migrations.py downgrade --revision def456
    
    # 查看当前状态
    python scripts/manage_migrations.py status
    
    # 查看迁移历史
    python scripts/manage_migrations.py history
    
    # 指定环境
    python scripts/manage_migrations.py --env production status
"""

import os
import sys
import argparse
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List

# 添加项目根目录和backend目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "GeminiOCR" / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from database_manager import DatabaseManager, switch_environment


class MigrationManager:
    """数据库迁移管理器"""
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv('DATABASE_ENV', 'local')
        self.alembic_cfg = project_root / "alembic.ini"
        
    def _run_alembic_command(self, command: List[str], env_vars: dict = None) -> int:
        """运行Alembic命令"""
        # 设置环境变量
        env = os.environ.copy()
        env['DATABASE_ENV'] = self.environment
        
        if env_vars:
            env.update(env_vars)
            
        # 构建完整命令
        full_command = ['alembic', '-c', str(self.alembic_cfg)] + command
        
        print(f"🔧 Running: {' '.join(full_command)}")
        print(f"📍 Environment: {self.environment}")
        
        try:
            result = subprocess.run(
                full_command,
                cwd=project_root,
                env=env,
                check=False,
                capture_output=False
            )
            return result.returncode
        except FileNotFoundError:
            print("❌ Alembic not found. Please install it: pip install alembic")
            return 1
        except Exception as e:
            print(f"❌ Command failed: {e}")
            return 1
    
    async def verify_connection(self) -> bool:
        """验证数据库连接"""
        try:
            print(f"🔍 Verifying connection to {self.environment} environment...")
            
            db_manager = DatabaseManager(self.environment)
            await db_manager.initialize()
            
            health = await db_manager.health_check()
            await db_manager.close()
            
            if health['status'] == 'healthy':
                print(f"✅ Database connection verified")
                return True
            else:
                print(f"❌ Database connection failed: {health.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Connection verification failed: {e}")
            return False
    
    def create_migration(self, message: str, autogenerate: bool = True) -> int:
        """创建新迁移"""
        command = ['revision']
        
        if autogenerate:
            command.append('--autogenerate')
            
        command.extend(['-m', message])
        
        # 添加环境信息到X参数
        command.extend(['-x', f'environment={self.environment}'])
        
        return self._run_alembic_command(command)
    
    def upgrade(self, revision: Optional[str] = None) -> int:
        """应用迁移"""
        command = ['upgrade']
        
        if revision:
            command.append(revision)
        else:
            command.append('head')
            
        return self._run_alembic_command(command)
    
    def downgrade(self, revision: Optional[str] = None) -> int:
        """回滚迁移"""
        command = ['downgrade']
        
        if revision:
            command.append(revision)
        else:
            command.append('-1')  # 回滚一个版本
            
        return self._run_alembic_command(command)
    
    def show_current(self) -> int:
        """显示当前版本"""
        return self._run_alembic_command(['current', '--verbose'])
    
    def show_history(self, limit: Optional[int] = None) -> int:
        """显示迁移历史"""
        command = ['history', '--verbose']
        
        if limit:
            command.extend(['-r', f'-{limit}:'])
            
        return self._run_alembic_command(command)
    
    def show_heads(self) -> int:
        """显示头版本"""
        return self._run_alembic_command(['heads', '--verbose'])
    
    def show_branches(self) -> int:
        """显示分支"""
        return self._run_alembic_command(['branches', '--verbose'])
    
    def check_migrations(self) -> int:
        """检查迁移状态"""
        print(f"📊 Migration Status for {self.environment} environment")
        print("=" * 50)
        
        # 显示当前版本
        print("📍 Current version:")
        result = self.show_current()
        if result != 0:
            return result
        
        print("\n🏷️ Available heads:")
        result = self.show_heads()
        if result != 0:
            return result
        
        print("\n📚 Recent migrations:")
        return self.show_history(limit=10)
    
    def stamp(self, revision: str) -> int:
        """标记数据库为特定版本（不运行迁移）"""
        print(f"⚠️  Warning: This will mark the database as version {revision} without running migrations")
        confirmation = input("Are you sure? (yes/no): ")
        
        if confirmation.lower() == 'yes':
            return self._run_alembic_command(['stamp', revision])
        else:
            print("❌ Operation cancelled")
            return 1
    
    def init_db(self) -> int:
        """初始化数据库（创建所有表）"""
        print(f"🏗️  Initializing database for {self.environment} environment...")
        
        # 首先标记为基础版本
        result = self._run_alembic_command(['stamp', 'base'])
        if result != 0:
            return result
        
        # 然后升级到最新版本
        return self.upgrade()
    
    def reset_db(self) -> int:
        """重置数据库（回滚所有迁移）"""
        print(f"⚠️  Warning: This will reset the database for {self.environment} environment")
        print("   All data will be lost!")
        
        if self.environment == 'production':
            print("❌ Database reset is not allowed in production environment")
            return 1
        
        confirmation = input("Are you sure? Type 'RESET' to confirm: ")
        
        if confirmation == 'RESET':
            return self.downgrade('base')
        else:
            print("❌ Operation cancelled")
            return 1
    
    def validate_schema(self) -> int:
        """验证schema一致性"""
        print(f"🔍 Validating schema for {self.environment} environment...")
        
        # 检查是否有待应用的迁移
        command = ['check']
        return self._run_alembic_command(command)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Database Migration Manager for GeminiOCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--env',
        choices=['local', 'sandbox', 'uat', 'production'],
        help="Database environment"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create migration
    create_parser = subparsers.add_parser('create', help='Create new migration')
    create_parser.add_argument('-m', '--message', required=True, help='Migration message')
    create_parser.add_argument('--manual', action='store_true', help='Create empty migration (no autogenerate)')
    
    # Upgrade
    upgrade_parser = subparsers.add_parser('upgrade', help='Apply migrations')
    upgrade_parser.add_argument('-r', '--revision', help='Target revision (default: head)')
    
    # Downgrade
    downgrade_parser = subparsers.add_parser('downgrade', help='Rollback migrations')
    downgrade_parser.add_argument('-r', '--revision', help='Target revision (default: -1)')
    
    # Status
    subparsers.add_parser('status', help='Show migration status')
    
    # History
    history_parser = subparsers.add_parser('history', help='Show migration history')
    history_parser.add_argument('-l', '--limit', type=int, help='Limit number of entries')
    
    # Current
    subparsers.add_parser('current', help='Show current version')
    
    # Heads
    subparsers.add_parser('heads', help='Show head versions')
    
    # Branches
    subparsers.add_parser('branches', help='Show branches')
    
    # Stamp
    stamp_parser = subparsers.add_parser('stamp', help='Mark database as specific version')
    stamp_parser.add_argument('revision', help='Target revision')
    
    # Init
    subparsers.add_parser('init', help='Initialize database')
    
    # Reset
    subparsers.add_parser('reset', help='Reset database (development only)')
    
    # Validate
    subparsers.add_parser('validate', help='Validate schema consistency')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 创建迁移管理器
    manager = MigrationManager(args.env)
    
    try:
        # 验证数据库连接
        if not await manager.verify_connection():
            print("❌ Cannot proceed without database connection")
            return 1
        
        # 执行命令
        if args.command == 'create':
            result = manager.create_migration(args.message, autogenerate=not args.manual)
        elif args.command == 'upgrade':
            result = manager.upgrade(args.revision)
        elif args.command == 'downgrade':
            result = manager.downgrade(args.revision)
        elif args.command == 'status':
            result = manager.check_migrations()
        elif args.command == 'history':
            result = manager.show_history(args.limit)
        elif args.command == 'current':
            result = manager.show_current()
        elif args.command == 'heads':
            result = manager.show_heads()
        elif args.command == 'branches':
            result = manager.show_branches()
        elif args.command == 'stamp':
            result = manager.stamp(args.revision)
        elif args.command == 'init':
            result = manager.init_db()
        elif args.command == 'reset':
            result = manager.reset_db()
        elif args.command == 'validate':
            result = manager.validate_schema()
        else:
            print(f"❌ Unknown command: {args.command}")
            result = 1
        
        if result == 0:
            print("✅ Operation completed successfully")
        else:
            print("❌ Operation failed")
        
        return result
        
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)