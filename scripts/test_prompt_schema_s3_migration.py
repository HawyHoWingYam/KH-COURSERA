"""
Comprehensive Test Suite for Prompt and Schema S3 Migration
测试prompt和schema S3迁移的完整测试套件

涵盖的测试范围:
- S3StorageManager prompt/schema方法
- PromptSchemaManager功能测试
- 配置加载和验证
- API端点测试
- 迁移脚本测试
- 集成测试
"""

import pytest
import asyncio
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any
import boto3
from moto import mock_s3

# 添加项目路径
import sys
project_root = Path(__file__).parent.parent
backend_path = project_root / "GeminiOCR" / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from utils.s3_storage import S3StorageManager
from utils.prompt_schema_manager import (
    PromptSchemaManager, 
    PromptSchemaValidator, 
    PromptSchemaCache,
    get_prompt_schema_manager,
    load_prompt_and_schema
)


class TestS3StorageManagerPromptSchema:
    """测试S3StorageManager的prompt和schema方法"""
    
    @pytest.fixture
    def s3_manager(self):
        """创建S3管理器实例"""
        with mock_s3():
            # 创建模拟的S3客户端
            boto3.client('s3', region_name='ap-southeast-1').create_bucket(
                Bucket='test-bucket',
                CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
            )
            
            manager = S3StorageManager('test-bucket', 'ap-southeast-1')
            yield manager
    
    @pytest.mark.asyncio
    async def test_upload_prompt_success(self, s3_manager):
        """测试成功上传prompt"""
        content = "Please extract the following information from the invoice document..."
        metadata = {"created_by": "test", "version": "1.0"}
        
        with mock_s3():
            result = s3_manager.upload_prompt("TEST_COMPANY", "INVOICE", content, "test_prompt.txt", metadata)
            
            assert result is not None
            assert result == "TEST_COMPANY/INVOICE/test_prompt.txt"
    
    @pytest.mark.asyncio
    async def test_get_prompt_success(self, s3_manager):
        """测试成功获取prompt"""
        content = "Test prompt content"
        
        with mock_s3():
            # 先上传
            s3_manager.upload_prompt("TEST_COMPANY", "INVOICE", content)
            
            # 再获取
            retrieved_content = s3_manager.get_prompt("TEST_COMPANY", "INVOICE")
            
            assert retrieved_content == content
    
    @pytest.mark.asyncio
    async def test_upload_schema_success(self, s3_manager):
        """测试成功上传schema"""
        schema_data = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "number"}
            }
        }
        
        with mock_s3():
            result = s3_manager.upload_schema("TEST_COMPANY", "INVOICE", schema_data)
            
            assert result is not None
            assert result == "TEST_COMPANY/INVOICE/schema.json"
    
    @pytest.mark.asyncio
    async def test_get_schema_success(self, s3_manager):
        """测试成功获取schema"""
        schema_data = {
            "type": "object",
            "properties": {"test": {"type": "string"}}
        }
        
        with mock_s3():
            # 先上传
            s3_manager.upload_schema("TEST_COMPANY", "INVOICE", schema_data)
            
            # 再获取
            retrieved_schema = s3_manager.get_schema("TEST_COMPANY", "INVOICE")
            
            assert retrieved_schema == schema_data
    
    @pytest.mark.asyncio
    async def test_prompt_exists(self, s3_manager):
        """测试检查prompt是否存在"""
        with mock_s3():
            # 不存在的情况
            assert not s3_manager.prompt_exists("NONEXISTENT", "TYPE")
            
            # 上传后存在
            s3_manager.upload_prompt("TEST_COMPANY", "INVOICE", "test content")
            assert s3_manager.prompt_exists("TEST_COMPANY", "INVOICE")
    
    @pytest.mark.asyncio
    async def test_list_prompts(self, s3_manager):
        """测试列出prompts"""
        with mock_s3():
            # 上传几个prompts
            s3_manager.upload_prompt("COMPANY_A", "INVOICE", "content1")
            s3_manager.upload_prompt("COMPANY_A", "RECEIPT", "content2")
            s3_manager.upload_prompt("COMPANY_B", "INVOICE", "content3")
            
            # 列出所有prompts
            all_prompts = s3_manager.list_prompts()
            assert len(all_prompts) >= 3
            
            # 列出特定公司的prompts
            company_a_prompts = s3_manager.list_prompts("COMPANY_A")
            assert len(company_a_prompts) >= 2


