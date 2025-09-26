"""
智能映射键推荐系统
分析schema文件和历史数据，为用户推荐最佳的映射键
"""
import json
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from difflib import SequenceMatcher
import re
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

from .file_storage import FileStorageService

logger = logging.getLogger(__name__)


class MappingKeyRecommender:
    """映射键推荐器"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.file_manager = FileStorageService()

        # 字段重要性权重配置
        self.field_importance_weights = {
            # 高权重字段 - 通常用作映射键的字段
            'account': 3.0, 'account_number': 3.0, 'account_no': 3.0,
            'customer': 2.8, 'customer_id': 2.8, 'customer_code': 2.8,
            'shop': 2.5, 'shop_code': 2.5, 'store': 2.5, 'store_code': 2.5,
            'branch': 2.3, 'branch_code': 2.3, 'location': 2.3,
            'department': 2.0, 'dept': 2.0, 'division': 2.0,
            'vendor': 1.8, 'supplier': 1.8, 'partner': 1.8,
            'reference': 1.5, 'ref': 1.5, 'id': 1.5,

            # 中权重字段
            'name': 1.2, 'title': 1.2, 'description': 1.0,
            'phone': 0.8, 'email': 0.8, 'address': 0.8,

            # 低权重字段 - 通常不适合作为映射键
            'amount': 0.3, 'total': 0.3, 'price': 0.3,
            'date': 0.2, 'time': 0.2, 'created': 0.2,
            'filename': 0.1, 'path': 0.1, 'url': 0.1
        }

        # 常见的映射键模式
        self.common_mapping_patterns = [
            r'.*account.*', r'.*shop.*', r'.*store.*', r'.*branch.*',
            r'.*customer.*', r'.*vendor.*', r'.*code.*', r'.*id$'
        ]

    def analyze_schema(self, schema_path: str) -> Dict:
        """分析schema文件，提取字段信息"""
        try:
            # 从S3或本地读取schema文件
            schema_bytes = self.file_manager.read_file(schema_path)

            if not schema_bytes:
                logger.warning(f"无法读取schema文件: {schema_path}")
                return {}

            schema_content = schema_bytes.decode('utf-8')
            schema_data = json.loads(schema_content)

            # 提取所有字段信息
            fields = self._extract_fields_from_schema(schema_data)

            # 计算字段重要性评分
            field_scores = self._calculate_field_importance(fields)

            return {
                'fields': fields,
                'field_scores': field_scores,
                'total_fields': len(fields),
                'schema_path': schema_path
            }

        except Exception as e:
            logger.error(f"分析schema文件失败 {schema_path}: {str(e)}")
            return {}

    def _extract_fields_from_schema(self, schema_data: Dict) -> List[str]:
        """从schema数据中提取字段名"""
        fields = []

        def extract_recursive(data, prefix=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    # 跳过非字段的元数据
                    if key.startswith('_') or key in ['type', 'description', 'format']:
                        continue

                    field_name = f"{prefix}.{key}" if prefix else key
                    fields.append(field_name)

                    # 递归处理嵌套对象
                    if isinstance(value, dict):
                        extract_recursive(value, field_name)
                    elif isinstance(value, list) and value and isinstance(value[0], dict):
                        extract_recursive(value[0], field_name)
            elif isinstance(data, list):
                for item in data[:1]:  # 只处理第一个元素作为模板
                    if isinstance(item, dict):
                        extract_recursive(item, prefix)

        extract_recursive(schema_data)

        # 清理和标准化字段名
        cleaned_fields = []
        for field in fields:
            # 移除前缀，获取最后的字段名
            clean_name = field.split('.')[-1].lower()
            # 移除特殊字符，只保留字母数字和下划线
            clean_name = re.sub(r'[^a-z0-9_]', '_', clean_name)
            if clean_name and clean_name not in cleaned_fields:
                cleaned_fields.append(clean_name)

        return cleaned_fields

    def _calculate_field_importance(self, fields: List[str]) -> Dict[str, float]:
        """计算字段重要性评分"""
        field_scores = {}

        for field in fields:
            score = 0.0
            field_lower = field.lower()

            # 1. 基于关键词的评分
            for keyword, weight in self.field_importance_weights.items():
                if keyword in field_lower:
                    score += weight

            # 2. 基于模式匹配的评分
            for pattern in self.common_mapping_patterns:
                if re.match(pattern, field_lower):
                    score += 1.0
                    break

            # 3. 字段长度的影响（太短或太长都不太适合做映射键）
            if 3 <= len(field) <= 15:
                score += 0.5
            elif len(field) > 20:
                score -= 0.3

            # 4. 特殊前缀/后缀的评分
            if field_lower.endswith('_code') or field_lower.endswith('_id') or field_lower.endswith('_no'):
                score += 1.5

            field_scores[field] = max(0.0, score)  # 确保分数不为负数

        return field_scores

    def get_historical_mapping_usage(self, company_id: Optional[int] = None,
                                   doc_type_id: Optional[int] = None) -> Dict[str, int]:
        """获取历史映射键使用统计"""
        try:
            # 构建查询条件
            where_conditions = []
            params = {}

            if company_id:
                where_conditions.append("oi.company_id = :company_id")
                params['company_id'] = company_id

            if doc_type_id:
                where_conditions.append("oi.doc_type_id = :doc_type_id")
                params['doc_type_id'] = doc_type_id

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # 查询order级别的mapping keys
            order_query = f"""
                SELECT o.mapping_keys
                FROM ocr_orders o
                JOIN ocr_order_items oi ON o.order_id = oi.order_id
                {where_clause}
                AND o.mapping_keys IS NOT NULL
                AND jsonb_array_length(o.mapping_keys::jsonb) > 0
            """

            # 查询item级别的mapping keys
            item_query = f"""
                SELECT oi.mapping_keys
                FROM ocr_order_items oi
                JOIN ocr_orders o ON o.order_id = oi.order_id
                {where_clause}
                AND oi.mapping_keys IS NOT NULL
                AND jsonb_array_length(oi.mapping_keys::jsonb) > 0
            """

            usage_counter = Counter()

            # 统计order级别的使用情况
            result = self.db.execute(text(order_query), params).fetchall()
            for row in result:
                if row[0]:
                    for key in row[0]:
                        usage_counter[key.lower()] += 2  # order级别权重更高

            # 统计item级别的使用情况
            result = self.db.execute(text(item_query), params).fetchall()
            for row in result:
                if row[0]:
                    for key in row[0]:
                        usage_counter[key.lower()] += 1

            return dict(usage_counter)

        except Exception as e:
            logger.error(f"获取历史映射使用统计失败: {str(e)}")
            return {}

    def suggest_mapping_keys(self, company_id: int, doc_type_id: int,
                           csv_headers: Optional[List[str]] = None,
                           limit: int = 3) -> List[Dict]:
        """为指定公司和文档类型推荐映射键"""
        try:
            # 1. 获取公司文档配置
            config_query = """
                SELECT schema_path, default_mapping_keys, mapping_suggestions_config
                FROM company_document_configs
                WHERE company_id = :company_id AND doc_type_id = :doc_type_id AND active = true
            """

            config = self.db.execute(text(config_query), {
                'company_id': company_id,
                'doc_type_id': doc_type_id
            }).fetchone()

            recommendations = []

            # 2. 如果有现有的默认映射键，优先使用
            if config and config[1]:  # default_mapping_keys
                existing_keys = config[1] if isinstance(config[1], list) else []
                for i, key in enumerate(existing_keys[:limit]):
                    recommendations.append({
                        'key': key,
                        'confidence': 0.9,
                        'source': 'existing_default',
                        'reason': '现有默认配置',
                        'priority': i + 1
                    })

            # 3. 基于schema分析推荐
            if config and config[0] and len(recommendations) < limit:  # schema_path
                schema_analysis = self.analyze_schema(config[0])
                if schema_analysis:
                    field_scores = schema_analysis.get('field_scores', {})

                    # 如果有CSV headers，优先匹配
                    if csv_headers:
                        matched_fields = self._match_csv_headers_to_schema(csv_headers, field_scores)
                        for field, score in matched_fields[:limit - len(recommendations)]:
                            recommendations.append({
                                'key': field,
                                'confidence': min(0.95, score / 10.0 + 0.5),
                                'source': 'schema_csv_match',
                                'reason': f'Schema字段匹配CSV列 (评分: {score:.1f})',
                                'priority': len(recommendations) + 1
                            })
                    else:
                        # 基于schema评分推荐
                        sorted_fields = sorted(field_scores.items(), key=lambda x: x[1], reverse=True)
                        for field, score in sorted_fields[:limit - len(recommendations)]:
                            if score > 1.0:  # 只推荐高分字段
                                recommendations.append({
                                    'key': field,
                                    'confidence': min(0.9, score / 10.0 + 0.4),
                                    'source': 'schema_analysis',
                                    'reason': f'Schema分析推荐 (评分: {score:.1f})',
                                    'priority': len(recommendations) + 1
                                })

            # 4. 基于历史使用统计推荐
            if len(recommendations) < limit:
                historical_usage = self.get_historical_mapping_usage(company_id, doc_type_id)
                if not historical_usage:  # 如果没有特定的历史数据，使用全局统计
                    historical_usage = self.get_historical_mapping_usage()

                # 排除已推荐的键
                existing_keys = {r['key'].lower() for r in recommendations}

                for key, usage_count in sorted(historical_usage.items(),
                                             key=lambda x: x[1], reverse=True)[:limit - len(recommendations)]:
                    if key.lower() not in existing_keys and usage_count > 0:
                        confidence = min(0.8, usage_count / 10.0 + 0.3)
                        recommendations.append({
                            'key': key,
                            'confidence': confidence,
                            'source': 'historical_usage',
                            'reason': f'历史使用频率: {usage_count}次',
                            'priority': len(recommendations) + 1
                        })

            # 5. 如果仍然不够，使用通用推荐
            if len(recommendations) < limit:
                default_recommendations = ['account_number', 'shop_code', 'customer_id', 'reference_no']
                existing_keys = {r['key'].lower() for r in recommendations}

                for key in default_recommendations[:limit - len(recommendations)]:
                    if key.lower() not in existing_keys:
                        recommendations.append({
                            'key': key,
                            'confidence': 0.5,
                            'source': 'default_recommendation',
                            'reason': '通用推荐键',
                            'priority': len(recommendations) + 1
                        })

            # 按置信度排序并限制数量
            recommendations.sort(key=lambda x: (-x['confidence'], x['priority']))
            return recommendations[:limit]

        except Exception as e:
            logger.error(f"生成映射键推荐失败: {str(e)}")
            return []

    def _match_csv_headers_to_schema(self, csv_headers: List[str],
                                   field_scores: Dict[str, float]) -> List[Tuple[str, float]]:
        """将CSV列头匹配到schema字段"""
        matches = []

        for csv_header in csv_headers:
            best_match = None
            best_score = 0.0

            csv_header_clean = csv_header.lower().strip()

            # 1. 精确匹配
            if csv_header_clean in field_scores:
                best_match = csv_header
                best_score = field_scores[csv_header_clean] + 5.0  # 精确匹配加分
            else:
                # 2. 模糊匹配
                for schema_field, field_score in field_scores.items():
                    similarity = SequenceMatcher(None, csv_header_clean, schema_field.lower()).ratio()

                    if similarity > 0.7:  # 相似度阈值
                        match_score = field_score + similarity * 3.0
                        if match_score > best_score:
                            best_match = csv_header
                            best_score = match_score

            if best_match and best_score > 1.0:
                matches.append((best_match, best_score))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def update_default_mapping_keys(self, company_id: int, doc_type_id: int,
                                  mapping_keys: List[str]) -> bool:
        """更新默认映射键配置"""
        try:
            update_query = """
                UPDATE company_document_configs
                SET default_mapping_keys = :mapping_keys,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = :company_id AND doc_type_id = :doc_type_id
            """

            result = self.db.execute(text(update_query), {
                'mapping_keys': json.dumps(mapping_keys),
                'company_id': company_id,
                'doc_type_id': doc_type_id
            })

            self.db.commit()

            logger.info(f"已更新默认映射键: company_id={company_id}, doc_type_id={doc_type_id}, keys={mapping_keys}")
            return result.rowcount > 0

        except Exception as e:
            logger.error(f"更新默认映射键失败: {str(e)}")
            self.db.rollback()
            return False

    def get_mapping_analytics(self, company_id: Optional[int] = None) -> Dict:
        """获取映射使用分析数据"""
        try:
            # 基础统计
            stats = {
                'total_orders_with_mapping': 0,
                'total_items_with_mapping': 0,
                'most_used_keys': {},
                'company_preferences': {},
                'mapping_success_rate': 0.0
            }

            # 查询统计数据
            base_condition = "WHERE o.mapping_keys IS NOT NULL" + (
                f" AND o.company_id = {company_id}" if company_id else ""
            )

            # 总订单数
            order_count_query = f"SELECT COUNT(*) FROM ocr_orders o {base_condition}"
            stats['total_orders_with_mapping'] = self.db.execute(text(order_count_query)).scalar() or 0

            # 总item数
            item_count_query = f"""
                SELECT COUNT(*) FROM ocr_order_items oi
                JOIN ocr_orders o ON o.order_id = oi.order_id
                {base_condition.replace('o.mapping_keys', 'oi.mapping_keys')}
            """
            stats['total_items_with_mapping'] = self.db.execute(text(item_count_query)).scalar() or 0

            # 获取历史使用统计
            stats['most_used_keys'] = self.get_historical_mapping_usage(company_id)

            return stats

        except Exception as e:
            logger.error(f"获取映射分析数据失败: {str(e)}")
            return {}