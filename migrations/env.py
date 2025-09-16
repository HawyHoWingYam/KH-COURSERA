"""
Alembic Environment Configuration for GeminiOCR
支持多环境数据库迁移管理，集成DatabaseManager
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 添加项目根目录和backend目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "GeminiOCR" / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

# 导入数据库管理器和模型
from database_manager import DatabaseManager
from db.models import Base  # 确保导入所有模型

# Alembic配置对象
config = context.config

# 如果存在日志配置，设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata


def get_database_url():
    """获取数据库URL"""
    # 1. 优先使用命令行参数或环境变量中的URL
    url = config.get_main_option("sqlalchemy.url")
    if url and url != "":
        return url
    
    # 2. 从环境变量获取
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    
    # 3. 根据当前环境构建URL
    environment = os.getenv('DATABASE_ENV', 'local')
    
    if environment == 'local':
        # Build from environment variables; do not hardcode local credentials
        host = os.getenv('DATABASE_HOST', 'localhost')
        port = os.getenv('DATABASE_PORT', '5432')
        database = os.getenv('POSTGRES_DB') or os.getenv('DATABASE_NAME', 'hya_ocr_local')
        username = os.getenv('POSTGRES_USER') or os.getenv('DATABASE_USERNAME', 'hya_ocr_user')
        password = os.getenv('POSTGRES_PASSWORD') or os.getenv('DATABASE_PASSWORD', '')

        if not password:
            raise ValueError(
                "Database password not found for local environment. Set POSTGRES_PASSWORD or DATABASE_PASSWORD."
            )

        safe_password = quote_plus(password)
        return f"postgresql://{username}:{safe_password}@{host}:{port}/{database}"
    
    # 对于AWS环境，需要从DatabaseManager获取配置
    # 这是同步函数，所以我们使用基本的环境变量
    host = os.getenv('AURORA_WRITER_ENDPOINT', 'localhost')
    port = os.getenv('DATABASE_PORT', '5432')
    database = os.getenv('DATABASE_NAME', 'hya_ocr')
    username = os.getenv('DATABASE_USERNAME', 'hya_ocr_admin')
    password = os.getenv('DATABASE_PASSWORD', '')
    
    if not password:
        raise ValueError(f"Database password not found for environment: {environment}")
    
    # URL encode password to handle special characters
    safe_password = quote_plus(password)
    return f"postgresql://{username}:{safe_password}@{host}:{port}/{database}"


def include_object(object, name, type_, reflected, compare_to):
    """
    控制哪些数据库对象应该包含在迁移中
    """
    # 排除AWS RDS相关的系统表和视图
    if type_ == "table":
        # 排除系统表
        if name.startswith(('pg_', 'information_schema', 'aws_', 'rds_')):
            return False
        
        # 排除一些常见的扩展表
        if name in ('spatial_ref_sys', 'geography_columns', 'geometry_columns'):
            return False
    
    return True


def run_migrations_offline() -> None:
    """在离线模式下运行迁移"""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # 支持SQLite兼容性
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移的核心函数"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        # 环境特定的配置
        version_table_schema=None,  # 使用默认schema
        transaction_per_migration=True,  # 每个迁移一个事务
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在异步模式下运行迁移"""
    try:
        # 获取数据库URL并创建异步引擎
        database_url = get_database_url()
        
        # 将同步URL转换为异步URL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # 配置异步引擎
        configuration = config.get_section(config.config_ini_section)
        configuration["sqlalchemy.url"] = database_url
        
        # 异步引擎配置
        connectable = async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


def run_migrations_online() -> None:
    """在在线模式下运行迁移"""
    # 检查是否需要异步模式
    database_url = get_database_url()
    
    if "+asyncpg" in database_url or os.getenv("ALEMBIC_ASYNC", "false").lower() == "true":
        # 异步模式
        asyncio.run(run_async_migrations())
    else:
        # 同步模式
        from sqlalchemy import create_engine
        
        connectable = create_engine(
            database_url,
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


# 主执行逻辑
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
