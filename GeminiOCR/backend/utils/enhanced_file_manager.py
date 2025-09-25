"""
Enhanced File Manager - Advanced ID-based file organization system
Extends the basic company file manager with enterprise-grade features.
"""

import logging
import os
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid

from .company_file_manager import CompanyFileManager, FileType
from .s3_storage import S3StorageManager

logger = logging.getLogger(__name__)


class FileCategory(Enum):
    """Extended file categories for better organization"""
    CONFIGURATION = "config"       # Prompts, schemas
    PROCESSING = "processing"      # Uploads, processing jobs  
    OUTPUT = "output"             # Results, exports
    ARCHIVE = "archive"           # Archived/backup files
    TEMPORARY = "temp"            # Temporary files


class FileAccessLevel(Enum):
    """File access levels for security"""
    PUBLIC = "public"
    COMPANY = "company"
    ADMIN = "admin"
    SYSTEM = "system"


class FileRetentionPolicy(Enum):
    """File retention policies"""
    PERMANENT = "permanent"       # Keep forever
    STANDARD = "standard"         # 1 year
    SHORT_TERM = "short_term"    # 90 days
    PROCESSING = "processing"     # 30 days
    TEMPORARY = "temporary"       # 7 days


class EnhancedFileManager(CompanyFileManager):
    """
    Enhanced file manager with enterprise features:
    - Standardized folder structure
    - File versioning
    - Retention policies  
    - Access controls
    - Metadata management
    """
    
    def __init__(self, s3_manager: Optional[S3StorageManager] = None):
        super().__init__()
        self.s3_manager = s3_manager
        
        # Define standard folder structure according to todolist requirements
        self.folder_structure = {
            'uploads': {
                'purpose': 'OCR Images/ZIP/PDF files',
                'retention': FileRetentionPolicy.STANDARD,
                'access_level': FileAccessLevel.COMPANY
            },
            'results': {
                'purpose': 'Result JSON files', 
                'retention': FileRetentionPolicy.STANDARD,
                'access_level': FileAccessLevel.COMPANY
            },
            'exports': {
                'purpose': 'NetSuite CSV, mapped CSV files',
                'retention': FileRetentionPolicy.STANDARD,
                'access_level': FileAccessLevel.COMPANY
            },
            'prompts': {
                'purpose': 'Prompt template files',
                'retention': FileRetentionPolicy.PERMANENT,
                'access_level': FileAccessLevel.ADMIN
            },
            'schemas': {
                'purpose': 'JSON schema files',
                'retention': FileRetentionPolicy.PERMANENT,
                'access_level': FileAccessLevel.ADMIN
            },
            'backups': {
                'purpose': 'Backup files',
                'retention': FileRetentionPolicy.STANDARD,
                'access_level': FileAccessLevel.SYSTEM
            }
        }
    
    def get_standardized_path(self, 
                            folder_type: str,
                            company_id: int,
                            doc_type_id: Optional[int] = None,
                            identifier: Optional[str] = None,
                            filename: Optional[str] = None) -> str:
        """
        Generate standardized path according to design specification.
        
        Standard Structure:
        - uploads/COMPANY/DOC_TYPE/batch_N/files
        - results/COMPANY/DOC_TYPE/batch_N/results.json
        - exports/COMPANY/DOC_TYPE/batch_N/netsuite.csv
        - prompts/COMPANY/DOC_TYPE/config_N/prompt.txt
        - schemas/COMPANY/DOC_TYPE/config_N/schema.json
        - backups/TYPE/COMPANY/DOC_TYPE/DATE/files
        """
        if folder_type not in self.folder_structure:
            raise ValueError(f"Unknown folder type: {folder_type}")
        
        # Get company and doc type codes for human-readable paths
        company_code = self._get_company_code(company_id)
        doc_type_code = self._get_doc_type_code(doc_type_id) if doc_type_id else "GENERAL"
        
        if folder_type in ['uploads', 'results', 'exports']:
            # Processing-related files: folder/COMPANY/DOC_TYPE/batch_N/file
            batch_id = identifier or "temp"
            path = f"{folder_type}/{company_code}/{doc_type_code}/batch_{batch_id}"
            
        elif folder_type in ['prompts', 'schemas']:
            # Configuration files: folder/COMPANY/DOC_TYPE/config_N/file
            config_id = identifier or "default"
            path = f"{folder_type}/{company_code}/{doc_type_code}/config_{config_id}"
            
        elif folder_type == 'backups':
            # Backup files: backups/TYPE/COMPANY/DOC_TYPE/DATE/file
            backup_type = identifier or "general"
            date_str = datetime.now().strftime("%Y-%m-%d")
            path = f"backups/{backup_type}/{company_code}/{doc_type_code}/{date_str}"
            
        else:
            # Fallback to basic structure
            path = f"{folder_type}/{company_code}"
            if doc_type_code != "GENERAL":
                path += f"/{doc_type_code}"
            if identifier:
                path += f"/{identifier}"
        
        if filename:
            path += f"/{filename}"
            
        return path
    
    def _get_company_code(self, company_id: int) -> str:
        """Get company code from ID (with caching if needed)."""
        # This should ideally query the database, but for now return a default
        return f"COMPANY_{company_id}"
    
    def _get_doc_type_code(self, doc_type_id: int) -> str:
        """Get document type code from ID (with caching if needed)."""
        # This should ideally query the database, but for now return a default
        return f"DOCTYPE_{doc_type_id}"
    
    def create_file_metadata(self,
                           file_path: str,
                           original_filename: str,
                           file_size: int,
                           content_type: str,
                           company_id: int,
                           created_by: Optional[str] = None,
                           retention_policy: Optional[FileRetentionPolicy] = None,
                           access_level: Optional[FileAccessLevel] = None,
                           tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create comprehensive file metadata."""
        now = datetime.now()
        
        # Determine folder type from path
        folder_type = file_path.split('/')[0]
        folder_config = self.folder_structure.get(folder_type, {})
        
        metadata = {
            'file_id': str(uuid.uuid4()),
            'file_path': file_path,
            'original_filename': original_filename,
            'file_size': file_size,
            'content_type': content_type,
            'company_id': company_id,
            'folder_type': folder_type,
            'created_at': now.isoformat(),
            'created_by': created_by or 'system',
            'updated_at': now.isoformat(),
            'version': 1,
            'retention_policy': (retention_policy or folder_config.get('retention', FileRetentionPolicy.STANDARD)).value,
            'access_level': (access_level or folder_config.get('access_level', FileAccessLevel.COMPANY)).value,
            'tags': tags or [],
            'checksum': None,  # To be calculated
            'encryption': False,
            'archived': False
        }
        
        # Calculate expiry date based on retention policy
        if metadata['retention_policy'] == FileRetentionPolicy.TEMPORARY.value:
            expiry = now + timedelta(days=7)
        elif metadata['retention_policy'] == FileRetentionPolicy.PROCESSING.value:
            expiry = now + timedelta(days=30)
        elif metadata['retention_policy'] == FileRetentionPolicy.SHORT_TERM.value:
            expiry = now + timedelta(days=90)
        elif metadata['retention_policy'] == FileRetentionPolicy.STANDARD.value:
            expiry = now + timedelta(days=365)
        else:  # PERMANENT
            expiry = None
        
        if expiry:
            metadata['expires_at'] = expiry.isoformat()
        
        return metadata
    
    def upload_with_metadata(self,
                           content: bytes,
                           folder_type: str,
                           company_id: int,
                           original_filename: str,
                           doc_type_id: Optional[int] = None,
                           identifier: Optional[str] = None,
                           metadata_override: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Upload file with comprehensive metadata management.
        
        Returns:
            Tuple of (success, file_path, metadata)
        """
        if not self.s3_manager:
            logger.error("S3 manager not available")
            return False, None, None
        
        try:
            # Generate standardized path
            file_path = self.get_standardized_path(
                folder_type=folder_type,
                company_id=company_id,
                doc_type_id=doc_type_id,
                identifier=identifier,
                filename=original_filename
            )
            
            # Create metadata
            metadata = self.create_file_metadata(
                file_path=file_path,
                original_filename=original_filename,
                file_size=len(content),
                content_type=self._guess_content_type(original_filename),
                company_id=company_id
            )
            
            # Apply metadata overrides
            if metadata_override:
                metadata.update(metadata_override)
            
            # Upload to S3 with metadata
            success = self.s3_manager.s3_client.put_object(
                Bucket=self.s3_manager.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=metadata['content_type'],
                Metadata={
                    'file_id': metadata['file_id'],
                    'company_id': str(company_id),
                    'folder_type': folder_type,
                    'retention_policy': metadata['retention_policy'],
                    'access_level': metadata['access_level'],
                    'created_at': metadata['created_at']
                }
            )
            
            if success:
                s3_uri = f"s3://{self.s3_manager.bucket_name}/{file_path}"
                logger.info(f"✅ Uploaded with metadata: {s3_uri}")
                return True, s3_uri, metadata
            else:
                logger.error(f"❌ Upload failed: {file_path}")
                return False, None, None
                
        except Exception as e:
            logger.error(f"❌ Upload with metadata failed: {e}")
            return False, None, None
    
    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename."""
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or 'application/octet-stream'
    
    def enforce_folder_structure(self) -> Dict[str, Any]:
        """
        Enforce standardized folder structure in S3.
        Creates folder markers and sets up proper organization.
        """
        if not self.s3_manager:
            return {'success': False, 'error': 'S3 manager not available'}
        
        results = {
            'folders_created': 0,
            'markers_added': 0,
            'errors': 0,
            'success': True
        }
        
        try:
            for folder_name, config in self.folder_structure.items():
                # Create folder marker with metadata
                marker_path = f"{folder_name}/.folder_info"
                folder_info = {
                    'folder_name': folder_name,
                    'purpose': config['purpose'],
                    'retention_policy': config['retention'].value,
                    'access_level': config['access_level'].value,
                    'created_at': datetime.now().isoformat(),
                    'structure_version': '2.0'
                }
                
                try:
                    self.s3_manager.s3_client.put_object(
                        Bucket=self.s3_manager.bucket_name,
                        Key=marker_path,
                        Body=json.dumps(folder_info, indent=2).encode('utf-8'),
                        ContentType='application/json',
                        Metadata={
                            'folder_marker': 'true',
                            'folder_type': folder_name,
                            'structure_version': '2.0'
                        }
                    )
                    
                    results['folders_created'] += 1
                    results['markers_added'] += 1
                    logger.info(f"✅ Created folder structure: {folder_name}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create folder {folder_name}: {e}")
                    results['errors'] += 1
        
        except Exception as e:
            logger.error(f"❌ Folder structure enforcement failed: {e}")
            results['success'] = False
            results['error'] = str(e)
        
        return results
    
    def migrate_legacy_paths(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate legacy file paths to new standardized structure.
        
        Args:
            dry_run: If True, only analyze without making changes
        """
        if not self.s3_manager:
            return {'success': False, 'error': 'S3 manager not available'}
        
        migration_results = {
            'files_analyzed': 0,
            'files_to_migrate': 0,
            'files_migrated': 0,
            'errors': 0,
            'dry_run': dry_run,
            'migrations': []
        }
        
        try:
            # Analyze all files in bucket
            paginator = self.s3_manager.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_manager.bucket_name)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    migration_results['files_analyzed'] += 1
                    
                    # Check if file needs migration
                    migration_target = self._analyze_migration_need(key)
                    
                    if migration_target:
                        migration_results['files_to_migrate'] += 1
                        migration_results['migrations'].append({
                            'source': key,
                            'target': migration_target,
                            'reason': 'Legacy path structure'
                        })
                        
                        if not dry_run:
                            # Perform migration
                            success = self._migrate_file(key, migration_target)
                            if success:
                                migration_results['files_migrated'] += 1
                            else:
                                migration_results['errors'] += 1
        
        except Exception as e:
            logger.error(f"❌ Migration analysis failed: {e}")
            migration_results['success'] = False
            migration_results['error'] = str(e)
        
        return migration_results
    
    def _analyze_migration_need(self, file_path: str) -> Optional[str]:
        """Analyze if a file needs migration to new structure."""
        # Check for legacy batch results structure
        if file_path.startswith('upload/batch_results/'):
            # Convert to new results structure
            return file_path.replace('upload/batch_results/', 'results/')
        
        # Check for legacy upload structure inconsistencies
        if file_path.startswith('upload/') and 'batch_results' not in file_path:
            # Already in correct uploads structure
            return None
        
        # Check for temp path structures in prompts/schemas
        if '/temp_' in file_path and file_path.startswith('companies/'):
            # These might need cleanup but are functional
            return None
        
        return None
    
    def _migrate_file(self, source_key: str, target_key: str) -> bool:
        """Migrate a single file from source to target location."""
        try:
            # Copy to new location
            copy_source = {'Bucket': self.s3_manager.bucket_name, 'Key': source_key}
            self.s3_manager.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.s3_manager.bucket_name,
                Key=target_key
            )
            
            # Verify copy
            try:
                self.s3_manager.s3_client.head_object(
                    Bucket=self.s3_manager.bucket_name,
                    Key=target_key
                )
                
                # Delete original
                self.s3_manager.s3_client.delete_object(
                    Bucket=self.s3_manager.bucket_name,
                    Key=source_key
                )
                
                logger.info(f"✅ Migrated: {source_key} -> {target_key}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Migration verification failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ File migration failed: {e}")
            return False
    
    def get_folder_statistics(self) -> Dict[str, Any]:
        """Get comprehensive folder usage statistics."""
        if not self.s3_manager:
            return {'error': 'S3 manager not available'}
        
        stats = {}
        
        try:
            for folder_name in self.folder_structure.keys():
                folder_stats = {
                    'file_count': 0,
                    'total_size': 0,
                    'file_types': {},
                    'companies': set(),
                    'oldest_file': None,
                    'newest_file': None
                }
                
                # List files in folder
                paginator = self.s3_manager.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(
                    Bucket=self.s3_manager.bucket_name,
                    Prefix=f"{folder_name}/"
                )
                
                for page in pages:
                    if 'Contents' not in page:
                        continue
                    
                    for obj in page['Contents']:
                        key = obj['Key']
                        size = obj['Size']
                        modified = obj['LastModified']
                        
                        folder_stats['file_count'] += 1
                        folder_stats['total_size'] += size
                        
                        # Track file types
                        ext = key.split('.')[-1].lower() if '.' in key else 'no_ext'
                        folder_stats['file_types'][ext] = folder_stats['file_types'].get(ext, 0) + 1
                        
                        # Track companies (extract from path)
                        path_parts = key.split('/')
                        if len(path_parts) > 1:
                            folder_stats['companies'].add(path_parts[1])
                        
                        # Track date range
                        if folder_stats['oldest_file'] is None or modified < folder_stats['oldest_file']:
                            folder_stats['oldest_file'] = modified
                        if folder_stats['newest_file'] is None or modified > folder_stats['newest_file']:
                            folder_stats['newest_file'] = modified
                
                # Convert sets to lists for JSON serialization
                folder_stats['companies'] = list(folder_stats['companies'])
                folder_stats['company_count'] = len(folder_stats['companies'])
                
                # Format dates
                if folder_stats['oldest_file']:
                    folder_stats['oldest_file'] = folder_stats['oldest_file'].isoformat()
                if folder_stats['newest_file']:
                    folder_stats['newest_file'] = folder_stats['newest_file'].isoformat()
                
                stats[folder_name] = folder_stats
        
        except Exception as e:
            logger.error(f"❌ Failed to get folder statistics: {e}")
            stats['error'] = str(e)
        
        return stats


def create_enhanced_file_manager(s3_manager: Optional[S3StorageManager] = None) -> EnhancedFileManager:
    """Factory function to create enhanced file manager."""
    return EnhancedFileManager(s3_manager)


def standardize_s3_structure(s3_manager: Optional[S3StorageManager] = None) -> Dict[str, Any]:
    """Convenience function to standardize S3 structure."""
    manager = create_enhanced_file_manager(s3_manager)
    return manager.enforce_folder_structure()