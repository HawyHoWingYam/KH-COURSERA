#!/usr/bin/env python3
"""
Prompt and Schema Migration to S3
将现有的prompt和schema文件迁移到S3存储

功能:
- 扫描本地uploads/document_type/目录结构
- 上传所有.txt prompts和.json schemas到S3
- 更新数据库中的路径引用
- 生成详细的迁移报告
- 支持回滚操作
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging
import hashlib
import shutil

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "GeminiOCR" / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from database_manager import DatabaseManager
from db.models import CompanyDocumentConfig, Company, DocumentType
from utils.s3_storage import get_s3_manager, is_s3_enabled
from utils.prompt_schema_manager import get_prompt_schema_manager

logger = logging.getLogger(__name__)


class MigrationReporter:
    """迁移报告生成器"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.report = {
            "migration_id": self._generate_migration_id(),
            "start_time": self.start_time.isoformat(),
            "end_time": None,
            "status": "running",
            "summary": {
                "total_files_found": 0,
                "total_files_migrated": 0,
                "total_files_failed": 0,
                "prompts_migrated": 0,
                "schemas_migrated": 0,
                "database_updates": 0,
                "database_update_failures": 0
            },
            "files": [],
            "database_updates": [],
            "errors": [],
            "warnings": []
        }
    
    def _generate_migration_id(self) -> str:
        """生成唯一的迁移ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        return f"migrate_s3_{timestamp}_{random_suffix}"
    
    def add_file_result(self, file_path: str, file_type: str, status: str, 
                       s3_key: Optional[str] = None, error: Optional[str] = None):
        """添加文件处理结果"""
        self.report["files"].append({
            "file_path": file_path,
            "file_type": file_type,
            "status": status,
            "s3_key": s3_key,
            "error": error,
            "processed_at": datetime.now().isoformat()
        })
        
        self.report["summary"]["total_files_found"] += 1
        if status == "success":
            self.report["summary"]["total_files_migrated"] += 1
            if file_type == "prompt":
                self.report["summary"]["prompts_migrated"] += 1
            else:
                self.report["summary"]["schemas_migrated"] += 1
        else:
            self.report["summary"]["total_files_failed"] += 1
    
    def add_database_update(self, config_id: int, old_path: str, new_path: str, 
                           path_type: str, status: str, error: Optional[str] = None):
        """添加数据库更新结果"""
        self.report["database_updates"].append({
            "config_id": config_id,
            "old_path": old_path,
            "new_path": new_path,
            "path_type": path_type,
            "status": status,
            "error": error,
            "updated_at": datetime.now().isoformat()
        })
        
        if status == "success":
            self.report["summary"]["database_updates"] += 1
        else:
            self.report["summary"]["database_update_failures"] += 1
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.report["errors"].append({
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_warning(self, warning: str):
        """添加警告信息"""
        self.report["warnings"].append({
            "warning": warning,
            "timestamp": datetime.now().isoformat()
        })
    
    def finalize(self, status: str):
        """完成报告"""
        self.report["end_time"] = datetime.now().isoformat()
        self.report["status"] = status
        self.report["duration_seconds"] = (datetime.now() - self.start_time).total_seconds()
    
    def save_report(self, output_dir: Path):
        """保存报告"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            report_file = output_dir / f"{self.report['migration_id']}_report.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 迁移报告已保存: {report_file}")
            return report_file
            
        except Exception as e:
            logger.error(f"❌ 保存迁移报告失败: {e}")
            return None
    
    def print_summary(self):
        """打印摘要"""
        print("\n" + "="*60)
        print(f"📊 迁移摘要 - {self.report['migration_id']}")
        print("="*60)
        print(f"开始时间: {self.report['start_time']}")
        print(f"结束时间: {self.report['end_time']}")
        print(f"总耗时: {self.report.get('duration_seconds', 0):.2f} 秒")
        print(f"状态: {self.report['status']}")
        print()
        
        summary = self.report["summary"]
        print(f"📁 文件迁移:")
        print(f"  发现文件: {summary['total_files_found']}")
        print(f"  成功迁移: {summary['total_files_migrated']}")
        print(f"  失败文件: {summary['total_files_failed']}")
        print(f"  - Prompts: {summary['prompts_migrated']}")
        print(f"  - Schemas: {summary['schemas_migrated']}")
        print()
        
        print(f"🗄️ 数据库更新:")
        print(f"  成功更新: {summary['database_updates']}")
        print(f"  更新失败: {summary['database_update_failures']}")
        print()
        
        if self.report["errors"]:
            print(f"❌ 错误数量: {len(self.report['errors'])}")
        
        if self.report["warnings"]:
            print(f"⚠️ 警告数量: {len(self.report['warnings'])}")
        
        print("="*60)


