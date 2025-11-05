"""
批量映射管理器
提供批量映射更新、预览差异、批量回滚等功能
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from enum import Enum
from psycopg2.extras import Json

from .mapping_history_manager import MappingHistoryManager, MappingOperation

logger = logging.getLogger(__name__)


class BulkMappingPreviewResult:
    """批量映射预览结果"""

    def __init__(self):
        self.affected_orders: List[Dict] = []
        self.summary: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []


class BulkMappingManager:
    """批量映射管理器"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.history_manager = MappingHistoryManager(db_session)

    def preview_bulk_mapping_update(
        self,
        target_orders: Optional[List[int]] = None,
        new_mapping_keys: Optional[List[str]] = None,
        filter_criteria: Optional[Dict] = None,
        operation_type: str = "update"
    ) -> BulkMappingPreviewResult:
        """
        预览批量映射更新

        Args:
            target_orders: 目标订单ID列表（可选）
            new_mapping_keys: 新映射键列表
            filter_criteria: 过滤条件（状态、创建时间等）
            operation_type: 操作类型 ('update', 'append', 'replace')

        Returns:
            预览结果
        """
        try:
            result = BulkMappingPreviewResult()

            # 构建查询条件
            where_conditions = []
            params = {}

            if target_orders:
                placeholders = ','.join([f':order_{i}' for i in range(len(target_orders))])
                where_conditions.append(f"order_id IN ({placeholders})")
                for i, order_id in enumerate(target_orders):
                    params[f'order_{i}'] = order_id

            if filter_criteria:
                if 'status' in filter_criteria:
                    where_conditions.append("status = :status")
                    params['status'] = filter_criteria['status']

                if 'created_after' in filter_criteria:
                    where_conditions.append("created_at >= :created_after")
                    params['created_after'] = filter_criteria['created_after']

                if 'created_before' in filter_criteria:
                    where_conditions.append("created_at <= :created_before")
                    params['created_before'] = filter_criteria['created_before']

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            # 获取受影响的订单
            query_sql = text(f"""
                SELECT
                    order_id, order_name, status, mapping_keys,
                    total_items, completed_items, failed_items,
                    created_at, updated_at
                FROM ocr_orders
                {where_clause}
                ORDER BY order_id
            """)

            orders_result = self.db.execute(query_sql, params)

            total_affected = 0
            unchanged_count = 0

            for row in orders_result:
                order_info = {
                    'order_id': row[0],
                    'order_name': row[1],
                    'status': row[2],
                    'current_mapping_keys': row[3] if row[3] else [],
                    'total_items': row[4],
                    'completed_items': row[5],
                    'failed_items': row[6],
                    'created_at': row[7].isoformat() if row[7] else None,
                    'updated_at': row[8].isoformat() if row[8] else None
                }

                # 计算映射变化
                current_keys = set(order_info['current_mapping_keys'])
                new_keys = set(new_mapping_keys) if new_mapping_keys else set()

                if operation_type == "update" or operation_type == "replace":
                    final_keys = new_keys
                elif operation_type == "append":
                    final_keys = current_keys.union(new_keys)
                else:
                    final_keys = current_keys

                # 计算差异
                added_keys = list(final_keys - current_keys)
                removed_keys = list(current_keys - final_keys)

                order_info['changes'] = {
                    'operation_type': operation_type,
                    'final_mapping_keys': list(final_keys),
                    'added_keys': added_keys,
                    'removed_keys': removed_keys,
                    'has_changes': len(added_keys) > 0 or len(removed_keys) > 0
                }

                # 检查警告条件
                if order_info['status'] != 'COMPLETED' and order_info['changes']['has_changes']:
                    result.warnings.append(f"Order {row[0]} is not completed, mapping changes may affect processing")

                if order_info['changes']['has_changes']:
                    total_affected += 1
                else:
                    unchanged_count += 1

                result.affected_orders.append(order_info)

            # 生成摘要
            result.summary = {
                'total_orders_found': len(result.affected_orders),
                'orders_with_changes': total_affected,
                'orders_unchanged': unchanged_count,
                'operation_type': operation_type,
                'new_mapping_keys': new_mapping_keys or [],
                'preview_timestamp': datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"Failed to preview bulk mapping update: {e}")
            raise

    def execute_bulk_mapping_update(
        self,
        target_orders: Optional[List[int]] = None,
        new_mapping_keys: Optional[List[str]] = None,
        filter_criteria: Optional[Dict] = None,
        operation_type: str = "update",
        operation_reason: Optional[str] = None,
        created_by: Optional[str] = None,
        confirm_changes: bool = False
    ) -> Dict[str, Any]:
        """
        执行批量映射更新

        Args:
            target_orders: 目标订单ID列表
            new_mapping_keys: 新映射键列表
            filter_criteria: 过滤条件
            operation_type: 操作类型
            operation_reason: 操作原因
            created_by: 操作用户
            confirm_changes: 确认执行更改

        Returns:
            执行结果
        """
        try:
            if not confirm_changes:
                raise ValueError("Must confirm changes before executing bulk update")

            # 先预览更改
            preview = self.preview_bulk_mapping_update(
                target_orders, new_mapping_keys, filter_criteria, operation_type
            )

            # 过滤出有变化的订单
            orders_to_update = [
                order for order in preview.affected_orders
                if order['changes']['has_changes']
            ]

            if not orders_to_update:
                return {
                    'success': True,
                    'message': 'No orders require updates',
                    'updated_count': 0,
                    'failed_count': 0,
                    'details': []
                }

            updated_count = 0
            failed_count = 0
            update_details = []

            for order in orders_to_update:
                try:
                    order_id = order['order_id']
                    final_keys = order['changes']['final_mapping_keys']

                    # 更新数据库中的mapping_keys
                    update_sql = text("""
                        UPDATE ocr_orders
                        SET mapping_keys = :mapping_keys, updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = :order_id
                    """)

                    self.db.execute(update_sql, {
                        'mapping_keys': Json(final_keys),
                        'order_id': order_id
                    })

                    # 创建历史记录
                    version = self.history_manager.create_mapping_version(
                        order_id=order_id,
                        mapping_keys=final_keys,
                        operation_type=MappingOperation.UPDATE,
                        operation_reason=operation_reason or f"Bulk {operation_type} operation",
                        created_by=created_by,
                        mapping_statistics={
                            'bulk_operation': True,
                            'operation_type': operation_type,
                            'added_keys': order['changes']['added_keys'],
                            'removed_keys': order['changes']['removed_keys']
                        }
                    )

                    updated_count += 1
                    update_details.append({
                        'order_id': order_id,
                        'status': 'success',
                        'version': version,
                        'changes': order['changes']
                    })

                except Exception as e:
                    failed_count += 1
                    update_details.append({
                        'order_id': order['order_id'],
                        'status': 'failed',
                        'error': str(e),
                        'changes': order['changes']
                    })
                    logger.error(f"Failed to update order {order['order_id']}: {e}")

            # 提交所有更改
            if failed_count == 0:
                self.db.commit()
            else:
                self.db.rollback()
                raise Exception(f"Bulk update failed with {failed_count} errors")

            return {
                'success': True,
                'message': f'Successfully updated {updated_count} orders',
                'updated_count': updated_count,
                'failed_count': failed_count,
                'details': update_details,
                'summary': preview.summary
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to execute bulk mapping update: {e}")
            raise

    def bulk_rollback_orders(
        self,
        target_orders: List[int],
        target_version: Optional[int] = None,
        rollback_to_date: Optional[str] = None,
        created_by: Optional[str] = None,
        rollback_reason: Optional[str] = None,
        confirm_rollback: bool = False
    ) -> Dict[str, Any]:
        """
        批量回滚订单映射

        Args:
            target_orders: 目标订单ID列表
            target_version: 目标版本号（所有订单统一回滚到此版本）
            rollback_to_date: 回滚到指定日期的最后版本
            created_by: 操作用户
            rollback_reason: 回滚原因
            confirm_rollback: 确认执行回滚

        Returns:
            回滚结果
        """
        try:
            if not confirm_rollback:
                raise ValueError("Must confirm rollback before executing")

            if not target_version and not rollback_to_date:
                raise ValueError("Must specify either target_version or rollback_to_date")

            rollback_count = 0
            failed_count = 0
            rollback_details = []

            for order_id in target_orders:
                try:
                    if target_version:
                        # 回滚到指定版本
                        success = self.history_manager.rollback_to_version(
                            order_id=order_id,
                            target_version=target_version,
                            created_by=created_by,
                            rollback_reason=rollback_reason or f"Bulk rollback to version {target_version}"
                        )
                    else:
                        # 回滚到指定日期的最后版本
                        # 首先找到该日期的最后版本
                        date_sql = text("""
                            SELECT MAX(mapping_version)
                            FROM mapping_history
                            WHERE order_id = :order_id
                            AND DATE(created_at) <= :rollback_date
                        """)

                        result = self.db.execute(date_sql, {
                            'order_id': order_id,
                            'rollback_date': rollback_to_date
                        })

                        last_version = result.fetchone()[0]
                        if not last_version:
                            raise ValueError(f"No version found for order {order_id} before date {rollback_to_date}")

                        success = self.history_manager.rollback_to_version(
                            order_id=order_id,
                            target_version=last_version,
                            created_by=created_by,
                            rollback_reason=rollback_reason or f"Bulk rollback to date {rollback_to_date}"
                        )

                    if success:
                        rollback_count += 1
                        rollback_details.append({
                            'order_id': order_id,
                            'status': 'success',
                            'target_version': target_version or last_version
                        })
                    else:
                        failed_count += 1
                        rollback_details.append({
                            'order_id': order_id,
                            'status': 'failed',
                            'error': 'Rollback returned false'
                        })

                except Exception as e:
                    failed_count += 1
                    rollback_details.append({
                        'order_id': order_id,
                        'status': 'failed',
                        'error': str(e)
                    })
                    logger.error(f"Failed to rollback order {order_id}: {e}")

            return {
                'success': failed_count == 0,
                'message': f'Successfully rolled back {rollback_count} orders, {failed_count} failed',
                'rollback_count': rollback_count,
                'failed_count': failed_count,
                'details': rollback_details
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to execute bulk rollback: {e}")
            raise

    def get_bulk_operation_candidates(
        self,
        operation_type: str = "all",
        include_completed_only: bool = True,
        min_items: int = 1
    ) -> List[Dict]:
        """
        获取适合批量操作的订单候选列表

        Args:
            operation_type: 操作类型过滤
            include_completed_only: 只包含已完成的订单
            min_items: 最小项目数量

        Returns:
            订单候选列表
        """
        try:
            where_conditions = [f"total_items >= {min_items}"]
            params = {}

            if include_completed_only:
                where_conditions.append("status = 'COMPLETED'")

            where_clause = "WHERE " + " AND ".join(where_conditions)

            query_sql = text(f"""
                SELECT
                    o.order_id, o.order_name, o.status, o.mapping_keys,
                    o.total_items, o.completed_items, o.failed_items,
                    o.created_at, o.updated_at,
                    COUNT(mh.history_id) as version_count,
                    MAX(mh.created_at) as last_mapping_change
                FROM ocr_orders o
                LEFT JOIN mapping_history mh ON o.order_id = mh.order_id AND mh.item_id IS NULL
                {where_clause}
                GROUP BY o.order_id, o.order_name, o.status, o.mapping_keys,
                         o.total_items, o.completed_items, o.failed_items,
                         o.created_at, o.updated_at
                ORDER BY o.created_at DESC
            """)

            result = self.db.execute(query_sql, params)

            candidates = []
            for row in result:
                candidate = {
                    'order_id': row[0],
                    'order_name': row[1],
                    'status': row[2],
                    'mapping_keys': row[3] if row[3] else [],
                    'total_items': row[4],
                    'completed_items': row[5],
                    'failed_items': row[6],
                    'created_at': row[7].isoformat() if row[7] else None,
                    'updated_at': row[8].isoformat() if row[8] else None,
                    'version_count': row[9] or 0,
                    'last_mapping_change': row[10].isoformat() if row[10] else None,
                    'is_suitable_for_bulk': row[2] == 'COMPLETED' and row[4] >= min_items
                }
                candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.error(f"Failed to get bulk operation candidates: {e}")
            raise