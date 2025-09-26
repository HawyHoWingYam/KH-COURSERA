"""
高级映射分析工具
提供映射使用模式分析、性能优化建议、数据洞察等功能
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from collections import defaultdict, Counter
import statistics
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import re

logger = logging.getLogger(__name__)


@dataclass
class MappingUsagePattern:
    """映射使用模式"""
    mapping_key: str
    frequency: int
    companies: Set[str]
    doc_types: Set[str]
    success_rate: float
    avg_processing_time: Optional[float]
    last_used: Optional[datetime]


@dataclass
class MappingInsight:
    """映射洞察"""
    insight_type: str
    title: str
    description: str
    impact_score: float  # 0-100
    recommendations: List[str]
    affected_items: List[Dict[str, Any]]
    data_points: Dict[str, Any]


@dataclass
class AnalysisReport:
    """分析报告"""
    report_id: str
    generated_at: datetime
    analysis_period: Tuple[datetime, datetime]
    summary: Dict[str, Any]
    insights: List[MappingInsight]
    patterns: List[MappingUsagePattern]
    recommendations: List[str]
    metrics: Dict[str, Any]


class AdvancedMappingAnalyzer:
    """高级映射分析工具"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def generate_comprehensive_analysis(
        self,
        analysis_period_days: int = 30,
        include_historical: bool = True,
        focus_areas: Optional[List[str]] = None
    ) -> AnalysisReport:
        """
        生成综合分析报告

        Args:
            analysis_period_days: 分析周期天数
            include_historical: 是否包含历史数据
            focus_areas: 重点分析领域

        Returns:
            分析报告
        """
        try:
            # 计算分析时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=analysis_period_days)

            # 生成报告ID
            report_id = f"mapping_analysis_{end_date.strftime('%Y%m%d_%H%M%S')}"

            logger.info(f"Generating comprehensive mapping analysis: {report_id}")

            # 收集各种分析数据
            summary = self._generate_summary_metrics(start_date, end_date)
            patterns = self._analyze_usage_patterns(start_date, end_date)
            insights = self._generate_insights(patterns, summary)
            recommendations = self._generate_recommendations(insights, patterns)
            metrics = self._calculate_performance_metrics(start_date, end_date)

            # 创建分析报告
            report = AnalysisReport(
                report_id=report_id,
                generated_at=end_date,
                analysis_period=(start_date, end_date),
                summary=summary,
                insights=insights,
                patterns=patterns,
                recommendations=recommendations,
                metrics=metrics
            )

            logger.info(f"Analysis complete: {len(insights)} insights, {len(patterns)} patterns")
            return report

        except Exception as e:
            logger.error(f"Failed to generate comprehensive analysis: {e}")
            raise

    def _generate_summary_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """生成摘要指标"""
        try:
            # 查询基础统计数据
            summary_sql = text("""
                SELECT
                    COUNT(DISTINCT o.order_id) as total_orders,
                    COUNT(DISTINCT oi.item_id) as total_items,
                    COUNT(DISTINCT o.mapping_keys) as unique_mapping_configs,
                    AVG(CASE WHEN oi.status = 'COMPLETED' THEN 1.0 ELSE 0.0 END) as success_rate,
                    AVG(oi.processing_time_seconds) as avg_processing_time
                FROM ocr_orders o
                LEFT JOIN ocr_order_items oi ON o.order_id = oi.order_id
                WHERE o.created_at BETWEEN :start_date AND :end_date
            """)

            result = self.db.execute(summary_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchone()

            # 查询映射键使用统计
            mapping_keys_sql = text("""
                SELECT
                    jsonb_array_elements_text(mapping_keys) as mapping_key,
                    COUNT(*) as usage_count
                FROM ocr_orders
                WHERE created_at BETWEEN :start_date AND :end_date
                    AND mapping_keys IS NOT NULL
                GROUP BY mapping_key
                ORDER BY usage_count DESC
                LIMIT 10
            """)

            mapping_keys_result = self.db.execute(mapping_keys_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()

            return {
                'total_orders': result[0] if result[0] else 0,
                'total_items': result[1] if result[1] else 0,
                'unique_mapping_configs': result[2] if result[2] else 0,
                'overall_success_rate': round(result[3] * 100, 2) if result[3] else 0,
                'avg_processing_time': round(result[4], 2) if result[4] else 0,
                'top_mapping_keys': [
                    {'key': row[0], 'usage_count': row[1]}
                    for row in mapping_keys_result
                ],
                'analysis_period_days': (end_date - start_date).days
            }

        except Exception as e:
            logger.error(f"Failed to generate summary metrics: {e}")
            return {}

    def _analyze_usage_patterns(self, start_date: datetime, end_date: datetime) -> List[MappingUsagePattern]:
        """分析使用模式"""
        try:
            patterns = []

            # 查询详细的映射键使用数据
            pattern_sql = text("""
                SELECT
                    jsonb_array_elements_text(o.mapping_keys) as mapping_key,
                    COUNT(*) as frequency,
                    array_agg(DISTINCT c.company_code) as companies,
                    array_agg(DISTINCT dt.type_code) as doc_types,
                    AVG(CASE WHEN oi.status = 'COMPLETED' THEN 1.0 ELSE 0.0 END) as success_rate,
                    AVG(oi.processing_time_seconds) as avg_processing_time,
                    MAX(o.created_at) as last_used
                FROM ocr_orders o
                LEFT JOIN ocr_order_items oi ON o.order_id = oi.order_id
                LEFT JOIN companies c ON oi.company_id = c.company_id
                LEFT JOIN document_types dt ON oi.doc_type_id = dt.doc_type_id
                WHERE o.created_at BETWEEN :start_date AND :end_date
                    AND o.mapping_keys IS NOT NULL
                GROUP BY mapping_key
                HAVING COUNT(*) >= 2
                ORDER BY frequency DESC
            """)

            result = self.db.execute(pattern_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()

            for row in result:
                pattern = MappingUsagePattern(
                    mapping_key=row[0],
                    frequency=row[1],
                    companies=set(row[2]) if row[2] else set(),
                    doc_types=set(row[3]) if row[3] else set(),
                    success_rate=round(row[4] * 100, 2) if row[4] else 0,
                    avg_processing_time=round(row[5], 2) if row[5] else None,
                    last_used=row[6]
                )
                patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Failed to analyze usage patterns: {e}")
            return []

    def _generate_insights(self, patterns: List[MappingUsagePattern], summary: Dict[str, Any]) -> List[MappingInsight]:
        """生成洞察"""
        insights = []

        try:
            # 洞察1: 高频映射键分析
            high_frequency_keys = [p for p in patterns if p.frequency >= 5]
            if high_frequency_keys:
                insights.append(MappingInsight(
                    insight_type="high_frequency",
                    title="高频使用映射键分析",
                    description=f"发现 {len(high_frequency_keys)} 个高频使用的映射键，它们占总使用量的 {sum(p.frequency for p in high_frequency_keys) / sum(p.frequency for p in patterns) * 100:.1f}%",
                    impact_score=85.0,
                    recommendations=[
                        "考虑将高频映射键设为默认选项",
                        "为高频映射键创建快速选择模板",
                        "优化高频映射键的处理算法"
                    ],
                    affected_items=[
                        {
                            'mapping_key': p.mapping_key,
                            'frequency': p.frequency,
                            'success_rate': p.success_rate
                        }
                        for p in high_frequency_keys[:5]
                    ],
                    data_points={
                        'total_high_frequency_keys': len(high_frequency_keys),
                        'usage_percentage': sum(p.frequency for p in high_frequency_keys) / sum(p.frequency for p in patterns) * 100
                    }
                ))

            # 洞察2: 低成功率映射键
            low_success_patterns = [p for p in patterns if p.success_rate < 80 and p.frequency >= 3]
            if low_success_patterns:
                insights.append(MappingInsight(
                    insight_type="low_success_rate",
                    title="低成功率映射键识别",
                    description=f"发现 {len(low_success_patterns)} 个成功率较低的映射键需要优化",
                    impact_score=75.0,
                    recommendations=[
                        "检查这些映射键的配置和schema",
                        "提供更好的映射键使用指导",
                        "考虑改进OCR算法对这些字段的识别"
                    ],
                    affected_items=[
                        {
                            'mapping_key': p.mapping_key,
                            'success_rate': p.success_rate,
                            'frequency': p.frequency
                        }
                        for p in low_success_patterns
                    ],
                    data_points={
                        'avg_success_rate': sum(p.success_rate for p in low_success_patterns) / len(low_success_patterns)
                    }
                ))

            # 洞察3: 映射键多样性分析
            if patterns:
                unique_keys = len(patterns)
                total_usage = sum(p.frequency for p in patterns)
                diversity_score = unique_keys / total_usage * 100

                insights.append(MappingInsight(
                    insight_type="diversity_analysis",
                    title="映射键多样性分析",
                    description=f"系统中使用了 {unique_keys} 种不同的映射键，多样性指数为 {diversity_score:.2f}",
                    impact_score=60.0,
                    recommendations=[
                        "如果多样性过高，考虑标准化常用映射键",
                        "提供映射键推荐系统",
                        "创建映射键最佳实践指南"
                    ],
                    affected_items=[],
                    data_points={
                        'unique_keys': unique_keys,
                        'diversity_score': diversity_score,
                        'total_usage': total_usage
                    }
                ))

            # 洞察4: 跨公司映射一致性
            cross_company_keys = [p for p in patterns if len(p.companies) >= 2]
            if cross_company_keys:
                insights.append(MappingInsight(
                    insight_type="cross_company_consistency",
                    title="跨公司映射一致性分析",
                    description=f"发现 {len(cross_company_keys)} 个映射键被多个公司使用，显示良好的标准化趋势",
                    impact_score=70.0,
                    recommendations=[
                        "推广这些通用映射键作为行业标准",
                        "为新公司提供标准映射键模板",
                        "建立映射键标准化指南"
                    ],
                    affected_items=[
                        {
                            'mapping_key': p.mapping_key,
                            'companies': list(p.companies),
                            'company_count': len(p.companies)
                        }
                        for p in cross_company_keys[:10]
                    ],
                    data_points={
                        'cross_company_keys': len(cross_company_keys)
                    }
                ))

        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")

        return insights

    def _generate_recommendations(self, insights: List[MappingInsight], patterns: List[MappingUsagePattern]) -> List[str]:
        """生成总体建议"""
        recommendations = []

        try:
            # 基于洞察生成建议
            if any(insight.insight_type == "high_frequency" for insight in insights):
                recommendations.append("建议实施映射键模板系统，为高频使用的映射键提供快速选择")

            if any(insight.insight_type == "low_success_rate" for insight in insights):
                recommendations.append("优先处理低成功率映射键的配置问题，提升整体处理质量")

            if any(insight.insight_type == "diversity_analysis" for insight in insights):
                recommendations.append("考虑建立映射键标准化流程，减少不必要的多样性")

            if any(insight.insight_type == "cross_company_consistency" for insight in insights):
                recommendations.append("推广跨公司通用映射键，建立行业标准")

            # 基于模式生成建议
            if patterns:
                avg_success_rate = sum(p.success_rate for p in patterns) / len(patterns)
                if avg_success_rate < 85:
                    recommendations.append("整体成功率需要提升，建议检查OCR算法和映射配置")

                processing_times = [p.avg_processing_time for p in patterns if p.avg_processing_time]
                if processing_times:
                    avg_time = sum(processing_times) / len(processing_times)
                    if avg_time > 60:  # 超过60秒
                        recommendations.append("处理时间较长，建议优化处理算法和系统性能")

            # 通用建议
            recommendations.extend([
                "定期进行映射使用分析，持续优化系统配置",
                "建立映射键使用指南和最佳实践文档",
                "考虑实施智能映射键推荐系统"
            ])

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")

        return recommendations

    def _calculate_performance_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """计算性能指标"""
        try:
            metrics = {}

            # 处理时间指标
            time_sql = text("""
                SELECT
                    AVG(processing_time_seconds) as avg_time,
                    MIN(processing_time_seconds) as min_time,
                    MAX(processing_time_seconds) as max_time,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_time_seconds) as median_time,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_time_seconds) as p95_time
                FROM ocr_order_items
                WHERE processing_started_at BETWEEN :start_date AND :end_date
                    AND processing_time_seconds IS NOT NULL
            """)

            time_result = self.db.execute(time_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchone()

            if time_result and time_result[0]:
                metrics['processing_time'] = {
                    'average': round(time_result[0], 2),
                    'minimum': round(time_result[1], 2),
                    'maximum': round(time_result[2], 2),
                    'median': round(time_result[3], 2),
                    'p95': round(time_result[4], 2)
                }

            # 成功率指标
            success_sql = text("""
                SELECT
                    status,
                    COUNT(*) as count
                FROM ocr_order_items
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY status
            """)

            success_result = self.db.execute(success_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()

            status_counts = dict(success_result)
            total_items = sum(status_counts.values())

            if total_items > 0:
                metrics['success_metrics'] = {
                    'total_items': total_items,
                    'completed': status_counts.get('COMPLETED', 0),
                    'failed': status_counts.get('FAILED', 0),
                    'success_rate': round(status_counts.get('COMPLETED', 0) / total_items * 100, 2)
                }

            # 映射键效率指标
            efficiency_sql = text("""
                SELECT
                    jsonb_array_elements_text(o.mapping_keys) as mapping_key,
                    AVG(oi.processing_time_seconds) as avg_processing_time,
                    AVG(CASE WHEN oi.status = 'COMPLETED' THEN 1.0 ELSE 0.0 END) as success_rate
                FROM ocr_orders o
                JOIN ocr_order_items oi ON o.order_id = oi.order_id
                WHERE o.created_at BETWEEN :start_date AND :end_date
                    AND o.mapping_keys IS NOT NULL
                    AND oi.processing_time_seconds IS NOT NULL
                GROUP BY mapping_key
                HAVING COUNT(*) >= 3
                ORDER BY success_rate DESC, avg_processing_time ASC
                LIMIT 10
            """)

            efficiency_result = self.db.execute(efficiency_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()

            metrics['efficiency_ranking'] = [
                {
                    'mapping_key': row[0],
                    'avg_processing_time': round(row[1], 2),
                    'success_rate': round(row[2] * 100, 2)
                }
                for row in efficiency_result
            ]

            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate performance metrics: {e}")
            return {}

    def analyze_mapping_trends(self, days_back: int = 90) -> Dict[str, Any]:
        """分析映射趋势"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # 时间序列分析
            trend_sql = text("""
                SELECT
                    DATE(o.created_at) as date,
                    COUNT(DISTINCT o.order_id) as orders,
                    COUNT(DISTINCT oi.item_id) as items,
                    AVG(CASE WHEN oi.status = 'COMPLETED' THEN 1.0 ELSE 0.0 END) as success_rate,
                    AVG(oi.processing_time_seconds) as avg_processing_time
                FROM ocr_orders o
                LEFT JOIN ocr_order_items oi ON o.order_id = oi.order_id
                WHERE o.created_at BETWEEN :start_date AND :end_date
                GROUP BY DATE(o.created_at)
                ORDER BY date
            """)

            trend_result = self.db.execute(trend_sql, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()

            trends = {
                'daily_stats': [
                    {
                        'date': row[0].isoformat(),
                        'orders': row[1],
                        'items': row[2],
                        'success_rate': round(row[3] * 100, 2) if row[3] else 0,
                        'avg_processing_time': round(row[4], 2) if row[4] else 0
                    }
                    for row in trend_result
                ],
                'analysis_period': f"{start_date.date()} to {end_date.date()}"
            }

            # 计算趋势指标
            if len(trends['daily_stats']) >= 7:
                recent_week = trends['daily_stats'][-7:]
                previous_week = trends['daily_stats'][-14:-7] if len(trends['daily_stats']) >= 14 else None

                trends['trend_analysis'] = {
                    'recent_avg_success_rate': sum(day['success_rate'] for day in recent_week) / len(recent_week),
                    'recent_avg_processing_time': sum(day['avg_processing_time'] for day in recent_week) / len(recent_week)
                }

                if previous_week:
                    prev_success_rate = sum(day['success_rate'] for day in previous_week) / len(previous_week)
                    prev_processing_time = sum(day['avg_processing_time'] for day in previous_week) / len(previous_week)

                    trends['trend_analysis'].update({
                        'success_rate_trend': trends['trend_analysis']['recent_avg_success_rate'] - prev_success_rate,
                        'processing_time_trend': trends['trend_analysis']['recent_avg_processing_time'] - prev_processing_time
                    })

            return trends

        except Exception as e:
            logger.error(f"Failed to analyze mapping trends: {e}")
            return {}

    def generate_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """生成优化建议"""
        try:
            suggestions = []

            # 基于历史数据生成优化建议
            recent_analysis = self.generate_comprehensive_analysis(analysis_period_days=7)

            # 处理时间优化建议
            if recent_analysis.metrics.get('processing_time', {}).get('average', 0) > 30:
                suggestions.append({
                    'category': 'performance',
                    'priority': 'high',
                    'title': '处理时间优化',
                    'description': '平均处理时间超过30秒，建议优化',
                    'action_items': [
                        '检查OCR算法性能',
                        '优化映射配置',
                        '考虑并行处理'
                    ],
                    'expected_impact': '处理时间减少20-40%'
                })

            # 成功率优化建议
            success_rate = recent_analysis.metrics.get('success_metrics', {}).get('success_rate', 100)
            if success_rate < 90:
                suggestions.append({
                    'category': 'quality',
                    'priority': 'high',
                    'title': '成功率提升',
                    'description': f'当前成功率为{success_rate}%，建议提升至95%以上',
                    'action_items': [
                        '分析失败案例',
                        '改进映射键配置',
                        '优化文档预处理'
                    ],
                    'expected_impact': '成功率提升至95%以上'
                })

            # 映射标准化建议
            if len(recent_analysis.patterns) > 20:
                suggestions.append({
                    'category': 'standardization',
                    'priority': 'medium',
                    'title': '映射键标准化',
                    'description': '映射键种类较多，建议标准化',
                    'action_items': [
                        '建立标准映射键库',
                        '提供映射键模板',
                        '实施最佳实践指南'
                    ],
                    'expected_impact': '减少配置复杂度，提升一致性'
                })

            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            return []