class TestPromptSchemaValidator:
    """测试PromptSchemaValidator"""
    
    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        return PromptSchemaValidator()
    
    def test_validate_prompt_success(self, validator):
        """测试成功验证prompt"""
        valid_prompt = "Please extract the invoice information from the document and identify the key fields."
        
        is_valid, message = validator.validate_prompt(valid_prompt)
        
        assert is_valid is True
        assert "验证通过" in message
    
    def test_validate_prompt_too_short(self, validator):
        """测试prompt过短"""
        short_prompt = "test"
        
        is_valid, message = validator.validate_prompt(short_prompt)
        
        assert is_valid is False
        assert "过短" in message
    
    def test_validate_prompt_missing_keywords(self, validator):
        """测试prompt缺少关键词"""
        # 配置严格模式
        validator.update_config({"strict_mode": True, "required_prompt_keywords": ["extract"]})
        
        invalid_prompt = "This is a very long prompt but it doesn't contain the required instruction keywords needed for processing."
        
        is_valid, message = validator.validate_prompt(invalid_prompt)
        
        assert is_valid is False
        assert "关键词" in message
    
    def test_validate_schema_success(self, validator):
        """测试成功验证schema"""
        valid_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            }
        }
        
        is_valid, message = validator.validate_schema(valid_schema)
        
        assert is_valid is True
        assert "验证通过" in message
    
    def test_validate_schema_missing_fields(self, validator):
        """测试schema缺少必需字段"""
        invalid_schema = {
            "properties": {
                "name": {"type": "string"}
            }
            # 缺少 "type" 字段
        }
        
        is_valid, message = validator.validate_schema(invalid_schema)
        
        assert is_valid is False
        assert "缺少必需字段" in message
    
    def test_validator_config_update(self, validator):
        """测试验证器配置更新"""
        new_config = {
            "prompt_min_length": 20,
            "prompt_max_length": 1000,
            "strict_mode": False
        }
        
        validator.update_config(new_config)
        
        assert validator.config["prompt_min_length"] == 20
        assert validator.config["prompt_max_length"] == 1000
        assert validator.config["strict_mode"] is False


class TestPromptSchemaCache:
    """测试PromptSchemaCache"""
    
    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return PromptSchemaCache(max_size=3, ttl_minutes=1)
    
    def test_cache_set_and_get(self, cache):
        """测试缓存设置和获取"""
        cache.set("COMPANY", "TYPE", "prompt", "test.txt", "test content")
        
        result = cache.get("COMPANY", "TYPE", "prompt", "test.txt")
        
        assert result == "test content"
    
    def test_cache_miss(self, cache):
        """测试缓存未命中"""
        result = cache.get("NONEXISTENT", "TYPE", "prompt", "test.txt")
        
        assert result is None
    
    def test_cache_size_limit(self, cache):
        """测试缓存大小限制"""
        # 添加超过最大大小的项目
        for i in range(5):
            cache.set(f"COMPANY_{i}", "TYPE", "prompt", "test.txt", f"content_{i}")
        
        # 缓存应该只保留最后3个
        assert len(cache.cache) == 3
        
        # 最早的应该被删除
        assert cache.get("COMPANY_0", "TYPE", "prompt", "test.txt") is None
        assert cache.get("COMPANY_4", "TYPE", "prompt", "test.txt") == "content_4"
    
    def test_cache_invalidation(self, cache):
        """测试缓存失效"""
        cache.set("COMPANY", "TYPE1", "prompt", "test.txt", "content1")
        cache.set("COMPANY", "TYPE2", "prompt", "test.txt", "content2")
        cache.set("OTHER", "TYPE1", "prompt", "test.txt", "content3")
        
        # 失效特定公司和类型
        cache.invalidate("COMPANY", "TYPE1")
        
        assert cache.get("COMPANY", "TYPE1", "prompt", "test.txt") is None
        assert cache.get("COMPANY", "TYPE2", "prompt", "test.txt") == "content2"
        assert cache.get("OTHER", "TYPE1", "prompt", "test.txt") == "content3"
    
    def test_cache_stats(self, cache):
        """测试缓存统计"""
        cache.set("COMPANY", "TYPE", "prompt", "test.txt", "content")
        
        stats = cache.get_stats()
        
        assert stats["total_items"] == 1
        assert stats["max_size"] == 3
        assert len(stats["items"]) == 1


