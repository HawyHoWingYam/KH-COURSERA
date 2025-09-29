"""
Company File Manager - Unified ID-based file management for all file types

This module provides a centralized approach to managing files across different types:
- Prompts & Schemas (configuration files)
- Uploads (user document uploads)
- Results (OCR processing outputs)
- Exports (data exports)

All file paths are now ID-based for stability and uniqueness.
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported file types in the system"""
    PROMPT = "prompts"
    SCHEMA = "schemas" 
    UPLOAD = "uploads"
    RESULT = "results"
    EXPORT = "exports"


class CompanyFileManager:
    """
    Unified file manager for all company-related files using ID-based paths
    
    New Clean S3 Structure:
    companies/{company_id}/prompts/{doc_type_id}/{config_id}/filename
    companies/{company_id}/schemas/{doc_type_id}/{config_id}/filename
    companies/{company_id}/uploads/{job_id}_{original_filename}
    companies/{company_id}/results/{job_id}_{result_type}.{ext}
    companies/{company_id}/exports/{export_id}_{export_name}.{ext}
    """
    
    def __init__(self, base_path: str = "companies"):
        """
        Initialize the company file manager
        
        Args:
            base_path: Base path for all company files (default: 'companies')
        """
        self.base_path = base_path
        
    def get_company_file_path(self, 
                            company_id: int,
                            file_type: FileType,
                            filename: str,
                            doc_type_id: Optional[int] = None,
                            config_id: Optional[int] = None,
                            job_id: Optional[str] = None,
                            export_id: Optional[str] = None) -> str:
        """
        Generate ID-based file path for any file type
        
        Args:
            company_id: Company ID (primary identifier)
            file_type: Type of file (prompt, schema, upload, result, export)
            filename: Original filename
            doc_type_id: Document type ID (for prompts/schemas)
            config_id: Configuration ID (for prompts/schemas)  
            job_id: Job ID (for uploads/results)
            export_id: Export ID (for exports)
            
        Returns:
            str: Complete S3-compatible file path
            
        Examples:
            get_company_file_path(1, FileType.PROMPT, "invoice.txt", doc_type_id=11, config_id=6)
            -> "companies/1/prompts/11/6/invoice.txt"
            
            get_company_file_path(1, FileType.UPLOAD, "doc.pdf", job_id="job123")
            -> "companies/1/uploads/job123_doc.pdf"
        """
        company_folder = f"{self.base_path}/{company_id}"
        file_type_folder = f"{company_folder}/{file_type.value}"
        
        if file_type in [FileType.PROMPT, FileType.SCHEMA]:
            # For prompts/schemas: companies/{company_id}/{type}/{doc_type_id}/{config_id}/filename
            if not doc_type_id:
                raise ValueError(f"doc_type_id required for {file_type.value}")
            
            # Handle case where config_id is None (for new configurations)
            if config_id is None:
                # Use timestamp-based temporary identifier for new configs
                import time
                temp_config_id = f"temp_{int(time.time() * 1000)}"
                logger.warning(f"Using temporary config_id for new configuration: {temp_config_id}")
                return f"{file_type_folder}/{doc_type_id}/{temp_config_id}/{filename}"
            
            return f"{file_type_folder}/{doc_type_id}/{config_id}/{filename}"
            
        elif file_type in [FileType.UPLOAD, FileType.RESULT]:
            # For uploads/results: companies/{company_id}/{type}/{job_id}_{filename}
            if not job_id:
                raise ValueError(f"job_id required for {file_type.value}")
                
            return f"{file_type_folder}/{job_id}_{filename}"
            
        elif file_type == FileType.EXPORT:
            # For exports: companies/{company_id}/exports/{export_id}_{filename}
            if not export_id:
                raise ValueError(f"export_id required for {file_type.value}")
                
            return f"{file_type_folder}/{export_id}_{filename}"
            
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def parse_file_path(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an ID-based file path to extract components
        
        Args:
            file_path: File path to parse
            
        Returns:
            Dict with parsed components: company_id, file_type, doc_type_id, 
            config_id, job_id, export_id, filename
            
        Examples:
            parse_file_path("companies/1/prompts/11/6_invoice.txt")
            -> {
                'company_id': 1, 'file_type': 'prompts', 'doc_type_id': 11,
                'config_id': 6, 'filename': 'invoice.txt'
            }
        """
        try:
            parts = file_path.strip('/').split('/')
            
            if len(parts) < 3 or parts[0] != self.base_path:
                raise ValueError(f"Invalid file path format: {file_path}")
            
            company_id = int(parts[1])
            file_type_str = parts[2]
            
            # Validate file type
            try:
                file_type = FileType(file_type_str)
            except ValueError:
                raise ValueError(f"Unknown file type: {file_type_str}")
            
            result = {
                'company_id': company_id,
                'file_type': file_type_str,
                'file_type_enum': file_type
            }
            
            if file_type in [FileType.PROMPT, FileType.SCHEMA]:
                # companies/{company_id}/{type}/{doc_type_id}/{config_id}_{filename}
                if len(parts) != 5:
                    raise ValueError(f"Invalid {file_type_str} path format")
                    
                doc_type_id = int(parts[3])
                config_filename = parts[4]
                
                # Parse config_id from filename
                if '_' not in config_filename:
                    raise ValueError(f"Invalid {file_type_str} filename format: {config_filename}")
                    
                config_id_str, filename = config_filename.split('_', 1)
                config_id = int(config_id_str)
                
                result.update({
                    'doc_type_id': doc_type_id,
                    'config_id': config_id,
                    'filename': filename
                })
                
            elif file_type in [FileType.UPLOAD, FileType.RESULT]:
                # companies/{company_id}/{type}/{job_id}_{filename}
                if len(parts) != 4:
                    raise ValueError(f"Invalid {file_type_str} path format")
                    
                job_filename = parts[3]
                
                if '_' not in job_filename:
                    raise ValueError(f"Invalid {file_type_str} filename format: {job_filename}")
                    
                job_id, filename = job_filename.split('_', 1)
                
                result.update({
                    'job_id': job_id,
                    'filename': filename
                })
                
            elif file_type == FileType.EXPORT:
                # companies/{company_id}/exports/{export_id}_{filename}
                if len(parts) != 4:
                    raise ValueError("Invalid export path format")
                    
                export_filename = parts[3]
                
                if '_' not in export_filename:
                    raise ValueError(f"Invalid export filename format: {export_filename}")
                    
                export_id, filename = export_filename.split('_', 1)
                
                result.update({
                    'export_id': export_id,
                    'filename': filename
                })
            
            return result
            
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing file path '{file_path}': {e}")
            raise ValueError(f"Invalid file path format: {file_path}")
    
    def validate_path(self, file_path: str) -> bool:
        """
        Validate if a file path follows the ID-based naming convention
        
        Args:
            file_path: Path to validate
            
        Returns:
            bool: True if path is valid, False otherwise
        """
        try:
            self.parse_file_path(file_path)
            return True
        except ValueError:
            return False
    
    def is_legacy_path(self, file_path: str) -> bool:
        """
        Check if a path is using the old name-based format
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if this is a legacy (name-based) path
        """
        # Legacy paths don't start with 'companies' or have string-based folder names
        parts = file_path.strip('/').split('/')
        
        if len(parts) < 3:
            return True
            
        # If it starts with companies and has numeric company_id, it's new format
        if parts[0] == self.base_path:
            try:
                int(parts[1])  # company_id should be numeric
                return False
            except ValueError:
                return True
                
        return True
    
    def migrate_legacy_path(self, legacy_path: str, 
                          company_id: int,
                          file_type: FileType,
                          doc_type_id: Optional[int] = None,
                          config_id: Optional[int] = None,
                          job_id: Optional[str] = None,
                          export_id: Optional[str] = None) -> str:
        """
        Convert a legacy name-based path to new ID-based path
        
        Args:
            legacy_path: Old path format (e.g., "prompts/hana/admin_billing/file.txt")
            company_id: Company ID to use
            file_type: File type
            doc_type_id: Document type ID (if applicable)
            config_id: Configuration ID (if applicable)  
            job_id: Job ID (if applicable)
            export_id: Export ID (if applicable)
            
        Returns:
            str: New ID-based path
            
        Example:
            migrate_legacy_path("prompts/hana/admin_billing/file.txt", 
                              company_id=1, file_type=FileType.PROMPT,
                              doc_type_id=11, config_id=6)
            -> "companies/1/prompts/11/6_file.txt"
        """
        # Extract filename from legacy path
        filename = os.path.basename(legacy_path)
        
        # Generate new ID-based path
        new_path = self.get_company_file_path(
            company_id=company_id,
            file_type=file_type,
            filename=filename,
            doc_type_id=doc_type_id,
            config_id=config_id,
            job_id=job_id,
            export_id=export_id
        )
        
        logger.info(f"Migrated path: {legacy_path} -> {new_path}")
        return new_path
    
    def get_company_folder_path(self, company_id: int, file_type: Optional[FileType] = None) -> str:
        """
        Get the base folder path for a company's files
        
        Args:
            company_id: Company ID
            file_type: Specific file type folder (optional)
            
        Returns:
            str: Folder path
        """
        base = f"{self.base_path}/{company_id}"
        
        if file_type:
            return f"{base}/{file_type.value}"
            
        return base
    
    def list_company_files(self, company_id: int, file_type: Optional[FileType] = None) -> str:
        """
        Get the search pattern for listing company files
        
        Args:
            company_id: Company ID
            file_type: File type to filter (optional)
            
        Returns:
            str: Search pattern for S3 listing
        """
        if file_type:
            return f"{self.base_path}/{company_id}/{file_type.value}/"
        else:
            return f"{self.base_path}/{company_id}/"