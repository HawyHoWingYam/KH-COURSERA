#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表和插入初始数据
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import time

# 添加项目根目录到路径
sys.path.insert(0, '/app')

from db.database import get_database_url, Base
from db.models import (
    Department, User, DocumentType, DepartmentDocTypeAccess, 
    Company, CompanyDocumentConfig, File, ProcessingJob, 
    DocumentFile, ApiUsage, BatchJob
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def wait_for_database(database_url: str, max_retries: int = 30, retry_interval: int = 2):
    """等待数据库可用"""
    logger.info("等待数据库连接...")
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接成功")
            engine.dispose()
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_interval)
            else:
                logger.error(f"❌ 数据库连接失败，已达最大重试次数: {e}")
                return False
    
    return False

def create_database_tables(database_url: str):
    """创建数据库表"""
    try:
        logger.info("创建数据库表...")
        engine = create_engine(database_url)
        
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表创建成功")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建数据库表失败: {e}")
        return False

def add_check_constraints(database_url: str):
    """添加检查约束"""
    try:
        logger.info("添加数据库检查约束...")
        engine = create_engine(database_url)
        
        constraints = [
            # ProcessingJob 状态约束
            """
            ALTER TABLE processing_jobs 
            ADD CONSTRAINT check_status 
            CHECK (status IN ('pending', 'processing', 'success', 'failed', 'error'))
            """,
            
            # BatchJob 状态约束
            """
            ALTER TABLE batch_jobs 
            ADD CONSTRAINT check_batch_status 
            CHECK (status IN ('pending', 'processing', 'success', 'failed', 'error'))
            """,
            
            # User 角色约束
            """
            ALTER TABLE users 
            ADD CONSTRAINT check_user_role 
            CHECK (role IN ('admin', 'user', 'manager'))
            """,
            
            # API Usage 状态约束
            """
            ALTER TABLE api_usage 
            ADD CONSTRAINT check_api_status 
            CHECK (status IN ('success', 'error', 'success_with_fallback', 'timeout', 'rate_limited'))
            """
        ]
        
        with engine.connect() as conn:
            for constraint_sql in constraints:
                try:
                    conn.execute(text(constraint_sql))
                    conn.commit()
                except SQLAlchemyError as e:
                    # 如果约束已存在，忽略错误
                    if "already exists" in str(e) or "duplicate key" in str(e):
                        logger.info(f"约束已存在，跳过...")
                        continue
                    else:
                        logger.warning(f"添加约束失败: {e}")
        
        logger.info("✅ 数据库约束添加完成")
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ 添加数据库约束失败: {e}")
        return False

def create_indexes(database_url: str):
    """创建索引以提高查询性能"""
    try:
        logger.info("创建数据库索引...")
        engine = create_engine(database_url)
        
        indexes = [
            # ProcessingJob 索引
            "CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_processing_jobs_company_id ON processing_jobs(company_id)",
            "CREATE INDEX IF NOT EXISTS idx_processing_jobs_doc_type_id ON processing_jobs(doc_type_id)",
            "CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON processing_jobs(created_at)",
            
            # BatchJob 索引
            "CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_batch_jobs_company_id ON batch_jobs(company_id)",
            "CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at)",
            
            # ApiUsage 索引
            "CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(api_call_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_api_usage_job_id ON api_usage(job_id)",
            
            # 复合索引
            "CREATE INDEX IF NOT EXISTS idx_jobs_company_doctype ON processing_jobs(company_id, doc_type_id)",
        ]
        
        with engine.connect() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                except SQLAlchemyError as e:
                    logger.warning(f"创建索引失败: {e}")
        
        logger.info("✅ 数据库索引创建完成")
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建数据库索引失败: {e}")
        return False