class PromptSchemaMigrator:
    """Prompt和Schema迁移器"""
    
    def __init__(self, dry_run: bool = False, backup_enabled: bool = True):
        """
        初始化迁移器
        
        Args:
            dry_run: 是否为试运行模式
            backup_enabled: 是否启用备份
        """
        self.dry_run = dry_run
        self.backup_enabled = backup_enabled
        self.db_manager = None
        self.s3_manager = get_s3_manager()
        self.prompt_schema_manager = get_prompt_schema_manager()
        self.reporter = MigrationReporter()
        
        # 源目录路径
        self.source_dir = backend_path / "uploads" / "document_type"
        
        # 备份目录
        if backup_enabled:
            self.backup_dir = project_root / "migration_backups" / self.reporter.report["migration_id"]
            self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """初始化数据库连接"""
        try:
            environment = os.getenv('DATABASE_ENV', 'local')
            self.db_manager = DatabaseManager(environment)
            await self.db_manager.initialize()
            logger.info(f"✅ 数据库连接已建立: {environment}")
            
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        if self.db_manager:
            await self.db_manager.close()
    
    def _discover_files(self) -> List[Dict]:
        """发现需要迁移的文件"""
        logger.info(f"🔍 扫描目录: {self.source_dir}")
        
        if not self.source_dir.exists():
            logger.error(f"❌ 源目录不存在: {self.source_dir}")
            return []
        
        files_to_migrate = []
        
        for doc_type_dir in self.source_dir.iterdir():
            if not doc_type_dir.is_dir():
                continue
                
            logger.debug(f"📂 扫描文档类型目录: {doc_type_dir.name}")
            
            for provider_dir in doc_type_dir.iterdir():
                if not provider_dir.is_dir():
                    continue
                
                logger.debug(f"📂 扫描提供商目录: {provider_dir.name}")
                
                # 扫描prompt文件
                prompt_dir = provider_dir / "prompt"
                if prompt_dir.exists():
                    for prompt_file in prompt_dir.glob("*.txt"):
                        files_to_migrate.append({
                            "file_path": prompt_file,
                            "file_type": "prompt",
                            "doc_type": doc_type_dir.name,
                            "provider": provider_dir.name,
                            "filename": prompt_file.name,
                            "company_code": provider_dir.name,  # 假设provider名就是company_code
                            "doc_type_code": doc_type_dir.name
                        })
                
                # 扫描schema文件
                schema_dir = provider_dir / "schema"
                if schema_dir.exists():
                    for schema_file in schema_dir.glob("*.json"):
                        files_to_migrate.append({
                            "file_path": schema_file,
                            "file_type": "schema",
                            "doc_type": doc_type_dir.name,
                            "provider": provider_dir.name,
                            "filename": schema_file.name,
                            "company_code": provider_dir.name,  # 假设provider名就是company_code
                            "doc_type_code": doc_type_dir.name
                        })
        
        logger.info(f"📊 发现 {len(files_to_migrate)} 个文件需要迁移")
        return files_to_migrate
    
    def _create_backup(self, file_path: Path) -> bool:
        """创建文件备份"""
        if not self.backup_enabled:
            return True
        
        try:
            # 保持原有的目录结构
            relative_path = file_path.relative_to(backend_path)
            backup_path = self.backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(file_path, backup_path)
            logger.debug(f"💾 备份已创建: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建备份失败: {e}")
            return False
    
    async def _migrate_file(self, file_info: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        迁移单个文件
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (成功状态, S3键名, 错误信息)
        """
        file_path = file_info["file_path"]
        file_type = file_info["file_type"]
        company_code = file_info["company_code"]
        doc_type_code = file_info["doc_type_code"]
        filename = file_info["filename"]
        
        try:
            # 创建备份
            if not self._create_backup(file_path):
                return False, None, "备份创建失败"
            
            # 读取文件内容
            if file_type == "prompt":
                content = file_path.read_text(encoding='utf-8')
                
                if self.dry_run:
                    logger.info(f"🔄 [DRY RUN] 将迁移prompt: {file_path}")
                    return True, f"s3://prompts/{company_code}/{doc_type_code}/{filename}", None
                
                # 上传到S3
                success = await self.prompt_schema_manager.upload_prompt(
                    company_code, doc_type_code, content, filename
                )
                
            else:  # schema
                with open(file_path, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                
                if self.dry_run:
                    logger.info(f"🔄 [DRY RUN] 将迁移schema: {file_path}")
                    return True, f"s3://schemas/{company_code}/{doc_type_code}/{filename}", None
                
                # 上传到S3
                success = await self.prompt_schema_manager.upload_schema(
                    company_code, doc_type_code, schema_data, filename
                )
            
            if success:
                s3_key = f"s3://{file_type}s/{company_code}/{doc_type_code}/{filename}"
                logger.info(f"✅ 文件迁移成功: {file_path} -> {s3_key}")
                return True, s3_key, None
            else:
                return False, None, "S3上传失败"
                
        except Exception as e:
            logger.error(f"❌ 文件迁移失败: {file_path}, 错误: {e}")
            return False, None, str(e)
    
    def _map_paths_to_company_codes(self) -> Dict[str, str]:
        """
        映射本地路径到公司代码
        这里需要根据实际的命名规则进行调整
        """
        path_mapping = {
            # 示例映射，需要根据实际情况调整
            "hana": "HANA",
            "hkpc": "HKPC",
            "[Finance]_hkbn_billing": "HKBN_FINANCE",
            "assembly_built": "ASSEMBLY",
            "invoice": "INVOICE"
        }
        return path_mapping
    
    async def _update_database_paths(self, migrated_files: List[Dict]):
        """更新数据库中的路径引用"""
        logger.info("🗄️ 开始更新数据库路径引用")
        
        try:
            async with self.db_manager.get_async_connection() as conn:
                # 获取所有配置
                configs = await conn.fetch("""
                    SELECT cdc.config_id, cdc.company_id, cdc.doc_type_id, 
                           cdc.prompt_path, cdc.schema_path,
                           c.company_code, dt.type_code
                    FROM company_document_configs cdc
                    JOIN companies c ON cdc.company_id = c.company_id
                    JOIN document_types dt ON cdc.doc_type_id = dt.doc_type_id
                    WHERE cdc.active = true
                """)
                
                path_mapping = self._map_paths_to_company_codes()
                
                for config in configs:
                    config_id = config['config_id']
                    current_prompt_path = config['prompt_path']
                    current_schema_path = config['schema_path']
                    company_code = config['company_code']
                    doc_type_code = config['type_code']
                    
                    # 查找对应的迁移文件
                    new_prompt_path = None
                    new_schema_path = None
                    
                    for file_info in migrated_files:
                        if (file_info['status'] == 'success' and 
                            file_info['company_code'] == company_code and
                            file_info['doc_type_code'] == doc_type_code):
                            
                            if file_info['file_type'] == 'prompt':
                                new_prompt_path = file_info['s3_key']
                            elif file_info['file_type'] == 'schema':
                                new_schema_path = file_info['s3_key']
                    
                    # 更新数据库
                    updates_made = False
                    
                    if new_prompt_path and current_prompt_path != new_prompt_path:
                        if not self.dry_run:
                            await conn.execute("""
                                UPDATE company_document_configs 
                                SET prompt_path = $1, updated_at = NOW()
                                WHERE config_id = $2
                            """, new_prompt_path, config_id)
                        
                        self.reporter.add_database_update(
                            config_id, current_prompt_path, new_prompt_path, "prompt", "success"
                        )
                        updates_made = True
                        logger.info(f"✅ 更新prompt路径: {config_id} -> {new_prompt_path}")
                    
                    if new_schema_path and current_schema_path != new_schema_path:
                        if not self.dry_run:
                            await conn.execute("""
                                UPDATE company_document_configs 
                                SET schema_path = $1, updated_at = NOW()
                                WHERE config_id = $2
                            """, new_schema_path, config_id)
                        
                        self.reporter.add_database_update(
                            config_id, current_schema_path, new_schema_path, "schema", "success"
                        )
                        updates_made = True
                        logger.info(f"✅ 更新schema路径: {config_id} -> {new_schema_path}")
                    
                    if not updates_made:
                        logger.debug(f"🔄 配置 {config_id} 无需更新")
                
        except Exception as e:
            logger.error(f"❌ 数据库更新失败: {e}")
            self.reporter.add_error(f"数据库更新失败: {e}")
    
    async def run_migration(self) -> bool:
        """运行迁移"""
        try:
            logger.info(f"🚀 开始迁移 {'(试运行模式)' if self.dry_run else ''}")
            
            # 检查S3连接
            if not is_s3_enabled():
                error_msg = "S3存储未启用，无法进行迁移"
                logger.error(f"❌ {error_msg}")
                self.reporter.add_error(error_msg)
                self.reporter.finalize("failed")
                return False
            
            # 发现文件
            files_to_migrate = self._discover_files()
            if not files_to_migrate:
                logger.warning("⚠️ 未发现需要迁移的文件")
                self.reporter.finalize("completed")
                return True
            
            # 迁移文件
            migrated_files = []
            for file_info in files_to_migrate:
                logger.info(f"🔄 迁移文件: {file_info['file_path']}")
                
                success, s3_key, error = await self._migrate_file(file_info)
                
                status = "success" if success else "failed"
                self.reporter.add_file_result(
                    str(file_info['file_path']), file_info['file_type'], 
                    status, s3_key, error
                )
                
                if success:
                    migrated_files.append({
                        **file_info,
                        'status': 'success',
                        's3_key': s3_key
                    })
            
            # 更新数据库
            if migrated_files:
                await self._update_database_paths(migrated_files)
            
            # 完成迁移
            migration_status = "completed" if self.reporter.report["summary"]["total_files_failed"] == 0 else "completed_with_errors"
            self.reporter.finalize(migration_status)
            
            logger.info(f"✅ 迁移完成，状态: {migration_status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 迁移失败: {e}")
            self.reporter.add_error(f"迁移失败: {e}")
            self.reporter.finalize("failed")
            return False


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将prompt和schema文件迁移到S3存储",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不实际执行迁移'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='禁用备份功能'
    )
    
    parser.add_argument(
        '--environment',
        choices=['local', 'sandbox', 'uat', 'production'],
        default=os.getenv('DATABASE_ENV', 'local'),
        help='数据库环境'
    )
    
    parser.add_argument(
        '--report-dir',
        type=Path,
        default=project_root / "migration_reports",
        help='报告保存目录'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 设置环境
    os.environ['DATABASE_ENV'] = args.environment
    
    # 创建迁移器
    migrator = PromptSchemaMigrator(
        dry_run=args.dry_run,
        backup_enabled=not args.no_backup
    )
    
    try:
        # 初始化
        await migrator.initialize()
        
        # 运行迁移
        success = await migrator.run_migration()
        
        # 保存报告
        report_file = migrator.reporter.save_report(args.report_dir)
        
        # 打印摘要
        migrator.reporter.print_summary()
        
        if report_file:
            print(f"\n📄 详细报告: {report_file}")
        
        # 返回退出码
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n👋 迁移被用户中断")
        migrator.reporter.finalize("cancelled")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ 迁移过程中发生未知错误: {e}")
        migrator.reporter.add_error(f"未知错误: {e}")
        migrator.reporter.finalize("failed")
        sys.exit(1)
        
    finally:
        await migrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())