class TestPromptSchemaManager:
    """测试PromptSchemaManager"""
    
    @pytest.fixture
    def temp_config(self):
        """创建临时配置"""
        return {
            "storage_backend": "local",
            "cache": {"enabled": True, "max_size": 10, "ttl_minutes": 5},
            "local_backup": {"enabled": True, "path": "/tmp/test_backup"},
            "validation": {"strict_mode": False},
            "performance": {"thread_pool_size": 2}
        }
    
    @pytest.fixture
    def manager(self, temp_config):
        """创建PromptSchemaManager实例"""
        with patch('utils.prompt_schema_manager.get_s3_manager', return_value=None):
            return PromptSchemaManager(config=temp_config)
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert manager.config["storage_backend"] == "local"
        assert manager.cache is not None
        assert manager.validator is not None
        assert manager.executor is not None
    
    @pytest.mark.asyncio
    async def test_get_prompt_from_backup(self, manager):
        """测试从本地备份获取prompt"""
        # 创建测试文件
        test_path = manager.local_backup_path / "TEST_COMPANY" / "INVOICE" / "prompt" / "prompt.txt"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("Test prompt content", encoding="utf-8")
        
        try:
            content = await manager.get_prompt("TEST_COMPANY", "INVOICE")
            assert content == "Test prompt content"
        finally:
            # 清理
            import shutil
            if test_path.parent.parent.parent.parent.exists():
                shutil.rmtree(test_path.parent.parent.parent.parent)
    
    @pytest.mark.asyncio
    async def test_upload_prompt_validation_failure(self, manager):
        """测试上传prompt时验证失败"""
        # 配置严格验证
        manager.validator.update_config({"strict_mode": True, "prompt_min_length": 100})
        
        short_content = "Too short"
        
        result = await manager.upload_prompt("TEST_COMPANY", "INVOICE", short_content)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_status(self, manager):
        """测试健康状态"""
        status = manager.get_health_status()
        
        assert "status" in status
        assert "cache" in status
        assert "local_backup_path" in status


class TestConfigIntegration:
    """测试配置集成"""
    
    def test_config_loading(self):
        """测试配置加载"""
        # 模拟config_loader
        mock_config = {
            "storage_backend": "s3",
            "cache": {"enabled": True, "max_size": 50},
            "s3": {"enabled": True, "bucket_name": "test-bucket"},
            "validation": {"strict_mode": True}
        }
        
        with patch('config_loader.config_loader') as mock_loader:
            mock_loader.get_prompt_schema_config.return_value = mock_config
            
            manager = PromptSchemaManager()
            
            assert manager.config["storage_backend"] == "s3"
            assert manager.config["cache"]["max_size"] == 50


class TestAPIEndpoints:
    """测试API端点（模拟测试）"""
    
    @pytest.fixture
    def mock_manager(self):
        """创建模拟的PromptSchemaManager"""
        manager = Mock()
        manager.get_prompt = AsyncMock(return_value="Test prompt content")
        manager.get_schema = AsyncMock(return_value={"type": "object", "properties": {}})
        manager.upload_prompt = AsyncMock(return_value=True)
        manager.upload_schema = AsyncMock(return_value=True)
        manager.get_health_status.return_value = {"status": "healthy"}
        manager.list_available_templates = AsyncMock(return_value={"prompts": [], "schemas": []})
        return manager
    
    @pytest.mark.asyncio
    async def test_get_prompt_endpoint_success(self, mock_manager):
        """测试获取prompt端点成功情况"""
        # 模拟API调用
        company_code = "TEST_COMPANY"
        doc_type_code = "INVOICE"
        
        result = await mock_manager.get_prompt(company_code, doc_type_code)
        
        assert result == "Test prompt content"
        mock_manager.get_prompt.assert_called_once_with(company_code, doc_type_code, "prompt.txt")
    
    @pytest.mark.asyncio
    async def test_upload_prompt_endpoint_success(self, mock_manager):
        """测试上传prompt端点成功情况"""
        company_code = "TEST_COMPANY"
        doc_type_code = "INVOICE"
        content = "New prompt content"
        
        result = await mock_manager.upload_prompt(company_code, doc_type_code, content)
        
        assert result is True
        mock_manager.upload_prompt.assert_called_once()


