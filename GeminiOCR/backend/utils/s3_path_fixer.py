"""
S3 Path Structure Fixer
Fixes S3 path generation to align with the desired folder structure.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class S3PathFixer:
    """Fixes S3 path structure to align with design specifications."""
    
    @staticmethod
    def get_results_path(company_code: str, doc_type_code: str, batch_id: int, filename: str) -> str:
        """
        Generate properly aligned results path.
        
        From: upload/batch_results/COMPANY/DOC_TYPE/batch_N/file.ext
        To: results/COMPANY/DOC_TYPE/batch_N/file.ext
        """
        return f"results/{company_code}/{doc_type_code}/batch_{batch_id}/{filename}"
    
    @staticmethod
    def get_exports_path(company_code: str, doc_type_code: str, batch_id: int, filename: str) -> str:
        """
        Generate properly aligned exports path for NetSuite CSV, mapped CSV files.
        
        Format: exports/COMPANY/DOC_TYPE/batch_N/file.ext
        """
        return f"exports/{company_code}/{doc_type_code}/batch_{batch_id}/{filename}"
    
    @staticmethod
    def get_backup_path(company_code: str, doc_type_code: str, backup_type: str, filename: str) -> str:
        """
        Generate backup path.
        
        Format: backups/TYPE/COMPANY/DOC_TYPE/YYYY-MM-DD/file.ext
        """
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        return f"backups/{backup_type}/{company_code}/{doc_type_code}/{date_str}/{filename}"
    
    @staticmethod
    def fix_legacy_batch_results_path(legacy_path: str) -> Optional[str]:
        """
        Convert legacy batch results path to new structure.
        
        Args:
            legacy_path: Legacy path like "upload/batch_results/COMPANY/DOC_TYPE/batch_N/file.ext"
            
        Returns:
            New path like "results/COMPANY/DOC_TYPE/batch_N/file.ext" or None if invalid
        """
        if not legacy_path:
            return None
        
        # Handle both full S3 URIs and relative paths
        if legacy_path.startswith('s3://'):
            # Extract path part from S3 URI
            uri_parts = legacy_path.split('/', 3)
            if len(uri_parts) < 4:
                return None
            bucket = uri_parts[2]
            path_part = uri_parts[3]
        else:
            path_part = legacy_path
            bucket = None
        
        # Check if it's a legacy batch results path
        if path_part.startswith('upload/batch_results/'):
            # Remove the upload/batch_results/ prefix and add results/ prefix
            new_path = path_part.replace('upload/batch_results/', 'results/')
            
            # Reconstruct S3 URI if original was a URI
            if bucket:
                return f"s3://{bucket}/{new_path}"
            else:
                return new_path
        
        return legacy_path  # Return as-is if not a legacy path
    
    @staticmethod
    def ensure_correct_folder_prefix(s3_manager, file_key: str, desired_folder: str) -> str:
        """
        Ensure file has correct folder prefix, accounting for S3 manager prefixes.
        
        Args:
            s3_manager: S3 storage manager instance
            file_key: Current file key
            desired_folder: Desired folder (results, exports, backups)
            
        Returns:
            Corrected file key
        """
        # Remove any existing upload/ prefix that S3Manager might add
        if file_key.startswith('upload/'):
            file_key = file_key[7:]  # Remove 'upload/' prefix
        
        # Ensure it starts with the desired folder
        if not file_key.startswith(f"{desired_folder}/"):
            # If it has a different folder prefix, replace it
            for folder in ['results', 'exports', 'backups', 'prompts', 'schemas']:
                if file_key.startswith(f"{folder}/"):
                    file_key = file_key.replace(f"{folder}/", f"{desired_folder}/", 1)
                    break
            else:
                # No folder prefix, add the desired one
                file_key = f"{desired_folder}/{file_key}"
        
        return file_key
    
    @staticmethod
    def upload_to_results_folder(s3_manager, content: bytes, company_code: str, 
                                doc_type_code: str, batch_id: int, filename: str) -> Optional[str]:
        """
        Upload file directly to results folder with correct path structure.
        
        Returns:
            S3 URI if successful, None if failed
        """
        try:
            # Generate correct results path
            results_key = S3PathFixer.get_results_path(company_code, doc_type_code, batch_id, filename)
            
            # Upload directly without going through upload/ prefix
            s3_manager.s3_client.put_object(
                Bucket=s3_manager.bucket_name,
                Key=results_key,
                Body=content,
                ContentType='application/json' if filename.endswith('.json') else 'text/csv'
            )
            
            # Return full S3 URI
            s3_uri = f"s3://{s3_manager.bucket_name}/{results_key}"
            logger.info(f"✅ Uploaded to results folder: {s3_uri}")
            return s3_uri
            
        except Exception as e:
            logger.error(f"❌ Failed to upload to results folder: {e}")
            return None
    
    @staticmethod
    def upload_to_exports_folder(s3_manager, content: bytes, company_code: str, 
                                doc_type_code: str, batch_id: int, filename: str) -> Optional[str]:
        """
        Upload file directly to exports folder with correct path structure.
        
        Returns:
            S3 URI if successful, None if failed
        """
        try:
            # Generate correct exports path
            exports_key = S3PathFixer.get_exports_path(company_code, doc_type_code, batch_id, filename)
            
            # Upload directly to exports folder
            s3_manager.s3_client.put_object(
                Bucket=s3_manager.bucket_name,
                Key=exports_key,
                Body=content,
                ContentType='text/csv' if filename.endswith('.csv') else 'application/octet-stream'
            )
            
            # Return full S3 URI
            s3_uri = f"s3://{s3_manager.bucket_name}/{exports_key}"
            logger.info(f"✅ Uploaded to exports folder: {s3_uri}")
            return s3_uri
            
        except Exception as e:
            logger.error(f"❌ Failed to upload to exports folder: {e}")
            return None


# Convenience functions for easy import
def fix_batch_results_paths():
    """Fix existing batch results paths in database."""
    from ..utils.s3_structure_migration import run_s3_migration
    return run_s3_migration()


def get_aligned_results_path(company_code: str, doc_type_code: str, batch_id: int, filename: str) -> str:
    """Get aligned results path for new uploads."""
    return S3PathFixer.get_results_path(company_code, doc_type_code, batch_id, filename)


def get_aligned_exports_path(company_code: str, doc_type_code: str, batch_id: int, filename: str) -> str:
    """Get aligned exports path for NetSuite/CSV files."""
    return S3PathFixer.get_exports_path(company_code, doc_type_code, batch_id, filename)