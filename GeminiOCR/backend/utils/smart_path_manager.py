"""
智能路径管理器
提供动态路径模板、冲突检测、自动迁移等高级功能
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text

from .enhanced_file_manager import EnhancedFileManager, FileCategory, FileAccessLevel
from .s3_storage import get_s3_manager

logger = logging.getLogger(__name__)


class PathTemplate(Enum):
    """路径模板枚举"""
    # 基础模板
    BASIC = "{category}/{company}/{doc_type}/{identifier}/{filename}"
    # 时间戳模板
    TIMESTAMPED = "{category}/{company}/{doc_type}/{date}/{identifier}/{filename}"
    # 层级模板
    HIERARCHICAL = "{category}/{company}/{doc_type}/{year}/{month}/{identifier}/{filename}"
    # 紧凑模板
    COMPACT = "{category}/{company}_{doc_type}_{identifier}/{filename}"
    # 自定义模板
    CUSTOM = "custom"


class PathConflictStrategy(Enum):
    """路径冲突解决策略"""
    AUTO_RENAME = "auto_rename"      # 自动重命名
    VERSION_SUFFIX = "version_suffix"  # 添加版本后缀
    TIMESTAMP_SUFFIX = "timestamp_suffix"  # 添加时间戳后缀
    FAIL = "fail"                    # 失败报错
    OVERWRITE = "overwrite"          # 覆盖


@dataclass
class PathContext:
    """路径生成上下文"""
    category: str
    company_id: int
    company_code: str
    doc_type_id: Optional[int] = None
    doc_type_code: Optional[str] = None
    identifier: Optional[str] = None
    filename: Optional[str] = None
    timestamp: Optional[datetime] = None
    custom_vars: Optional[Dict[str, str]] = None


@dataclass
class PathValidationResult:
    """路径验证结果"""
    is_valid: bool
    path: str
    conflicts: List[str]
    suggestions: List[str]
    metadata: Dict[str, Any]


class SmartPathManager:
    """智能路径管理器"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.enhanced_manager = EnhancedFileManager()
        self.s3_manager = get_s3_manager()

        # 默认路径模板配置
        self.default_templates = {
            "uploads": PathTemplate.HIERARCHICAL,
            "results": PathTemplate.TIMESTAMPED,
            "exports": PathTemplate.BASIC,
            "prompts": PathTemplate.BASIC,
            "schemas": PathTemplate.BASIC,
            "backups": PathTemplate.TIMESTAMPED,
            "temp": PathTemplate.COMPACT
        }

        # 路径变量解析器
        self.variable_patterns = {
            'date': r'\{date\}',
            'year': r'\{year\}',
            'month': r'\{month\}',
            'day': r'\{day\}',
            'timestamp': r'\{timestamp\}',
            'uuid': r'\{uuid\}',
            'counter': r'\{counter\}'
        }

    def generate_smart_path(
        self,
        context: PathContext,
        template: Optional[PathTemplate] = None,
        conflict_strategy: PathConflictStrategy = PathConflictStrategy.AUTO_RENAME
    ) -> str:
        """
        生成智能路径

        Args:
            context: 路径生成上下文
            template: 路径模板
            conflict_strategy: 冲突解决策略

        Returns:
            生成的路径
        """
        try:
            # 选择模板
            if template is None:
                template = self.default_templates.get(context.category, PathTemplate.BASIC)

            # 生成基础路径
            base_path = self._generate_path_from_template(template, context)

            # 处理路径冲突
            final_path = self._resolve_path_conflicts(base_path, conflict_strategy, context)

            logger.info(f"Generated smart path: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to generate smart path: {e}")
            raise

    def _generate_path_from_template(self, template: PathTemplate, context: PathContext) -> str:
        """从模板生成路径"""

        # 准备变量字典
        variables = {
            'category': context.category,
            'company': context.company_code,
            'doc_type': context.doc_type_code or 'GENERAL',
            'identifier': context.identifier or 'default',
            'filename': context.filename or ''
        }

        # 添加时间相关变量
        timestamp = context.timestamp or datetime.now()
        variables.update({
            'date': timestamp.strftime('%Y%m%d'),
            'year': timestamp.strftime('%Y'),
            'month': timestamp.strftime('%m'),
            'day': timestamp.strftime('%d'),
            'timestamp': timestamp.strftime('%Y%m%d_%H%M%S'),
            'uuid': str(uuid.uuid4())[:8]
        })

        # 添加自定义变量
        if context.custom_vars:
            variables.update(context.custom_vars)

        # 获取模板字符串
        if template == PathTemplate.CUSTOM:
            # 自定义模板需要在context中提供
            template_str = context.custom_vars.get('template', PathTemplate.BASIC.value)
        else:
            template_str = template.value

        # 替换变量
        path = template_str.format(**variables)

        # 处理计数器变量
        if '{counter}' in path:
            counter = self._get_next_counter(path.replace('{counter}', ''))
            path = path.replace('{counter}', str(counter))

        # 清理路径
        path = self._cleanup_path(path)

        return path

    def _resolve_path_conflicts(
        self,
        path: str,
        strategy: PathConflictStrategy,
        context: PathContext
    ) -> str:
        """解决路径冲突"""

        if not self._path_exists(path):
            return path

        if strategy == PathConflictStrategy.FAIL:
            raise ValueError(f"Path already exists: {path}")

        if strategy == PathConflictStrategy.OVERWRITE:
            return path

        if strategy == PathConflictStrategy.AUTO_RENAME:
            return self._auto_rename_path(path)

        if strategy == PathConflictStrategy.VERSION_SUFFIX:
            return self._add_version_suffix(path)

        if strategy == PathConflictStrategy.TIMESTAMP_SUFFIX:
            return self._add_timestamp_suffix(path)

        return path

    def _auto_rename_path(self, path: str) -> str:
        """自动重命名路径"""
        base_path = Path(path)
        parent = base_path.parent
        stem = base_path.stem
        suffix = base_path.suffix

        counter = 1
        while True:
            new_name = f"{stem}_{counter:03d}{suffix}"
            new_path = parent / new_name
            if not self._path_exists(str(new_path)):
                return str(new_path)
            counter += 1
            if counter > 999:  # 防止无限循环
                # 使用UUID作为后备方案
                uuid_suffix = str(uuid.uuid4())[:8]
                new_name = f"{stem}_{uuid_suffix}{suffix}"
                return str(parent / new_name)

    def _add_version_suffix(self, path: str) -> str:
        """添加版本后缀"""
        base_path = Path(path)
        parent = base_path.parent
        stem = base_path.stem
        suffix = base_path.suffix

        # 查找最高版本号
        version = 1
        while True:
            new_name = f"{stem}_v{version:02d}{suffix}"
            new_path = parent / new_name
            if not self._path_exists(str(new_path)):
                return str(new_path)
            version += 1

    def _add_timestamp_suffix(self, path: str) -> str:
        """添加时间戳后缀"""
        base_path = Path(path)
        parent = base_path.parent
        stem = base_path.stem
        suffix = base_path.suffix

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_name = f"{stem}_{timestamp}{suffix}"
        return str(parent / new_name)

    def _get_next_counter(self, base_path: str) -> int:
        """获取下一个计数器值"""
        try:
            # 查询数据库中类似路径的最大计数器
            # 这里可以根据具体需要实现
            return 1
        except Exception:
            return 1

    def _cleanup_path(self, path: str) -> str:
        """清理路径"""
        # 移除多余的斜杠
        path = re.sub(r'/+', '/', path)
        # 移除开头和结尾的斜杠
        path = path.strip('/')
        # 移除空的路径段
        parts = [part for part in path.split('/') if part.strip()]
        return '/'.join(parts)

    def _path_exists(self, path: str) -> bool:
        """检查路径是否存在"""
        try:
            if self.s3_manager:
                return self.s3_manager.file_exists(path)
            else:
                return Path(path).exists()
        except Exception:
            return False

    def validate_path_structure(self, path: str) -> PathValidationResult:
        """验证路径结构"""
        try:
            conflicts = []
            suggestions = []
            metadata = {}

            # 检查路径格式
            if not path or path.strip() == '':
                return PathValidationResult(
                    is_valid=False,
                    path=path,
                    conflicts=['Empty path'],
                    suggestions=['Provide a valid path'],
                    metadata={}
                )

            # 检查非法字符
            illegal_chars = ['<', '>', ':', '"', '|', '?', '*']
            found_illegal = [char for char in illegal_chars if char in path]
            if found_illegal:
                conflicts.append(f"Illegal characters found: {found_illegal}")

            # 检查路径长度
            if len(path) > 260:  # Windows路径长度限制
                conflicts.append("Path too long (>260 characters)")
                suggestions.append("Shorten path components")

            # 检查路径段长度
            for segment in path.split('/'):
                if len(segment) > 100:
                    conflicts.append(f"Path segment too long: {segment[:50]}...")
                    suggestions.append("Shorten individual path segments")

            # 检查是否存在
            if self._path_exists(path):
                conflicts.append("Path already exists")
                suggestions.append("Use conflict resolution strategy")

            # 分析路径模式
            path_parts = path.split('/')
            metadata = {
                'depth': len(path_parts),
                'total_length': len(path),
                'segments': path_parts,
                'estimated_template': self._identify_template_pattern(path)
            }

            is_valid = len(conflicts) == 0

            return PathValidationResult(
                is_valid=is_valid,
                path=path,
                conflicts=conflicts,
                suggestions=suggestions,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Path validation failed: {e}")
            return PathValidationResult(
                is_valid=False,
                path=path,
                conflicts=[f"Validation error: {str(e)}"],
                suggestions=['Check path format'],
                metadata={}
            )

    def _identify_template_pattern(self, path: str) -> str:
        """识别路径模板模式"""
        parts = path.split('/')

        if len(parts) >= 5:
            # 检查是否包含日期模式
            for part in parts:
                if re.match(r'\d{4}', part):  # 年份模式
                    return "HIERARCHICAL"
                if re.match(r'\d{8}', part):  # 日期模式
                    return "TIMESTAMPED"

        if len(parts) == 3:
            return "COMPACT"

        return "BASIC"

    def migrate_legacy_paths(
        self,
        source_pattern: str,
        target_template: PathTemplate,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """迁移历史路径"""
        try:
            migration_plan = {
                'source_pattern': source_pattern,
                'target_template': target_template.value,
                'files_to_migrate': [],
                'estimated_time': 0,
                'conflicts': [],
                'dry_run': dry_run
            }

            # 查找匹配的文件
            matching_files = self._find_files_by_pattern(source_pattern)

            for file_info in matching_files:
                try:
                    # 解析现有路径
                    old_path = file_info['path']
                    context = self._parse_path_to_context(old_path)

                    # 生成新路径
                    new_path = self._generate_path_from_template(target_template, context)

                    migration_plan['files_to_migrate'].append({
                        'old_path': old_path,
                        'new_path': new_path,
                        'file_size': file_info.get('size', 0),
                        'last_modified': file_info.get('last_modified')
                    })

                except Exception as e:
                    migration_plan['conflicts'].append({
                        'file': file_info['path'],
                        'error': str(e)
                    })

            # 估算迁移时间
            total_size = sum(f.get('file_size', 0) for f in migration_plan['files_to_migrate'])
            migration_plan['estimated_time'] = max(1, total_size // (10 * 1024 * 1024))  # 假设10MB/秒

            # 执行迁移（如果不是试运行）
            if not dry_run:
                migration_plan['results'] = self._execute_migration(migration_plan['files_to_migrate'])

            return migration_plan

        except Exception as e:
            logger.error(f"Failed to migrate legacy paths: {e}")
            raise

    def _find_files_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """根据模式查找文件"""
        # 这里需要根据实际的存储系统实现
        # 可以查询数据库或直接扫描存储系统
        files = []

        try:
            if self.s3_manager:
                # S3实现
                files = self._find_s3_files_by_pattern(pattern)
            else:
                # 本地文件系统实现
                files = self._find_local_files_by_pattern(pattern)
        except Exception as e:
            logger.error(f"Failed to find files by pattern {pattern}: {e}")

        return files

    def _find_s3_files_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """在S3中查找匹配模式的文件"""
        # 实现S3文件查找逻辑
        return []

    def _find_local_files_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """在本地文件系统中查找匹配模式的文件"""
        # 实现本地文件查找逻辑
        return []

    def _parse_path_to_context(self, path: str) -> PathContext:
        """解析路径为上下文"""
        parts = path.split('/')

        # 基本解析逻辑，可以根据需要扩展
        return PathContext(
            category=parts[0] if len(parts) > 0 else 'unknown',
            company_id=0,  # 需要从路径中解析或查询数据库
            company_code=parts[1] if len(parts) > 1 else 'UNKNOWN',
            doc_type_code=parts[2] if len(parts) > 2 else 'GENERAL',
            identifier=parts[3] if len(parts) > 3 else 'default',
            filename=parts[-1] if len(parts) > 0 else ''
        )

    def _execute_migration(self, files_to_migrate: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行文件迁移"""
        results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        for file_info in files_to_migrate:
            try:
                old_path = file_info['old_path']
                new_path = file_info['new_path']

                # 实际的文件移动逻辑
                if self._move_file(old_path, new_path):
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to move {old_path} to {new_path}")

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error migrating {file_info['old_path']}: {str(e)}")

        return results

    def _move_file(self, old_path: str, new_path: str) -> bool:
        """移动文件"""
        try:
            if self.s3_manager:
                # S3文件移动
                return self.s3_manager.copy_file(old_path, new_path) and self.s3_manager.delete_file(old_path)
            else:
                # 本地文件移动
                old_file = Path(old_path)
                new_file = Path(new_path)
                new_file.parent.mkdir(parents=True, exist_ok=True)
                old_file.rename(new_file)
                return True
        except Exception as e:
            logger.error(f"Failed to move file from {old_path} to {new_path}: {e}")
            return False

    def get_path_analytics(self, category: Optional[str] = None) -> Dict[str, Any]:
        """获取路径分析统计"""
        try:
            analytics = {
                'total_paths': 0,
                'path_patterns': {},
                'template_usage': {},
                'conflict_frequency': {},
                'average_depth': 0,
                'storage_efficiency': {}
            }

            # 这里可以实现具体的分析逻辑
            # 查询数据库获取路径使用统计

            return analytics

        except Exception as e:
            logger.error(f"Failed to get path analytics: {e}")
            return {}