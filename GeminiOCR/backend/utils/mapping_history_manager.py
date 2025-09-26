"""
映射历史版本管理器
提供映射配置的版本控制、历史追踪和回滚功能
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from enum import Enum
from psycopg2.extras import Json

logger = logging.getLogger(__name__)


class MappingOperation(Enum):
    """映射操作类型枚举"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ROLLBACK = "ROLLBACK"
    APPLY_RECOMMENDATION = "APPLY_RECOMMENDATION"


class MappingHistoryManager:
    """映射历史管理器"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def create_mapping_version(
        self,
        order_id: int,
        mapping_keys: List[str],
        operation_type: MappingOperation,
        item_id: Optional[int] = None,
        mapping_config: Optional[Dict] = None,
        operation_reason: Optional[str] = None,
        created_by: Optional[str] = None,
        mapping_statistics: Optional[Dict] = None
    ) -> int:
        """
        创建新的映射版本记录

        Args:
            order_id: 订单ID
            mapping_keys: 映射键列表
            operation_type: 操作类型
            item_id: 项目ID（可选，用于item级映射）
            mapping_config: 映射配置
            operation_reason: 操作原因
            created_by: 操作用户
            mapping_statistics: 映射统计信息

        Returns:
            新版本号
        """
        try:
            # 获取当前最大版本号
            current_version = self._get_latest_version(order_id, item_id)
            new_version = current_version + 1

            # 插入新版本记录
            insert_sql = text("""
                INSERT INTO mapping_history (
                    order_id, item_id, mapping_version, mapping_keys,
                    mapping_config, operation_type, operation_reason,
                    created_by, mapping_statistics
                ) VALUES (
                    :order_id, :item_id, :mapping_version, :mapping_keys,
                    :mapping_config, :operation_type, :operation_reason,
                    :created_by, :mapping_statistics
                ) RETURNING history_id
            """)

            result = self.db.execute(insert_sql, {
                'order_id': order_id,
                'item_id': item_id,
                'mapping_version': new_version,
                'mapping_keys': Json(mapping_keys),  # 使用psycopg2.Json包装器
                'mapping_config': Json(mapping_config) if mapping_config else None,
                'operation_type': operation_type.value,
                'operation_reason': operation_reason,
                'created_by': created_by,
                'mapping_statistics': Json(mapping_statistics) if mapping_statistics else None
            })

            history_id = result.fetchone()[0]
            self.db.commit()

            logger.info(f"Created mapping version {new_version} for order {order_id}, history_id: {history_id}")
            return new_version

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create mapping version: {e}")
            raise

    def get_mapping_history(
        self,
        order_id: int,
        item_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取映射历史记录

        Args:
            order_id: 订单ID
            item_id: 项目ID（可选）
            limit: 返回记录数限制

        Returns:
            历史记录列表
        """
        try:
            where_clause = "WHERE order_id = :order_id"
            params = {'order_id': order_id, 'limit': limit}

            if item_id is not None:
                where_clause += " AND item_id = :item_id"
                params['item_id'] = item_id
            else:
                where_clause += " AND item_id IS NULL"  # 只获取order级别的历史

            query_sql = text(f"""
                SELECT
                    history_id, order_id, item_id, mapping_version,
                    mapping_keys, mapping_config, operation_type,
                    operation_reason, created_by, created_at,
                    mapping_statistics
                FROM mapping_history
                {where_clause}
                ORDER BY mapping_version DESC
                LIMIT :limit
            """)

            result = self.db.execute(query_sql, params)

            history_records = []
            for row in result:
                record = {
                    'history_id': row[0],
                    'order_id': row[1],
                    'item_id': row[2],
                    'mapping_version': row[3],
                    'mapping_keys': row[4] if row[4] else [],
                    'mapping_config': row[5] if row[5] else {},
                    'operation_type': row[6],
                    'operation_reason': row[7],
                    'created_by': row[8],
                    'created_at': row[9].isoformat() if row[9] else None,
                    'mapping_statistics': row[10] if row[10] else {}
                }
                history_records.append(record)

            return history_records

        except Exception as e:
            logger.error(f"Failed to get mapping history: {e}")
            raise

    def get_mapping_version(
        self,
        order_id: int,
        version: int,
        item_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        获取特定版本的映射配置

        Args:
            order_id: 订单ID
            version: 版本号
            item_id: 项目ID（可选）

        Returns:
            版本记录或None
        """
        try:
            where_clause = "WHERE order_id = :order_id AND mapping_version = :version"
            params = {'order_id': order_id, 'version': version}

            if item_id is not None:
                where_clause += " AND item_id = :item_id"
                params['item_id'] = item_id
            else:
                where_clause += " AND item_id IS NULL"

            query_sql = text(f"""
                SELECT
                    history_id, order_id, item_id, mapping_version,
                    mapping_keys, mapping_config, operation_type,
                    operation_reason, created_by, created_at,
                    mapping_statistics
                FROM mapping_history
                {where_clause}
                LIMIT 1
            """)

            result = self.db.execute(query_sql, params)
            row = result.fetchone()

            if not row:
                return None

            return {
                'history_id': row[0],
                'order_id': row[1],
                'item_id': row[2],
                'mapping_version': row[3],
                'mapping_keys': row[4] if row[4] else [],
                'mapping_config': row[5] if row[5] else {},
                'operation_type': row[6],
                'operation_reason': row[7],
                'created_by': row[8],
                'created_at': row[9].isoformat() if row[9] else None,
                'mapping_statistics': row[10] if row[10] else {}
            }

        except Exception as e:
            logger.error(f"Failed to get mapping version: {e}")
            raise

    def compare_versions(
        self,
        order_id: int,
        version1: int,
        version2: int,
        item_id: Optional[int] = None
    ) -> Dict:
        """
        比较两个版本的差异

        Args:
            order_id: 订单ID
            version1: 版本1
            version2: 版本2
            item_id: 项目ID（可选）

        Returns:
            版本差异信息
        """
        try:
            v1_data = self.get_mapping_version(order_id, version1, item_id)
            v2_data = self.get_mapping_version(order_id, version2, item_id)

            if not v1_data or not v2_data:
                raise ValueError("One or both versions not found")

            # 比较映射键
            v1_keys = set(v1_data['mapping_keys'])
            v2_keys = set(v2_data['mapping_keys'])

            added_keys = list(v2_keys - v1_keys)
            removed_keys = list(v1_keys - v2_keys)
            unchanged_keys = list(v1_keys & v2_keys)

            # 检查键的顺序变化
            order_changed = v1_data['mapping_keys'] != v2_data['mapping_keys']

            diff_result = {
                'version1': v1_data,
                'version2': v2_data,
                'changes': {
                    'added_keys': added_keys,
                    'removed_keys': removed_keys,
                    'unchanged_keys': unchanged_keys,
                    'order_changed': order_changed,
                    'total_changes': len(added_keys) + len(removed_keys) + (1 if order_changed else 0)
                },
                'summary': self._generate_diff_summary(added_keys, removed_keys, order_changed)
            }

            return diff_result

        except Exception as e:
            logger.error(f"Failed to compare versions: {e}")
            raise

    def rollback_to_version(
        self,
        order_id: int,
        target_version: int,
        item_id: Optional[int] = None,
        created_by: Optional[str] = None,
        rollback_reason: Optional[str] = None
    ) -> bool:
        """
        回滚到指定版本

        Args:
            order_id: 订单ID
            target_version: 目标版本号
            item_id: 项目ID（可选）
            created_by: 操作用户
            rollback_reason: 回滚原因

        Returns:
            回滚是否成功
        """
        try:
            # 获取目标版本数据
            target_data = self.get_mapping_version(order_id, target_version, item_id)
            if not target_data:
                raise ValueError(f"Target version {target_version} not found")

            # 更新order的mapping_keys
            if item_id is None:
                # Order级别回滚
                update_sql = text("""
                    UPDATE ocr_orders
                    SET mapping_keys = :mapping_keys
                    WHERE order_id = :order_id
                """)
                self.db.execute(update_sql, {
                    'mapping_keys': Json(target_data['mapping_keys']),
                    'order_id': order_id
                })
            else:
                # Item级别回滚 - 假设有item mapping配置表
                # 这里可能需要根据实际的item mapping存储方式调整
                pass

            # 创建回滚记录
            self.create_mapping_version(
                order_id=order_id,
                mapping_keys=target_data['mapping_keys'],
                operation_type=MappingOperation.ROLLBACK,
                item_id=item_id,
                mapping_config=target_data['mapping_config'],
                operation_reason=rollback_reason or f"回滚到版本 {target_version}",
                created_by=created_by,
                mapping_statistics={'rollback_target_version': target_version}
            )

            logger.info(f"Successfully rolled back order {order_id} to version {target_version}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to rollback to version: {e}")
            raise

    def _get_latest_version(self, order_id: int, item_id: Optional[int] = None) -> int:
        """获取最新版本号"""
        where_clause = "WHERE order_id = :order_id"
        params = {'order_id': order_id}

        if item_id is not None:
            where_clause += " AND item_id = :item_id"
            params['item_id'] = item_id
        else:
            where_clause += " AND item_id IS NULL"

        query_sql = text(f"""
            SELECT COALESCE(MAX(mapping_version), 0)
            FROM mapping_history
            {where_clause}
        """)

        result = self.db.execute(query_sql, params)
        return result.fetchone()[0]

    def _generate_diff_summary(self, added_keys: List[str], removed_keys: List[str], order_changed: bool) -> str:
        """生成差异摘要"""
        summary_parts = []

        if added_keys:
            summary_parts.append(f"新增 {len(added_keys)} 个映射键: {', '.join(added_keys)}")

        if removed_keys:
            summary_parts.append(f"移除 {len(removed_keys)} 个映射键: {', '.join(removed_keys)}")

        if order_changed and not added_keys and not removed_keys:
            summary_parts.append("映射键顺序发生变化")

        if not summary_parts:
            return "无变化"

        return "; ".join(summary_parts)

    def get_mapping_statistics(self, order_id: int, item_id: Optional[int] = None) -> Dict:
        """
        获取映射历史统计信息

        Returns:
            统计信息包括版本数量、操作类型分布等
        """
        try:
            where_clause = "WHERE order_id = :order_id"
            params = {'order_id': order_id}

            if item_id is not None:
                where_clause += " AND item_id = :item_id"
                params['item_id'] = item_id
            else:
                where_clause += " AND item_id IS NULL"

            # 获取基本统计
            stats_sql = text(f"""
                SELECT
                    COUNT(*) as total_versions,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_modified,
                    COUNT(DISTINCT created_by) as unique_operators
                FROM mapping_history
                {where_clause}
            """)

            stats_result = self.db.execute(stats_sql, params).fetchone()

            # 获取操作类型分布
            ops_sql = text(f"""
                SELECT operation_type, COUNT(*) as count
                FROM mapping_history
                {where_clause}
                GROUP BY operation_type
                ORDER BY count DESC
            """)

            ops_result = self.db.execute(ops_sql, params).fetchall()

            return {
                'total_versions': stats_result[0] if stats_result[0] else 0,
                'first_created': stats_result[1].isoformat() if stats_result[1] else None,
                'last_modified': stats_result[2].isoformat() if stats_result[2] else None,
                'unique_operators': stats_result[3] if stats_result[3] else 0,
                'operation_distribution': {row[0]: row[1] for row in ops_result}
            }

        except Exception as e:
            logger.error(f"Failed to get mapping statistics: {e}")
            raise