def insert_initial_data(database_url: str):
    """插入初始数据"""
    try:
        logger.info("插入初始数据...")
        engine = create_engine(database_url)
        
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 创建默认部门
            if not session.query(Department).filter_by(department_name="General").first():
                general_dept = Department(department_name="General")
                session.add(general_dept)
                logger.info("✅ 创建默认部门: General")
            
            if not session.query(Department).filter_by(department_name="Finance").first():
                finance_dept = Department(department_name="Finance")
                session.add(finance_dept)
                logger.info("✅ 创建部门: Finance")
                
            if not session.query(Department).filter_by(department_name="Operations").first():
                ops_dept = Department(department_name="Operations")
                session.add(ops_dept)
                logger.info("✅ 创建部门: Operations")
            
            # 创建默认公司
            if not session.query(Company).filter_by(company_code="DEFAULT").first():
                default_company = Company(
                    company_name="Default Company",
                    company_code="DEFAULT",
                    active=True
                )
                session.add(default_company)
                logger.info("✅ 创建默认公司: Default Company")
            
            if not session.query(Company).filter_by(company_code="hana").first():
                hana_company = Company(
                    company_name="Hana Company",
                    company_code="hana", 
                    active=True
                )
                session.add(hana_company)
                logger.info("✅ 创建公司: Hana Company")
            
            # 创建默认文档类型
            document_types = [
                {
                    "type_name": "Invoice",
                    "type_code": "invoice",
                    "description": "Invoice documents for processing"
                },
                {
                    "type_name": "Finance HKBN Billing",
                    "type_code": "[Finance]_hkbn_billing",
                    "description": "HKBN billing documents"
                },
                {
                    "type_name": "MTR Invoice",
                    "type_code": "mtr_invoice", 
                    "description": "MTR invoice documents"
                },
                {
                    "type_name": "Assembly Built",
                    "type_code": "assembly_built",
                    "description": "Assembly built documents"
                }
            ]
            
            for doc_type_data in document_types:
                if not session.query(DocumentType).filter_by(type_code=doc_type_data["type_code"]).first():
                    doc_type = DocumentType(**doc_type_data)
                    session.add(doc_type)
                    logger.info(f"✅ 创建文档类型: {doc_type_data['type_name']}")
            
            session.commit()
            logger.info("✅ 初始数据插入完成")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 插入初始数据失败: {e}")
            return False
        finally:
            session.close()
            
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ 插入初始数据失败: {e}")
        return False

def verify_database_setup(database_url: str):
    """验证数据库设置"""
    try:
        logger.info("验证数据库设置...")
        engine = create_engine(database_url)
        
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # 检查表是否存在
        tables_to_check = [
            (Company, "companies"),
            (DocumentType, "document_types"), 
            (ProcessingJob, "processing_jobs"),
            (BatchJob, "batch_jobs"),
            (User, "users"),
            (Department, "departments")
        ]
        
        for model, table_name in tables_to_check:
            try:
                count = session.query(model).count()
                logger.info(f"✅ 表 {table_name}: {count} 条记录")
            except Exception as e:
                logger.error(f"❌ 表 {table_name} 检查失败: {e}")
                return False
        
        session.close()
        engine.dispose()
        logger.info("✅ 数据库验证完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库验证失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("🚀 开始数据库初始化...")
    
    try:
        # 获取数据库URL
        database_url = get_database_url()
        logger.info(f"数据库URL: {database_url.split('@')[1] if '@' in database_url else 'localhost'}")
        
        # 等待数据库可用
        if not wait_for_database(database_url):
            logger.error("❌ 数据库连接失败，退出初始化")
            sys.exit(1)
        
        # 创建数据库表
        if not create_database_tables(database_url):
            logger.error("❌ 创建数据库表失败，退出初始化") 
            sys.exit(1)
        
        # 添加约束
        if not add_check_constraints(database_url):
            logger.warning("⚠️ 添加约束失败，继续执行")
        
        # 创建索引
        if not create_indexes(database_url):
            logger.warning("⚠️ 创建索引失败，继续执行")
        
        # 插入初始数据
        if not insert_initial_data(database_url):
            logger.error("❌ 插入初始数据失败，退出初始化")
            sys.exit(1)
        
        # 验证数据库设置
        if not verify_database_setup(database_url):
            logger.error("❌ 数据库验证失败，退出初始化")
            sys.exit(1)
        
        logger.info("🎉 数据库初始化完成！")
        
    except Exception as e:
        logger.error(f"❌ 数据库初始化发生未知错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()