class TestMigrationScript:
    """测试迁移脚本（集成测试）"""
    
    @pytest.fixture
    def temp_uploads_dir(self):
        """创建临时uploads目录结构"""
        with tempfile.TemporaryDirectory() as temp_dir:
            uploads_dir = Path(temp_dir) / "uploads" / "document_type"
            
            # 创建测试文件结构
            company_dir = uploads_dir / "INVOICE" / "TEST_COMPANY"
            company_dir.mkdir(parents=True)
            
            # 创建prompt文件
            prompt_dir = company_dir / "prompt"
            prompt_dir.mkdir()
            (prompt_dir / "prompt.txt").write_text("Test prompt content")
            
            # 创建schema文件
            schema_dir = company_dir / "schema"
            schema_dir.mkdir()
            (schema_dir / "schema.json").write_text('{"type": "object", "properties": {}}')
            
            yield uploads_dir
    
    def test_discover_files(self, temp_uploads_dir):
        """测试文件发现功能"""
        # 这里应该导入并测试迁移脚本的文件发现功能
        # 由于迁移脚本是独立的，我们可以测试其核心逻辑
        
        found_files = []
        for doc_type_dir in temp_uploads_dir.iterdir():
            if doc_type_dir.is_dir():
                for provider_dir in doc_type_dir.iterdir():
                    if provider_dir.is_dir():
                        prompt_dir = provider_dir / "prompt"
                        if prompt_dir.exists():
                            for prompt_file in prompt_dir.glob("*.txt"):
                                found_files.append({
                                    "file_path": prompt_file,
                                    "file_type": "prompt",
                                    "doc_type": doc_type_dir.name,
                                    "provider": provider_dir.name
                                })
                        
                        schema_dir = provider_dir / "schema"
                        if schema_dir.exists():
                            for schema_file in schema_dir.glob("*.json"):
                                found_files.append({
                                    "file_path": schema_file,
                                    "file_type": "schema",
                                    "doc_type": doc_type_dir.name,
                                    "provider": provider_dir.name
                                })
        
        assert len(found_files) == 2  # 1 prompt + 1 schema
        assert any(f["file_type"] == "prompt" for f in found_files)
        assert any(f["file_type"] == "schema" for f in found_files)


@pytest.mark.integration
class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_flow(self):
        """测试端到端流程"""
        # 测试完整的流程：配置加载 -> 管理器初始化 -> 文件操作
        config = {
            "storage_backend": "local",
            "cache": {"enabled": True, "max_size": 10, "ttl_minutes": 5},
            "local_backup": {"enabled": True, "path": "/tmp/integration_test"},
            "validation": {"strict_mode": False}
        }
        
        with patch('utils.prompt_schema_manager.get_s3_manager', return_value=None):
            manager = PromptSchemaManager(config=config)
            
            # 测试上传
            prompt_content = "Please extract information from the document and identify key fields."
            schema_data = {"type": "object", "properties": {"test": {"type": "string"}}}
            
            # 由于是本地模式，这些操作应该主要使用本地备份
            prompt_result = await manager.upload_prompt("TEST_COMPANY", "INVOICE", prompt_content)
            schema_result = await manager.upload_schema("TEST_COMPANY", "INVOICE", schema_data)
            
            # 在本地模式下，即使S3上传失败，本地备份成功也应该返回True
            assert prompt_result is True
            assert schema_result is True
            
            # 测试检索
            retrieved_prompt = await manager.get_prompt("TEST_COMPANY", "INVOICE")
            retrieved_schema = await manager.get_schema("TEST_COMPANY", "INVOICE")
            
            assert retrieved_prompt == prompt_content
            assert retrieved_schema == schema_data
            
            # 清理
            import shutil
            if manager.local_backup_path.exists():
                shutil.rmtree(manager.local_backup_path)


# 运行特定的测试套件
if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])
    
    # 或者运行特定的测试类
    # pytest.main([f"{__file__}::TestS3StorageManagerPromptSchema", "-v"])
    
    # 运行集成测试
    # pytest.main([f"{__file__}::TestIntegration", "-v", "-m", "integration"])