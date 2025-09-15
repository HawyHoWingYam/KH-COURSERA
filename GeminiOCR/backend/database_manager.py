"""
Database Manager for GeminiOCR
支持多环境数据库连接管理，包括本地PostgreSQL和AWS Aurora PostgreSQL

Features:
- 环境配置自动切换 (local, sandbox, uat, production)
- AWS Secrets Manager集成
- 连接池管理
- 读写分离
- 健康检查和故障转移
- 连接重试机制
"""

import os
import yaml
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, TimeoutError
import asyncpg
from asyncpg import Pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置数据类"""
    host: str
    port: int
    database: str
    username: str
    password: str
    readonly_host: Optional[str] = None
    ssl_mode: str = "require"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    environment: str = "local"
    
    def get_connection_url(self, readonly: bool = False) -> str:
        """构建数据库连接URL"""
        host = self.readonly_host if readonly and self.readonly_host else self.host
        return f"postgresql://{self.username}:{self.password}@{host}:{self.port}/{self.database}"


class DatabaseManager:
    """数据库管理器 - 支持多环境配置和连接管理"""
    
    def __init__(self, environment: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            environment: 环境名称 (local, sandbox, uat, production)
                       如果未提供，将从环境变量 DATABASE_ENV 读取
        """
        self.environment = environment or os.getenv('DATABASE_ENV', 'local')
        self.config: Optional[DatabaseConfig] = None
        self.engine = None
        self.readonly_engine = None
        self.session_factory = None
        self.async_pool: Optional[Pool] = None
        self.readonly_async_pool: Optional[Pool] = None
        
        # AWS clients (仅在需要时初始化)
        self._secrets_client = None
        self._parameter_store_client = None
        
        logger.info(f"Initializing DatabaseManager for environment: {self.environment}")
        
    async def initialize(self):
        """异步初始化数据库连接"""
        try:
            await self._load_config()
            await self._create_connections()
            await self._verify_connections()
            logger.info(f"Database manager initialized successfully for {self.environment}")
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
            
    async def _load_config(self):
        """加载数据库配置"""
        config_path = Path(__file__).parent / "config" / "database" / f"{self.environment}.yml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Database config file not found: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        # 解析配置
        db_config = config_data['database']
        
        # 处理环境变量替换
        db_config = await self._resolve_config_variables(db_config)
        
        self.config = DatabaseConfig(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            username=db_config['username'],
            password=db_config['password'],
            readonly_host=db_config.get('readonly_host'),
            ssl_mode=db_config.get('ssl_mode', 'require'),
            pool_size=db_config.get('pool_size', 10),
            max_overflow=db_config.get('max_overflow', 20),
            pool_timeout=db_config.get('pool_timeout', 30),
            pool_recycle=db_config.get('pool_recycle', 3600),
            environment=self.environment
        )
        
    async def _resolve_config_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析配置中的环境变量和AWS资源引用"""
        resolved_config = config.copy()
        
        for key, value in config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                var_name = value[2:-1]  # 移除 ${ 和 }
                
                # 优先从环境变量获取
                env_value = os.getenv(var_name)
                if env_value:
                    resolved_config[key] = env_value
                    continue
                
                # 从AWS Secrets Manager获取
                if self.environment in ['sandbox', 'uat', 'production']:
                    aws_value = await self._get_from_aws_secrets(var_name)
                    if aws_value:
                        resolved_config[key] = aws_value
                        continue
                
                # 如果都没找到，抛出错误
                raise ValueError(f"Could not resolve configuration variable: {var_name}")
                
        return resolved_config
        
    async def _get_from_aws_secrets(self, secret_name: str) -> Optional[str]:
        """从AWS Secrets Manager获取值"""
        try:
            if not self._secrets_client:
                self._secrets_client = boto3.client('secretsmanager', region_name='ap-southeast-1')
                
            # 尝试多种可能的secret名称格式
            possible_names = [
                f"hya-ocr/{self.environment}/database/credentials",
                f"hya-ocr/{self.environment}/database/{secret_name.lower()}",
                secret_name
            ]
            
            for name in possible_names:
                try:
                    response = self._secrets_client.get_secret_value(SecretId=name)
                    secret_data = json.loads(response['SecretString'])
                    
                    # 映射常见的secret键名
                    key_mappings = {
                        'AURORA_WRITER_ENDPOINT': 'host',
                        'AURORA_READER_ENDPOINT': 'readonly_host',
                        'DATABASE_USERNAME': 'username',
                        'DATABASE_PASSWORD': 'password',
                        'DATABASE_SECRET_ARN': 'secret_arn'
                    }
                    
                    mapped_key = key_mappings.get(secret_name, secret_name.lower())
                    if mapped_key in secret_data:
                        return secret_data[mapped_key]
                        
                except self._secrets_client.exceptions.ResourceNotFoundException:
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to retrieve secret {secret_name}: {e}")
            
        return None
        
    async def _create_connections(self):
        """创建数据库连接"""
        if not self.config:
            raise RuntimeError("Database config not loaded")
            
        # 创建SQLAlchemy同步连接
        self._create_sync_connections()
        
        # 创建AsyncPG异步连接池
        await self._create_async_connections()
        
    def _create_sync_connections(self):
        """创建SQLAlchemy同步连接"""
        # 主写入连接
        self.engine = create_engine(
            self.config.get_connection_url(),
            poolclass=QueuePool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=True,
            echo=self.environment == 'local'  # 仅在本地环境显示SQL
        )
        
        # 只读连接 (如果配置了读副本)
        if self.config.readonly_host:
            self.readonly_engine = create_engine(
                self.config.get_connection_url(readonly=True),
                poolclass=QueuePool,
                pool_size=self.config.pool_size // 2,
                max_overflow=self.config.max_overflow // 2,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True,
                echo=False
            )
            
        # 创建Session工厂
        self.session_factory = sessionmaker(bind=self.engine)
        
    async def _create_async_connections(self):
        """创建AsyncPG异步连接池"""
        try:
            # 主连接池
            self.async_pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                ssl=self.config.ssl_mode if self.config.ssl_mode != 'disable' else False,
                min_size=5,
                max_size=self.config.pool_size,
                command_timeout=60
            )
            
            # 只读连接池
            if self.config.readonly_host:
                self.readonly_async_pool = await asyncpg.create_pool(
                    host=self.config.readonly_host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.username,
                    password=self.config.password,
                    ssl=self.config.ssl_mode if self.config.ssl_mode != 'disable' else False,
                    min_size=2,
                    max_size=self.config.pool_size // 2,
                    command_timeout=60
                )
                
        except Exception as e:
            logger.error(f"Failed to create async connections: {e}")
            raise
            
    async def _verify_connections(self):
        """验证数据库连接"""
        try:
            # 验证同步连接
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"Connected to PostgreSQL: {version}")
                
            # 验证异步连接
            if self.async_pool:
                async with self.async_pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    logger.info(f"Async connection verified: {version[:50]}...")
                    
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            raise
            
    def get_session(self):
        """获取数据库会话 (同步)"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        return self.session_factory()
        
    @asynccontextmanager
    async def get_async_connection(self, readonly: bool = False):
        """获取异步数据库连接 (上下文管理器)"""
        pool = self.readonly_async_pool if readonly and self.readonly_async_pool else self.async_pool
        
        if not pool:
            raise RuntimeError("Async pool not initialized")
            
        async with pool.acquire() as conn:
            yield conn
            
    async def execute_query(self, query: str, params: Optional[Dict] = None, readonly: bool = False):
        """执行查询 (异步)"""
        async with self.get_async_connection(readonly=readonly) as conn:
            if params:
                return await conn.fetch(query, *params.values())
            else:
                return await conn.fetch(query)
                
    async def execute_command(self, command: str, params: Optional[Dict] = None):
        """执行命令 (异步写入)"""
        async with self.get_async_connection(readonly=False) as conn:
            if params:
                return await conn.execute(command, *params.values())
            else:
                return await conn.execute(command)
                
    async def health_check(self) -> Dict[str, Any]:
        """数据库健康检查"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # 检查写入连接
            async with self.get_async_connection(readonly=False) as conn:
                await conn.fetchval("SELECT 1")
            write_latency = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # 检查只读连接 (如果存在)
            read_latency = None
            if self.readonly_async_pool:
                start_time = asyncio.get_event_loop().time()
                async with self.get_async_connection(readonly=True) as conn:
                    await conn.fetchval("SELECT 1")
                read_latency = (asyncio.get_event_loop().time() - start_time) * 1000
                
            return {
                "status": "healthy",
                "environment": self.environment,
                "write_latency_ms": round(write_latency, 2),
                "read_latency_ms": round(read_latency, 2) if read_latency else None,
                "pool_stats": {
                    "write_pool_size": self.async_pool.get_size(),
                    "read_pool_size": self.readonly_async_pool.get_size() if self.readonly_async_pool else None
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "environment": self.environment,
                "error": str(e)
            }
            
    async def close(self):
        """关闭所有数据库连接"""
        if self.async_pool:
            await self.async_pool.close()
        if self.readonly_async_pool:
            await self.readonly_async_pool.close()
        if self.engine:
            self.engine.dispose()
        if self.readonly_engine:
            self.readonly_engine.dispose()
            
        logger.info("Database connections closed")


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


async def get_database_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
        
    return _db_manager


async def switch_environment(environment: str):
    """切换数据库环境"""
    global _db_manager
    
    if _db_manager:
        await _db_manager.close()
        
    _db_manager = DatabaseManager(environment)
    await _db_manager.initialize()
    
    logger.info(f"Switched to database environment: {environment}")


# 便捷函数
async def get_db_session():
    """获取数据库会话"""
    db_manager = await get_database_manager()
    return db_manager.get_session()


async def execute_query(query: str, params: Optional[Dict] = None, readonly: bool = False):
    """执行查询"""
    db_manager = await get_database_manager()
    return await db_manager.execute_query(query, params, readonly)


async def health_check():
    """数据库健康检查"""
    db_manager = await get_database_manager()
    return await db_manager.health_check()


if __name__ == "__main__":
    # 测试脚本
    async def test_database_manager():
        """测试数据库管理器"""
        
        # 测试本地环境
        print("Testing local environment...")
        await switch_environment("local")
        health = await health_check()
        print(f"Local health: {health}")
        
        # 测试sandbox环境 (如果配置了)
        if os.getenv('TEST_SANDBOX'):
            print("Testing sandbox environment...")
            await switch_environment("sandbox")
            health = await health_check()
            print(f"Sandbox health: {health}")
            
    # 运行测试
    asyncio.run(test_database_manager())