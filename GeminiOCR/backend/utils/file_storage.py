import os
import shutil
import logging
from typing import Optional, Union, BinaryIO
from pathlib import Path
from datetime import datetime
import tempfile
import uuid

from .s3_storage import get_s3_manager, is_s3_enabled, S3StorageManager

logger = logging.getLogger(__name__)

class FileStorageService:
    """统一的文件存储服务，支持本地存储和S3存储"""
    
    def __init__(self):
        self.s3_manager = get_s3_manager()
        self.use_s3 = is_s3_enabled()
        self.local_upload_dir = "uploads"
        
        # 确保本地上传目录存在
        if not self.use_s3:
            os.makedirs(self.local_upload_dir, exist_ok=True)
            
        logger.info(f"📁 文件存储服务初始化完成，使用{'S3' if self.use_s3 else '本地'}存储")
    
    def save_uploaded_file(self, 
                          uploaded_file, 
                          company_code: str, 
                          doc_type_code: str, 
                          job_id: Optional[int] = None) -> tuple[str, str]:
        """
        保存上传的文件
        
        Args:
            uploaded_file: FastAPI UploadFile对象
            company_code: 公司代码
            doc_type_code: 文档类型代码
            job_id: 任务ID（可选）
            
        Returns:
            tuple[str, str]: (存储路径, 显示名称)
        """
        filename = uploaded_file.filename
        
        if self.use_s3:
            return self._save_to_s3(uploaded_file, company_code, doc_type_code, filename, job_id)
        else:
            return self._save_to_local(uploaded_file, company_code, doc_type_code, filename, job_id)
    
    def _save_to_s3(self, uploaded_file, company_code: str, doc_type_code: str, 
                   filename: str, job_id: Optional[int] = None) -> tuple[str, str]:
        """保存文件到S3"""
        try:
            # 生成S3键名
            s3_key = S3StorageManager.generate_file_key(
                company_code, doc_type_code, filename, job_id
            )
            
            # 准备元数据
            metadata = {
                'company_code': company_code,
                'doc_type_code': doc_type_code,
                'original_filename': filename,
                'upload_time': datetime.now().isoformat()
            }
            
            if job_id:
                metadata['job_id'] = str(job_id)
            
            # 上传到S3
            success = self.s3_manager.upload_file(
                uploaded_file.file, 
                s3_key, 
                content_type=uploaded_file.content_type,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ 文件已上传到S3：{s3_key}")
                return f"s3://{self.s3_manager.bucket_name}/{s3_key}", filename
            else:
                raise Exception("S3上传失败")
                
        except Exception as e:
            logger.error(f"❌ S3文件上传失败：{e}")
            # 回退到本地存储
            logger.info("🔄 回退到本地存储")
            return self._save_to_local(uploaded_file, company_code, doc_type_code, filename, job_id)
    
    def _save_to_local(self, uploaded_file, company_code: str, doc_type_code: str, 
                      filename: str, job_id: Optional[int] = None) -> tuple[str, str]:
        """保存文件到本地"""
        try:
            # 构建本地文件路径
            if job_id:
                local_dir = os.path.join(self.local_upload_dir, company_code, doc_type_code, "jobs")
            else:
                local_dir = os.path.join(self.local_upload_dir, company_code, doc_type_code)
            
            os.makedirs(local_dir, exist_ok=True)
            
            # 生成唯一文件名避免冲突
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            unique_filename = f"{timestamp}_{unique_id}_{safe_filename}"
            
            file_path = os.path.join(local_dir, unique_filename)
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            
            logger.info(f"✅ 文件已保存到本地：{file_path}")
            return file_path, filename
            
        except Exception as e:
            logger.error(f"❌ 本地文件保存失败：{e}")
            raise
    
    def read_file(self, file_path: str) -> Optional[bytes]:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径（可以是本地路径或S3 URL）
            
        Returns:
            Optional[bytes]: 文件内容
        """
        if file_path.startswith('s3://'):
            return self._read_from_s3(file_path)
        else:
            return self._read_from_local(file_path)
    
    def _read_from_s3(self, s3_url: str) -> Optional[bytes]:
        """从S3读取文件"""
        try:
            # 解析S3 URL
            # s3://bucket-name/key/path
            s3_url = s3_url[5:]  # 移除 's3://'
            parts = s3_url.split('/', 1)
            if len(parts) != 2:
                raise ValueError("无效的S3 URL格式")
            
            bucket_name, key = parts
            
            if self.s3_manager and self.s3_manager.bucket_name == bucket_name:
                return self.s3_manager.download_file(key)
            else:
                logger.error(f"❌ S3存储桶不匹配：{bucket_name} vs {self.s3_manager.bucket_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 从S3读取文件失败：{e}")
            return None
    
    def _read_from_local(self, file_path: str) -> Optional[bytes]:
        """从本地读取文件"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return f.read()
            else:
                logger.warning(f"⚠️ 本地文件不存在：{file_path}")
                return None
        except Exception as e:
            logger.error(f"❌ 从本地读取文件失败：{e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径（可以是本地路径或S3 URL）
            
        Returns:
            bool: 删除是否成功
        """
        if file_path.startswith('s3://'):
            return self._delete_from_s3(file_path)
        else:
            return self._delete_from_local(file_path)
    
    def _delete_from_s3(self, s3_url: str) -> bool:
        """从S3删除文件"""
        try:
            # 解析S3 URL
            s3_url = s3_url[5:]  # 移除 's3://'
            parts = s3_url.split('/', 1)
            if len(parts) != 2:
                raise ValueError("无效的S3 URL格式")
            
            bucket_name, key = parts
            
            if self.s3_manager and self.s3_manager.bucket_name == bucket_name:
                return self.s3_manager.delete_file(key)
            else:
                logger.error(f"❌ S3存储桶不匹配：{bucket_name} vs {self.s3_manager.bucket_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 从S3删除文件失败：{e}")
            return False
    
    def _delete_from_local(self, file_path: str) -> bool:
        """从本地删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"✅ 本地文件删除成功：{file_path}")
                return True
            else:
                logger.warning(f"⚠️ 本地文件不存在，无需删除：{file_path}")
                return True
        except Exception as e:
            logger.error(f"❌ 本地文件删除失败：{e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径（可以是本地路径或S3 URL）
            
        Returns:
            bool: 文件是否存在
        """
        if file_path.startswith('s3://'):
            return self._s3_file_exists(file_path)
        else:
            return os.path.exists(file_path)
    
    def _s3_file_exists(self, s3_url: str) -> bool:
        """检查S3文件是否存在"""
        try:
            # 解析S3 URL
            s3_url = s3_url[5:]  # 移除 's3://'
            parts = s3_url.split('/', 1)
            if len(parts) != 2:
                return False
            
            bucket_name, key = parts
            
            if self.s3_manager and self.s3_manager.bucket_name == bucket_name:
                return self.s3_manager.file_exists(key)
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ 检查S3文件存在时出错：{e}")
            return False
    
    def get_file_size(self, file_path: str) -> int:
        """
        获取文件大小
        
        Args:
            file_path: 文件路径（可以是本地路径或S3 URL）
            
        Returns:
            int: 文件大小（字节）
        """
        if file_path.startswith('s3://'):
            return self._get_s3_file_size(file_path)
        else:
            try:
                return os.path.getsize(file_path) if os.path.exists(file_path) else 0
            except:
                return 0
    
    def _get_s3_file_size(self, s3_url: str) -> int:
        """获取S3文件大小"""
        try:
            # 解析S3 URL
            s3_url = s3_url[5:]  # 移除 's3://'
            parts = s3_url.split('/', 1)
            if len(parts) != 2:
                return 0
            
            bucket_name, key = parts
            
            if self.s3_manager and self.s3_manager.bucket_name == bucket_name:
                file_info = self.s3_manager.get_file_info(key)
                return file_info.get('size', 0) if file_info else 0
            else:
                return 0
                
        except Exception as e:
            logger.error(f"❌ 获取S3文件大小失败：{e}")
            return 0
    
    def create_temp_file_from_storage(self, file_path: str) -> Optional[str]:
        """
        从存储中创建临时文件（用于需要本地文件路径的操作）
        
        Args:
            file_path: 文件路径（可以是本地路径或S3 URL）
            
        Returns:
            Optional[str]: 临时文件路径，使用后需要手动删除
        """
        if not file_path.startswith('s3://'):
            # 本地文件直接返回原路径
            return file_path if os.path.exists(file_path) else None
        
        # S3文件需要下载到临时文件
        try:
            content = self.read_file(file_path)
            if content is None:
                return None
            
            # 创建临时文件
            suffix = Path(file_path).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            logger.info(f"✅ 从S3创建临时文件：{temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"❌ 创建临时文件失败：{e}")
            return None
    
    def cleanup_temp_file(self, temp_path: str):
        """清理临时文件"""
        try:
            if temp_path and os.path.exists(temp_path) and temp_path.startswith('/tmp'):
                os.remove(temp_path)
                logger.info(f"✅ 清理临时文件：{temp_path}")
        except Exception as e:
            logger.warning(f"⚠️ 清理临时文件失败：{e}")


# 全局文件存储服务实例
_file_storage_service = None

def get_file_storage() -> FileStorageService:
    """获取全局文件存储服务实例"""
    global _file_storage_service
    
    if _file_storage_service is None:
        _file_storage_service = FileStorageService()
    
    return _file_storage_service