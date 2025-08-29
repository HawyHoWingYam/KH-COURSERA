import boto3
import os
import logging
from typing import Optional, BinaryIO, Union
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime, timedelta
import json
import uuid
import mimetypes

logger = logging.getLogger(__name__)

class S3StorageManager:
    """AWS S3文件存储管理器 - 使用单存储桶多文件夹结构"""
    
    def __init__(self, bucket_name: str, region: str = 'ap-southeast-1'):
        """
        初始化S3存储管理器
        
        Args:
            bucket_name: S3存储桶名称
            region: AWS区域
        """
        self.bucket_name = bucket_name
        self.region = region
        self.upload_prefix = 'upload/'
        self.results_prefix = 'results/'
        self.exports_prefix = 'exports/'
        self._s3_client = None
        self._s3_resource = None
        
    @property
    def s3_client(self):
        """延迟初始化S3客户端"""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client('s3', region_name=self.region)
                logger.info(f"✅ S3客户端初始化成功，区域：{self.region}")
            except Exception as e:
                logger.error(f"❌ S3客户端初始化失败：{e}")
                raise
        return self._s3_client
    
    @property
    def s3_resource(self):
        """延迟初始化S3资源"""
        if self._s3_resource is None:
            try:
                self._s3_resource = boto3.resource('s3', region_name=self.region)
                logger.info(f"✅ S3资源初始化成功，区域：{self.region}")
            except Exception as e:
                logger.error(f"❌ S3资源初始化失败：{e}")
                raise
        return self._s3_resource
    
    def ensure_bucket_exists(self) -> bool:
        """确保S3存储桶存在"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3存储桶已存在：{self.bucket_name}")
            return True
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            
            if error_code == 404:
                # 存储桶不存在，尝试创建
                try:
                    if self.region == 'us-east-1':
                        # us-east-1区域创建存储桶的特殊处理
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    
                    logger.info(f"✅ 成功创建S3存储桶：{self.bucket_name}")
                    return True
                except ClientError as create_error:
                    logger.error(f"❌ 创建S3存储桶失败：{create_error}")
                    return False
            else:
                logger.error(f"❌ 检查S3存储桶时出错：{e}")
                return False
    
    def upload_file(self, 
                   file_content: Union[BinaryIO, bytes], 
                   key: str,
                   content_type: Optional[str] = None,
                   metadata: Optional[dict] = None) -> bool:
        """
        上传文件到S3
        
        Args:
            file_content: 文件内容（文件对象或字节数据）
            key: S3中的文件键名
            content_type: 文件的MIME类型
            metadata: 文件元数据
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 自动推断content_type
            if content_type is None:
                content_type, _ = mimetypes.guess_type(key)
                if content_type is None:
                    content_type = 'application/octet-stream'
            
            # 准备上传参数
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': f"{self.upload_prefix}{key}",
                'ContentType': content_type
            }
            
            # 添加元数据
            if metadata:
                upload_args['Metadata'] = metadata
            
            # 执行上传
            if hasattr(file_content, 'read'):
                # 文件对象 - upload_fileobj 需要单独的参数格式
                extra_args = {
                    'ContentType': content_type
                }
                if metadata:
                    extra_args['Metadata'] = metadata
                
                self.s3_client.upload_fileobj(
                    file_content, 
                    upload_args['Bucket'], 
                    upload_args['Key'], 
                    ExtraArgs=extra_args
                )
            else:
                # 字节数据
                self.s3_client.put_object(Body=file_content, **upload_args)
            
            logger.info(f"✅ 文件上传成功：s3://{self.bucket_name}/{self.upload_prefix}{key}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ 文件上传失败：{e}")
            return False
        except Exception as e:
            logger.error(f"❌ 文件上传时发生未知错误：{e}")
            return False
    
    def save_json_result(self, key: str, data: dict, metadata: Optional[dict] = None) -> bool:
        """
        保存JSON结果到results文件夹
        
        Args:
            key: 文件键名
            data: JSON数据
            metadata: 文件元数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            json_content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            
            upload_args = {
                'Bucket': self.bucket_name,
                'Key': f"{self.results_prefix}{key}",
                'Body': json_content,
                'ContentType': 'application/json',
                'ContentEncoding': 'utf-8'
            }
            
            if metadata:
                upload_args['Metadata'] = metadata
            
            self.s3_client.put_object(**upload_args)
            logger.info(f"✅ JSON结果保存成功：s3://{self.bucket_name}/{self.results_prefix}{key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ JSON结果保存失败：{e}")
            return False
    
    def get_json_result(self, key: str) -> Optional[dict]:
        """
        从results文件夹获取JSON结果
        
        Args:
            key: 文件键名
            
        Returns:
            Optional[dict]: JSON数据，失败时返回None
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{self.results_prefix}{key}")
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            logger.info(f"✅ JSON结果获取成功：s3://{self.bucket_name}/{self.results_prefix}{key}")
            return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"⚠️ JSON文件不存在：s3://{self.bucket_name}/{self.results_prefix}{key}")
            else:
                logger.error(f"❌ JSON结果获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ JSON结果获取时发生未知错误：{e}")
            return None

    def save_excel_export(self, key: str, file_content: Union[BinaryIO, bytes], metadata: Optional[dict] = None) -> bool:
        """
        保存Excel文件到exports文件夹
        
        Args:
            key: 文件键名
            file_content: Excel文件内容
            metadata: 文件元数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if hasattr(file_content, 'read'):
                # 文件对象 - upload_fileobj 需要单独的参数格式
                extra_args = {
                    'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                }
                if metadata:
                    extra_args['Metadata'] = metadata
                
                self.s3_client.upload_fileobj(
                    file_content,
                    self.bucket_name,
                    f"{self.exports_prefix}{key}",
                    ExtraArgs=extra_args
                )
            else:
                upload_args = {
                    'Bucket': self.bucket_name,
                    'Key': f"{self.exports_prefix}{key}",
                    'Body': file_content,
                    'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                }
                if metadata:
                    upload_args['Metadata'] = metadata
                self.s3_client.put_object(**upload_args)
            
            logger.info(f"✅ Excel文件保存成功：s3://{self.bucket_name}/{self.exports_prefix}{key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Excel文件保存失败：{e}")
            return False
    
    def get_excel_export(self, key: str) -> Optional[bytes]:
        """
        从exports文件夹获取Excel文件
        
        Args:
            key: 文件键名
            
        Returns:
            Optional[bytes]: Excel文件内容，失败时返回None
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{self.exports_prefix}{key}")
            content = response['Body'].read()
            logger.info(f"✅ Excel文件获取成功：s3://{self.bucket_name}/{self.exports_prefix}{key}")
            return content
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"⚠️ Excel文件不存在：s3://{self.bucket_name}/{self.exports_prefix}{key}")
            else:
                logger.error(f"❌ Excel文件获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Excel文件获取时发生未知错误：{e}")
            return None
    
    def download_file(self, key: str, folder: str = 'upload') -> Optional[bytes]:
        """
        从S3下载文件
        
        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            Optional[bytes]: 文件内容，失败时返回None
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_key = f"{folder_prefix}{key}"
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response['Body'].read()
            logger.info(f"✅ 文件下载成功：s3://{self.bucket_name}/{full_key}")
            return content
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"⚠️ 文件不存在：s3://{self.bucket_name}/{full_key}")
            else:
                logger.error(f"❌ 文件下载失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ 文件下载时发生未知错误：{e}")
            return None
    
    def delete_file(self, key: str, folder: str = 'upload') -> bool:
        """
        从S3删除文件
        
        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            bool: 删除是否成功
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_key = f"{folder_prefix}{key}"
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=full_key)
            logger.info(f"✅ 文件删除成功：s3://{self.bucket_name}/{full_key}")
            return True
        except ClientError as e:
            logger.error(f"❌ 文件删除失败：{e}")
            return False
        except Exception as e:
            logger.error(f"❌ 文件删除时发生未知错误：{e}")
            return False
    
    def file_exists(self, key: str, folder: str = 'upload') -> bool:
        """
        检查文件是否在S3中存在
        
        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            bool: 文件是否存在
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_key = f"{folder_prefix}{key}"
        
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"❌ 检查文件存在时出错：{e}")
                return False
    
    def get_file_info(self, key: str, folder: str = 'upload') -> Optional[dict]:
        """
        获取S3文件信息
        
        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            Optional[dict]: 文件信息，包含大小、修改时间等
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_key = f"{folder_prefix}{key}"
        
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"⚠️ 文件不存在：s3://{self.bucket_name}/{full_key}")
            else:
                logger.error(f"❌ 获取文件信息失败：{e}")
            return None
    
    def generate_presigned_url(self, key: str, expires_in: int = 3600, folder: str = 'upload') -> Optional[str]:
        """
        生成预签名URL用于临时访问文件
        
        Args:
            key: 文件键名
            expires_in: URL过期时间（秒）
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            Optional[str]: 预签名URL
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_key = f"{folder_prefix}{key}"
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': full_key},
                ExpiresIn=expires_in
            )
            logger.info(f"✅ 生成预签名URL成功：s3://{self.bucket_name}/{full_key}")
            return url
        except ClientError as e:
            logger.error(f"❌ 生成预签名URL失败：{e}")
            return None
    
    def list_files(self, prefix: str = '', max_keys: int = 1000, folder: str = 'upload') -> list:
        """
        列出S3存储桶中的文件
        
        Args:
            prefix: 文件前缀过滤
            max_keys: 最大返回文件数
            folder: 文件夹名称 (upload/results/exports)
            
        Returns:
            list: 文件信息列表
        """
        folder_prefix = f"{folder}/" if not folder.endswith('/') else folder
        full_prefix = f"{folder_prefix}{prefix}"
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=full_prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # 移除文件夹前缀，只返回相对路径
                        relative_key = obj['Key'][len(folder_prefix):] if obj['Key'].startswith(folder_prefix) else obj['Key']
                        files.append({
                            'key': relative_key,
                            'full_key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag'].strip('"')
                        })
            
            logger.info(f"✅ 列出文件成功，文件夹：{folder}，前缀：{prefix}，数量：{len(files)}")
            return files
        except ClientError as e:
            logger.error(f"❌ 列出文件失败：{e}")
            return []

    @staticmethod
    def generate_file_key(company_code: str, doc_type_code: str, 
                         filename: str, job_id: Optional[int] = None) -> str:
        """
        生成标准化的S3文件键名
        
        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 原始文件名
            job_id: 任务ID（可选）
            
        Returns:
            str: S3文件键名
        """
        # 清理文件名中的特殊字符
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        # 构建文件路径
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        
        if job_id:
            key = f"uploads/{company_code}/{doc_type_code}/jobs/{job_id}/{timestamp}_{unique_id}_{safe_filename}"
        else:
            key = f"uploads/{company_code}/{doc_type_code}/{timestamp}_{unique_id}_{safe_filename}"
        
        return key

    def get_health_status(self) -> dict:
        """获取S3存储的健康状态"""
        try:
            # 测试存储桶连接
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            # 获取存储桶信息
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)
            
            return {
                'status': 'healthy',
                'bucket': self.bucket_name,
                'region': location.get('LocationConstraint', 'us-east-1'),
                'accessible': True,
                'folders': ['upload', 'results', 'exports']
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'bucket': self.bucket_name,
                'region': self.region,
                'accessible': False,
                'error': str(e)
            }


# 全局S3存储管理器实例
_s3_manager = None

def get_s3_manager() -> Optional[S3StorageManager]:
    """获取全局S3存储管理器实例"""
    global _s3_manager
    
    if _s3_manager is None:
        try:
            # 从环境变量获取S3设置
            bucket_name = os.getenv('S3_BUCKET_NAME')
            region = os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-1')
            
            if bucket_name:
                _s3_manager = S3StorageManager(bucket_name, region)
                _s3_manager.ensure_bucket_exists()
                logger.info(f"✅ S3存储管理器初始化成功：bucket={bucket_name}")
            else:
                logger.warning("⚠️ 未配置S3存储桶名称，将使用本地文件存储")
                
        except Exception as e:
            logger.error(f"❌ S3存储管理器初始化失败：{e}")
            _s3_manager = None
    
    return _s3_manager


def is_s3_enabled() -> bool:
    """检查是否启用了S3存储"""
    return get_s3_manager() is not None