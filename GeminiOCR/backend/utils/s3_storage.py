import boto3
import os
import logging
from typing import Optional, BinaryIO, Union
from botocore.exceptions import ClientError
from datetime import datetime
import json
import uuid
import mimetypes

from .company_file_manager import CompanyFileManager, FileType

logger = logging.getLogger(__name__)


def clean_schema_for_gemini(schema):
    """
    Clean JSON schema for Gemini API compatibility by removing unsupported fields.
    
    Args:
        schema: The JSON schema dictionary
        
    Returns:
        Cleaned schema dictionary safe for Gemini API
    """
    if not isinstance(schema, dict):
        return schema
    
    # Fields that cause Gemini API errors
    problematic_fields = ["$schema", "$id", "$ref", "definitions", "patternProperties"]
    
    cleaned_schema = {}
    for key, value in schema.items():
        if key in problematic_fields:
            logger.info(f"Removing problematic schema field for Gemini compatibility: {key}")
            continue
            
        if isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned_value = clean_schema_for_gemini(value)
            # Only add if the cleaned value is not empty
            if cleaned_value:
                cleaned_schema[key] = cleaned_value
        elif isinstance(value, list):
            cleaned_schema[key] = [
                clean_schema_for_gemini(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned_schema[key] = value
    
    return cleaned_schema


class S3StorageManager:
    """AWS S3文件存储管理器 - 使用单存储桶多文件夹结构"""

    def __init__(self, bucket_name: str, region: str = "ap-southeast-1", enable_legacy_compatibility: bool = True):
        """
        初始化S3存储管理器

        Args:
            bucket_name: S3存储桶名称
            region: AWS区域
            enable_legacy_compatibility: 是否启用旧路径兼容模式
        """
        self.bucket_name = bucket_name
        self.region = region
        self.enable_legacy_compatibility = enable_legacy_compatibility
        
        # Initialize Company File Manager for ID-based paths
        self.company_file_manager = CompanyFileManager()
        
        # Legacy prefixes (kept for backward compatibility)
        self.upload_prefix = "upload/"
        self.results_prefix = "results/"
        self.exports_prefix = "exports/"
        self.prompts_prefix = "prompts/"
        self.schemas_prefix = "schemas/"
        
        self._s3_client = None
        self._s3_resource = None

    @property
    def s3_client(self):
        """延迟初始化S3客户端"""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client("s3", region_name=self.region)
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
                self._s3_resource = boto3.resource("s3", region_name=self.region)
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
            error_code = int(e.response["Error"]["Code"])

            if error_code == 404:
                # 存储桶不存在，尝试创建
                try:
                    if self.region == "us-east-1":
                        # us-east-1区域创建存储桶的特殊处理
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.region
                            },
                        )

                    logger.info(f"✅ 成功创建S3存储桶：{self.bucket_name}")
                    return True
                except ClientError as create_error:
                    logger.error(f"❌ 创建S3存储桶失败：{create_error}")
                    return False
            else:
                logger.error(f"❌ 检查S3存储桶时出错：{e}")
                return False

    def upload_file(
        self,
        file_content: Union[BinaryIO, bytes],
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
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
                    content_type = "application/octet-stream"

            # 准备上传参数
            upload_args = {
                "Bucket": self.bucket_name,
                "Key": f"{self.upload_prefix}{key}",
                "ContentType": content_type,
            }

            # 添加元数据
            if metadata:
                upload_args["Metadata"] = metadata

            # 执行上传
            if hasattr(file_content, "read"):
                # 文件对象 - upload_fileobj 需要单独的参数格式
                extra_args = {"ContentType": content_type}
                if metadata:
                    extra_args["Metadata"] = metadata

                self.s3_client.upload_fileobj(
                    file_content,
                    upload_args["Bucket"],
                    upload_args["Key"],
                    ExtraArgs=extra_args,
                )
            else:
                # 字节数据
                self.s3_client.put_object(Body=file_content, **upload_args)

            logger.info(
                f"✅ 文件上传成功：s3://{self.bucket_name}/{self.upload_prefix}{key}"
            )
            return True

        except ClientError as e:
            logger.error(f"❌ 文件上传失败：{e}")
            return False
        except Exception as e:
            logger.error(f"❌ 文件上传时发生未知错误：{e}")
            return False

    def save_json_result(
        self, key: str, data: dict, metadata: Optional[dict] = None
    ) -> bool:
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
            json_content = json.dumps(data, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )

            upload_args = {
                "Bucket": self.bucket_name,
                "Key": f"{self.results_prefix}{key}",
                "Body": json_content,
                "ContentType": "application/json",
                "ContentEncoding": "utf-8",
            }

            if metadata:
                upload_args["Metadata"] = metadata

            self.s3_client.put_object(**upload_args)
            logger.info(
                f"✅ JSON结果保存成功：s3://{self.bucket_name}/{self.results_prefix}{key}"
            )
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
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=f"{self.results_prefix}{key}"
            )
            content = response["Body"].read().decode("utf-8")
            data = json.loads(content)
            logger.info(
                f"✅ JSON结果获取成功：s3://{self.bucket_name}/{self.results_prefix}{key}"
            )
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(
                    f"⚠️ JSON文件不存在：s3://{self.bucket_name}/{self.results_prefix}{key}"
                )
            else:
                logger.error(f"❌ JSON结果获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ JSON结果获取时发生未知错误：{e}")
            return None

    def save_excel_export(
        self,
        key: str,
        file_content: Union[BinaryIO, bytes],
        metadata: Optional[dict] = None,
    ) -> bool:
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
            if hasattr(file_content, "read"):
                # 文件对象 - upload_fileobj 需要单独的参数格式
                extra_args = {
                    "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                }
                if metadata:
                    extra_args["Metadata"] = metadata

                self.s3_client.upload_fileobj(
                    file_content,
                    self.bucket_name,
                    f"{self.exports_prefix}{key}",
                    ExtraArgs=extra_args,
                )
            else:
                upload_args = {
                    "Bucket": self.bucket_name,
                    "Key": f"{self.exports_prefix}{key}",
                    "Body": file_content,
                    "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
                if metadata:
                    upload_args["Metadata"] = metadata
                self.s3_client.put_object(**upload_args)

            logger.info(
                f"✅ Excel文件保存成功：s3://{self.bucket_name}/{self.exports_prefix}{key}"
            )
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
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=f"{self.exports_prefix}{key}"
            )
            content = response["Body"].read()
            logger.info(
                f"✅ Excel文件获取成功：s3://{self.bucket_name}/{self.exports_prefix}{key}"
            )
            return content
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(
                    f"⚠️ Excel文件不存在：s3://{self.bucket_name}/{self.exports_prefix}{key}"
                )
            else:
                logger.error(f"❌ Excel文件获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Excel文件获取时发生未知错误：{e}")
            return None

    def download_file(self, key: str, folder: str = "upload") -> Optional[bytes]:
        """
        从S3下载文件

        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            Optional[bytes]: 文件内容，失败时返回None
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
        full_key = f"{folder_prefix}{key}"

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response["Body"].read()
            logger.info(f"✅ 文件下载成功：s3://{self.bucket_name}/{full_key}")
            return content
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ 文件不存在：s3://{self.bucket_name}/{full_key}")
            else:
                logger.error(f"❌ 文件下载失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ 文件下载时发生未知错误：{e}")
            return None

    def delete_file(self, key: str, folder: str = "upload") -> bool:
        """
        从S3删除文件

        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            bool: 删除是否成功
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
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

    def file_exists(self, key: str, folder: str = "upload") -> bool:
        """
        检查文件是否在S3中存在

        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            bool: 文件是否存在
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
        full_key = f"{folder_prefix}{key}"

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                logger.error(f"❌ 检查文件存在时出错：{e}")
                return False

    def get_file_info(self, key: str, folder: str = "upload") -> Optional[dict]:
        """
        获取S3文件信息

        Args:
            key: 文件键名
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            Optional[dict]: 文件信息，包含大小、修改时间等
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
        full_key = f"{folder_prefix}{key}"

        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "content_type": response.get("ContentType", "application/octet-stream"),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.warning(f"⚠️ 文件不存在：s3://{self.bucket_name}/{full_key}")
            else:
                logger.error(f"❌ 获取文件信息失败：{e}")
            return None

    def generate_presigned_url(
        self, key: str, expires_in: int = 3600, folder: str = "upload"
    ) -> Optional[str]:
        """
        生成预签名URL用于临时访问文件

        Args:
            key: 文件键名
            expires_in: URL过期时间（秒）
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            Optional[str]: 预签名URL
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
        full_key = f"{folder_prefix}{key}"

        try:
            filename = os.path.basename(full_key) or "download"
            safe_filename = filename.replace('"', '')
            content_type, _ = mimetypes.guess_type(safe_filename)

            params = {
                "Bucket": self.bucket_name,
                "Key": full_key,
                "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
            }

            if content_type:
                params["ResponseContentType"] = content_type

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            logger.info(f"✅ 生成预签名URL成功：s3://{self.bucket_name}/{full_key}")
            return url
        except ClientError as e:
            logger.error(f"❌ 生成预签名URL失败：{e}")
            return None

    def generate_presigned_url_for_path(self, stored_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for stored database path (S3 URI or relative path)
        
        Args:
            stored_path: Full S3 URI (s3://bucket/key) or relative path within current bucket
            expires_in: URL expiration time in seconds
            
        Returns:
            Optional[str]: Presigned URL for direct download
        """
        try:
            if not stored_path:
                logger.warning("⚠️ Empty stored path provided")
                return None
            
            # Handle S3 URI format: s3://bucket/key/path/file.ext
            if stored_path.startswith('s3://'):
                # Parse S3 URI
                s3_parts = stored_path[5:].split('/', 1)  # Remove 's3://' and split on first '/'
                if len(s3_parts) != 2:
                    logger.error(f"❌ Invalid S3 URI format: {stored_path}")
                    return None
                    
                bucket_name = s3_parts[0]
                s3_key = s3_parts[1]
                
                logger.info(f"🔗 Generating presigned URL for S3 URI: bucket={bucket_name}, key={s3_key}")
                
                filename = os.path.basename(s3_key) or "download"
                safe_filename = filename.replace('"', '')
                content_type, _ = mimetypes.guess_type(safe_filename)

                params = {
                    "Bucket": bucket_name,
                    "Key": s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
                }

                if content_type:
                    params["ResponseContentType"] = content_type

                # Generate presigned URL
                url = self.s3_client.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=expires_in
                )
                
                logger.info(f"✅ Successfully generated presigned URL for S3 URI: {stored_path}")
                return url
                
            # Handle relative paths (assume they're relative to current bucket)
            elif stored_path and not stored_path.startswith('/'):
                logger.info(f"🔗 Generating presigned URL for relative path in bucket {self.bucket_name}: {stored_path}")
                
                filename = os.path.basename(stored_path) or "download"
                safe_filename = filename.replace('"', '')
                content_type, _ = mimetypes.guess_type(safe_filename)

                params = {
                    "Bucket": self.bucket_name,
                    "Key": stored_path,
                    "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
                }

                if content_type:
                    params["ResponseContentType"] = content_type

                url = self.s3_client.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=expires_in
                )
                
                logger.info(f"✅ Successfully generated presigned URL for relative path: {stored_path}")
                return url
                
            else:
                logger.error(f"❌ Unsupported path format: {stored_path}")
                return None
                
        except ClientError as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unknown error generating presigned URL: {e}")
            return None

    def list_files(
        self, prefix: str = "", max_keys: int = 1000, folder: str = "upload"
    ) -> list:
        """
        列出S3存储桶中的文件

        Args:
            prefix: 文件前缀过滤
            max_keys: 最大返回文件数
            folder: 文件夹名称 (upload/results/exports)

        Returns:
            list: 文件信息列表
        """
        folder_prefix = f"{folder}/" if not folder.endswith("/") else folder
        full_prefix = f"{folder_prefix}{prefix}"

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self.bucket_name, Prefix=full_prefix, MaxKeys=max_keys
            )

            files = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        # 移除文件夹前缀，只返回相对路径
                        relative_key = (
                            obj["Key"][len(folder_prefix) :]
                            if obj["Key"].startswith(folder_prefix)
                            else obj["Key"]
                        )
                        files.append(
                            {
                                "key": relative_key,
                                "full_key": obj["Key"],
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"],
                                "etag": obj["ETag"].strip('"'),
                            }
                        )

            logger.info(
                f"✅ 列出文件成功，文件夹：{folder}，前缀：{prefix}，数量：{len(files)}"
            )
            return files
        except ClientError as e:
            logger.error(f"❌ 列出文件失败：{e}")
            return []

    def upload_prompt(
        self,
        company_code: str,
        doc_type_code: str,
        prompt_content: str,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        上传prompt文件到S3

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            prompt_content: prompt内容
            filename: 文件名（可选，默认为prompt.txt）
            metadata: 文件元数据

        Returns:
            Optional[str]: S3键名，失败时返回None
        """
        try:
            if not filename:
                filename = "prompt.txt"

            # 构建S3键名
            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.prompts_prefix}{key}"

            # 准备元数据
            upload_metadata = {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "file_type": "prompt",
                "uploaded_at": datetime.now().isoformat(),
            }
            if metadata:
                upload_metadata.update(metadata)

            # 上传内容
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=prompt_content.encode("utf-8"),
                ContentType="text/plain",
                ContentEncoding="utf-8",
                Metadata=upload_metadata,
            )

            logger.info(f"✅ Prompt上传成功：s3://{self.bucket_name}/{full_key}")
            return key

        except Exception as e:
            logger.error(f"❌ Prompt上传失败：{e}")
            return None

    def get_prompt(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> Optional[str]:
        """
        从S3获取prompt内容

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为prompt.txt）

        Returns:
            Optional[str]: prompt内容，失败时返回None
        """
        try:
            if not filename:
                filename = "prompt.txt"

            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.prompts_prefix}{key}"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response["Body"].read().decode("utf-8")

            logger.info(f"✅ Prompt获取成功：s3://{self.bucket_name}/{full_key}")
            return content

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ Prompt文件不存在：s3://{self.bucket_name}/{self.prompts_prefix}{company_code}/{doc_type_code}/{filename or 'prompt.txt'}")
            else:
                logger.error(f"❌ Prompt获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Prompt获取时发生未知错误：{e}")
            return None

    def get_file_by_key(self, s3_key: str) -> Optional[str]:
        """
        通过完整S3 key获取文件内容（文本文件）
        
        Args:
            s3_key: 完整的S3 key路径
            
        Returns:
            Optional[str]: 文件内容，失败时返回None
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read().decode("utf-8")
            
            logger.info(f"✅ 文件获取成功：s3://{self.bucket_name}/{s3_key}")
            return content
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ 文件不存在：s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"❌ 文件获取失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ 文件获取时发生未知错误：{e}")
            return None

    def get_schema_by_key(self, s3_key: str) -> Optional[dict]:
        """
        通过完整S3 key获取schema文件内容
        
        Args:
            s3_key: 完整的S3 key路径
            
        Returns:
            Optional[dict]: schema数据，失败时返回None
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read().decode("utf-8")
            schema_data = json.loads(content)
            
            # Clean schema for Gemini API compatibility
            schema_data = clean_schema_for_gemini(schema_data)
            
            logger.info(f"✅ Schema获取成功：s3://{self.bucket_name}/{s3_key}")
            return schema_data
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ Schema文件不存在：s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"❌ Schema获取失败：{e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Schema JSON解析失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Schema获取时发生未知错误：{e}")
            return None

    def upload_schema(
        self,
        company_code: str,
        doc_type_code: str,
        schema_data: dict,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        上传schema文件到S3

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            schema_data: schema JSON数据
            filename: 文件名（可选，默认为schema.json）
            metadata: 文件元数据

        Returns:
            Optional[str]: S3键名，失败时返回None
        """
        try:
            if not filename:
                filename = "schema.json"

            # 验证schema格式
            if not isinstance(schema_data, dict):
                raise ValueError("Schema data must be a dictionary")

            # 构建S3键名
            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.schemas_prefix}{key}"

            # 准备元数据
            upload_metadata = {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "file_type": "schema",
                "uploaded_at": datetime.now().isoformat(),
            }
            if metadata:
                upload_metadata.update(metadata)

            # 转换为JSON字符串
            schema_content = json.dumps(schema_data, ensure_ascii=False, indent=2)

            # 上传内容
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=schema_content.encode("utf-8"),
                ContentType="application/json",
                ContentEncoding="utf-8",
                Metadata=upload_metadata,
            )

            logger.info(f"✅ Schema上传成功：s3://{self.bucket_name}/{full_key}")
            return key

        except Exception as e:
            logger.error(f"❌ Schema上传失败：{e}")
            return None

    def get_schema(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> Optional[dict]:
        """
        从S3获取schema数据

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为schema.json）

        Returns:
            Optional[dict]: schema数据，失败时返回None
        """
        try:
            if not filename:
                filename = "schema.json"

            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.schemas_prefix}{key}"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response["Body"].read().decode("utf-8")
            schema_data = json.loads(content)
            
            # Clean schema for Gemini API compatibility
            schema_data = clean_schema_for_gemini(schema_data)

            logger.info(f"✅ Schema获取成功：s3://{self.bucket_name}/{full_key}")
            return schema_data

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ Schema文件不存在：s3://{self.bucket_name}/{self.schemas_prefix}{company_code}/{doc_type_code}/{filename or 'schema.json'}")
            else:
                logger.error(f"❌ Schema获取失败：{e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Schema JSON解析失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Schema获取时发生未知错误：{e}")
            return None

    def download_prompt_raw(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> Optional[bytes]:
        """
        从S3下载prompt文件的原始内容（用于文件下载）

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为prompt.txt）

        Returns:
            Optional[bytes]: 文件原始内容，失败时返回None
        """
        try:
            if not filename:
                filename = "prompt.txt"

            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.prompts_prefix}{key}"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response["Body"].read()

            logger.info(f"✅ Prompt原始内容下载成功：s3://{self.bucket_name}/{full_key}")
            return content

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ Prompt文件不存在：s3://{self.bucket_name}/{self.prompts_prefix}{company_code}/{doc_type_code}/{filename or 'prompt.txt'}")
            else:
                logger.error(f"❌ Prompt原始内容下载失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Prompt原始内容下载时发生未知错误：{e}")
            return None

    def download_schema_raw(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> Optional[bytes]:
        """
        从S3下载schema文件的原始内容（用于文件下载）

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为schema.json）

        Returns:
            Optional[bytes]: 文件原始内容，失败时返回None
        """
        try:
            if not filename:
                filename = "schema.json"

            key = f"{company_code}/{doc_type_code}/{filename}"
            full_key = f"{self.schemas_prefix}{key}"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            content = response["Body"].read()

            logger.info(f"✅ Schema原始内容下载成功：s3://{self.bucket_name}/{full_key}")
            return content

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"⚠️ Schema文件不存在：s3://{self.bucket_name}/{self.schemas_prefix}{company_code}/{doc_type_code}/{filename or 'schema.json'}")
            else:
                logger.error(f"❌ Schema原始内容下载失败：{e}")
            return None
        except Exception as e:
            logger.error(f"❌ Schema原始内容下载时发生未知错误：{e}")
            return None

    def list_prompts(self, company_code: Optional[str] = None, doc_type_code: Optional[str] = None) -> list:
        """
        列出prompt文件

        Args:
            company_code: 公司代码（可选）
            doc_type_code: 文档类型代码（可选）

        Returns:
            list: prompt文件信息列表
        """
        try:
            # 构建前缀
            prefix = ""
            if company_code and doc_type_code:
                prefix = f"{company_code}/{doc_type_code}/"
            elif company_code:
                prefix = f"{company_code}/"

            return self.list_files(prefix=prefix, folder="prompts")

        except Exception as e:
            logger.error(f"❌ 列出prompt文件失败：{e}")
            return []

    def list_schemas(self, company_code: Optional[str] = None, doc_type_code: Optional[str] = None) -> list:
        """
        列出schema文件

        Args:
            company_code: 公司代码（可选）
            doc_type_code: 文档类型代码（可选）

        Returns:
            list: schema文件信息列表
        """
        try:
            # 构建前缀
            prefix = ""
            if company_code and doc_type_code:
                prefix = f"{company_code}/{doc_type_code}/"
            elif company_code:
                prefix = f"{company_code}/"

            return self.list_files(prefix=prefix, folder="schemas")

        except Exception as e:
            logger.error(f"❌ 列出schema文件失败：{e}")
            return []

    def delete_prompt(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> bool:
        """
        删除prompt文件

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为prompt.txt）

        Returns:
            bool: 删除是否成功
        """
        try:
            if not filename:
                filename = "prompt.txt"

            key = f"{company_code}/{doc_type_code}/{filename}"
            return self.delete_file(key, folder="prompts")

        except Exception as e:
            logger.error(f"❌ 删除prompt文件失败：{e}")
            return False

    def delete_schema(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> bool:
        """
        删除schema文件

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为schema.json）

        Returns:
            bool: 删除是否成功
        """
        try:
            if not filename:
                filename = "schema.json"

            key = f"{company_code}/{doc_type_code}/{filename}"
            return self.delete_file(key, folder="schemas")

        except Exception as e:
            logger.error(f"❌ 删除schema文件失败：{e}")
            return False

    def prompt_exists(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> bool:
        """
        检查prompt文件是否存在

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为prompt.txt）

        Returns:
            bool: 文件是否存在
        """
        try:
            if not filename:
                filename = "prompt.txt"

            key = f"{company_code}/{doc_type_code}/{filename}"
            return self.file_exists(key, folder="prompts")

        except Exception as e:
            logger.error(f"❌ 检查prompt文件存在时出错：{e}")
            return False

    def schema_exists(self, company_code: str, doc_type_code: str, filename: Optional[str] = None) -> bool:
        """
        检查schema文件是否存在

        Args:
            company_code: 公司代码
            doc_type_code: 文档类型代码
            filename: 文件名（可选，默认为schema.json）

        Returns:
            bool: 文件是否存在
        """
        try:
            if not filename:
                filename = "schema.json"

            key = f"{company_code}/{doc_type_code}/{filename}"
            return self.file_exists(key, folder="schemas")

        except Exception as e:
            logger.error(f"❌ 检查schema文件存在时出错：{e}")
            return False

    @staticmethod
    def generate_file_key(
        company_code: str,
        doc_type_code: str,
        filename: str,
        job_id: Optional[int] = None,
    ) -> str:
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
        safe_filename = "".join(
            c for c in filename if c.isalnum() or c in (" ", "-", "_", ".")
        ).rstrip()

        # 构建文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
                "status": "healthy",
                "bucket": self.bucket_name,
                "region": location.get("LocationConstraint", "us-east-1"),
                "accessible": True,
                "folders": ["upload", "results", "exports", "prompts", "schemas"],
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "bucket": self.bucket_name,
                "region": self.region,
                "accessible": False,
                "error": str(e),
            }

    # ========================================
    # NEW ID-BASED METHODS FOR FILE MANAGEMENT
    # ========================================
    
    def upload_company_file(self, 
                          company_id: int,
                          file_type: FileType,
                          content: Union[str, bytes],
                          filename: str,
                          doc_type_id: Optional[int] = None,
                          config_id: Optional[int] = None,
                          job_id: Optional[str] = None,
                          export_id: Optional[str] = None,
                          metadata: Optional[dict] = None) -> Optional[str]:
        """
        Upload file using new ID-based path structure
        
        Args:
            company_id: Company ID
            file_type: Type of file (prompt, schema, upload, result, export)
            content: File content (string or bytes)
            filename: Original filename
            doc_type_id: Document type ID (for prompts/schemas)
            config_id: Configuration ID (for prompts/schemas)
            job_id: Job ID (for uploads/results)
            export_id: Export ID (for exports)
            metadata: Additional metadata
            
        Returns:
            Optional[str]: S3 key if successful, None if failed
        """
        try:
            # Generate ID-based path
            s3_path = self.company_file_manager.get_company_file_path(
                company_id=company_id,
                file_type=file_type,
                filename=filename,
                doc_type_id=doc_type_id,
                config_id=config_id,
                job_id=job_id,
                export_id=export_id
            )
            
            # Prepare metadata
            upload_metadata = {
                "company_id": str(company_id),
                "file_type": file_type.value,
                "uploaded_at": datetime.now().isoformat(),
            }
            
            # Add type-specific metadata
            if doc_type_id:
                upload_metadata["doc_type_id"] = str(doc_type_id)
            if config_id:
                upload_metadata["config_id"] = str(config_id)
            if job_id:
                upload_metadata["job_id"] = job_id
            if export_id:
                upload_metadata["export_id"] = export_id
                
            if metadata:
                upload_metadata.update(metadata)
            
            # Determine content type
            content_type = "text/plain"
            if file_type == FileType.SCHEMA or filename.endswith('.json'):
                content_type = "application/json"
            elif filename.endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "application/octet-stream"
            
            # Convert content to bytes if needed
            if isinstance(content, str):
                body = content.encode('utf-8')
                encoding = "utf-8"
            else:
                body = content
                encoding = None
                
            # Upload to S3
            put_args = {
                "Bucket": self.bucket_name,
                "Key": s3_path,
                "Body": body,
                "ContentType": content_type,
                "Metadata": upload_metadata,
            }
            
            if encoding:
                put_args["ContentEncoding"] = encoding
            
            self.s3_client.put_object(**put_args)
            
            logger.info(f"✅ ID-based file upload successful: s3://{self.bucket_name}/{s3_path}")
            return s3_path
            
        except Exception as e:
            logger.error(f"❌ ID-based file upload failed: {e}")
            return None
    
    def download_company_file(self,
                            company_id: int,
                            file_type: FileType,
                            filename: str,
                            doc_type_id: Optional[int] = None,
                            config_id: Optional[int] = None,
                            job_id: Optional[str] = None,
                            export_id: Optional[str] = None) -> Optional[bytes]:
        """
        Download file using new ID-based path structure
        
        Args:
            company_id: Company ID
            file_type: Type of file
            filename: Original filename
            doc_type_id: Document type ID (for prompts/schemas)
            config_id: Configuration ID (for prompts/schemas)
            job_id: Job ID (for uploads/results)
            export_id: Export ID (for exports)
            
        Returns:
            Optional[bytes]: File content if found, None if not found
        """
        try:
            # Generate ID-based path
            s3_path = self.company_file_manager.get_company_file_path(
                company_id=company_id,
                file_type=file_type,
                filename=filename,
                doc_type_id=doc_type_id,
                config_id=config_id,
                job_id=job_id,
                export_id=export_id
            )
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            content = response["Body"].read()
            
            logger.info(f"✅ ID-based file download successful: s3://{self.bucket_name}/{s3_path}")
            return content
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"⚠️ ID-based file not found: s3://{self.bucket_name}/{s3_path}")
            else:
                logger.error(f"❌ ID-based file download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ ID-based file download failed: {e}")
            return None
    
    def upload_prompt_by_id(self,
                          company_id: int,
                          doc_type_id: int,
                          config_id: int,
                          prompt_content: str,
                          filename: Optional[str] = None,
                          metadata: Optional[dict] = None) -> Optional[str]:
        """
        Upload prompt using clean ID-based path (convenience method)
        
        Args:
            company_id: Company ID
            doc_type_id: Document type ID
            config_id: Configuration ID
            prompt_content: Prompt content
            filename: Filename (should be original filename)
            metadata: Additional metadata
            
        Returns:
            Optional[str]: S3 key if successful
        """
        if not filename:
            filename = "prompt.txt"  # Use clean default filename
            
        return self.upload_company_file(
            company_id=company_id,
            file_type=FileType.PROMPT,
            content=prompt_content,
            filename=filename,
            doc_type_id=doc_type_id,
            config_id=config_id,
            metadata=metadata
        )
    
    def upload_schema_by_id(self,
                          company_id: int,
                          doc_type_id: int,
                          config_id: int,
                          schema_data: dict,
                          filename: Optional[str] = None,
                          metadata: Optional[dict] = None) -> Optional[str]:
        """
        Upload schema using clean ID-based path (convenience method)
        
        Args:
            company_id: Company ID
            doc_type_id: Document type ID
            config_id: Configuration ID
            schema_data: Schema data as dict
            filename: Filename (should be original filename)
            metadata: Additional metadata
            
        Returns:
            Optional[str]: S3 key if successful
        """
        import json
        
        if not filename:
            filename = "schema.json"  # Use clean default filename
            
        # Convert schema data to JSON string
        schema_content = json.dumps(schema_data, indent=2, ensure_ascii=False)
            
        return self.upload_company_file(
            company_id=company_id,
            file_type=FileType.SCHEMA,
            content=schema_content,
            filename=filename,
            doc_type_id=doc_type_id,
            config_id=config_id,
            metadata=metadata
        )
    
    def download_prompt_by_id(self,
                            company_id: int,
                            doc_type_id: int,
                            config_id: int,
                            filename: Optional[str] = None) -> Optional[str]:
        """
        Download prompt using clean ID-based path with fallbacks (convenience method)
        
        Returns:
            Optional[str]: Prompt content as string
        """
        if not filename:
            filename = "prompt.txt"  # Clean default filename
            
        # Try primary ID-based path
        content = self.download_company_file(
            company_id=company_id,
            file_type=FileType.PROMPT,
            filename=filename,
            doc_type_id=doc_type_id,
            config_id=config_id
        )
        
        # If not found, try temp path fallback
        if content is None:
            logger.info(f"🔄 Primary path not found, trying temp path fallback for config {config_id}")
            temp_paths = [
                f"companies/{company_id}/prompts/{doc_type_id}/temp_{config_id}/{filename}",
                f"companies/{company_id}/prompts/{doc_type_id}/temp_{int(config_id) * 1000}/{filename}",
                # Try some common temp timestamp patterns
                f"companies/{company_id}/prompts/{doc_type_id}/temp_1758089852851/{filename}",
            ]
            
            for temp_path in temp_paths:
                logger.info(f"🔍 Trying temp path: {temp_path}")
                try:
                    response = self.s3_client.get_object(Bucket=self.bucket_name, Key=temp_path)
                    content = response["Body"].read()
                    logger.info(f"✅ Found prompt at temp path: {temp_path}")
                    break
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        logger.warning(f"⚠️ S3 error on temp path {temp_path}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Error trying temp path {temp_path}: {e}")
        
        if content:
            return content.decode('utf-8')
        return None
    
    def download_schema_by_id(self,
                            company_id: int,
                            doc_type_id: int,
                            config_id: int,
                            filename: Optional[str] = None) -> Optional[dict]:
        """
        Download schema using clean ID-based path with fallbacks (convenience method)
        
        Returns:
            Optional[dict]: Schema data as dictionary
        """
        if not filename:
            filename = "schema.json"  # Clean default filename
            
        # Try primary ID-based path
        content = self.download_company_file(
            company_id=company_id,
            file_type=FileType.SCHEMA,
            filename=filename,
            doc_type_id=doc_type_id,
            config_id=config_id
        )
        
        # If not found, try temp path fallback
        if content is None:
            logger.info(f"🔄 Primary schema path not found, trying temp path fallback for config {config_id}")
            temp_paths = [
                f"companies/{company_id}/schemas/{doc_type_id}/temp_{config_id}/{filename}",
                f"companies/{company_id}/schemas/{doc_type_id}/temp_{int(config_id) * 1000}/{filename}",
                # Try some common temp timestamp patterns
                f"companies/{company_id}/schemas/{doc_type_id}/temp_1758089852982/{filename}",
            ]
            
            for temp_path in temp_paths:
                logger.info(f"🔍 Trying temp schema path: {temp_path}")
                try:
                    response = self.s3_client.get_object(Bucket=self.bucket_name, Key=temp_path)
                    content = response["Body"].read()
                    logger.info(f"✅ Found schema at temp path: {temp_path}")
                    break
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        logger.warning(f"⚠️ S3 error on temp schema path {temp_path}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Error trying temp schema path {temp_path}: {e}")
        
        if content:
            try:
                import json
                schema_data = json.loads(content.decode('utf-8'))
                
                # Clean schema for Gemini API compatibility
                schema_data = clean_schema_for_gemini(schema_data)
                
                return schema_data
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse schema JSON: {e}")
                return None
        return None
    
    def download_file_by_stored_path(self, stored_path: str) -> Optional[bytes]:
        """
        Download file using stored database path (S3 URI or relative path)
        
        Args:
            stored_path: Full S3 URI (s3://bucket/key) or relative path within current bucket
            
        Returns:
            Optional[bytes]: File content if found, None if not found
        """
        try:
            if not stored_path:
                logger.warning("⚠️ Empty stored path provided")
                return None
            
            # Handle S3 URI format: s3://bucket/key/path/file.ext
            if stored_path.startswith('s3://'):
                # Parse S3 URI
                s3_parts = stored_path[5:].split('/', 1)  # Remove 's3://' and split on first '/'
                if len(s3_parts) != 2:
                    logger.error(f"❌ Invalid S3 URI format: {stored_path}")
                    return None
                    
                bucket_name = s3_parts[0]
                s3_key = s3_parts[1]
                
                logger.info(f"📥 Downloading from S3 URI: bucket={bucket_name}, key={s3_key}")
                
                # Direct S3 download
                response = self.s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                content = response["Body"].read()
                
                logger.info(f"✅ Successfully downloaded from S3 URI: {stored_path}")
                return content
                
            # Handle relative paths (assume they're relative to current bucket)
            elif stored_path and not stored_path.startswith('/'):
                logger.info(f"📥 Downloading relative path from bucket {self.bucket_name}: {stored_path}")
                
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=stored_path)
                content = response["Body"].read()
                
                logger.info(f"✅ Successfully downloaded relative path: {stored_path}")
                return content
                
            else:
                logger.error(f"❌ Unsupported path format: {stored_path}")
                return None
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"⚠️ File not found at stored path: {stored_path}")
            else:
                logger.error(f"❌ S3 error downloading from stored path: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to download from stored path '{stored_path}': {e}")
            return None


# 全局S3存储管理器实例
_s3_manager = None


def get_s3_manager() -> Optional[S3StorageManager]:
    """获取全局S3存储管理器实例"""
    global _s3_manager

    if _s3_manager is None:
        try:
            # 从环境变量获取S3设置
            bucket_name = os.getenv("S3_BUCKET_NAME")
            region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1")

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
