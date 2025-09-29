#!/usr/bin/env python3
"""
S3 Structure Fix Script
Fixes S3 file storage structure alignment issues and implements missing features.
"""

import sys
import os
import logging
import json
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent / "GeminiOCR" / "backend"
sys.path.insert(0, str(backend_dir))

from utils.s3_structure_migration import S3StructureMigrationManager, run_s3_migration
from utils.s3_storage import get_s3_manager
from db.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_analysis_only():
    """Run analysis only without making changes."""
    logger.info("Running S3 structure analysis only...")
    
    s3_manager = get_s3_manager()
    if not s3_manager:
        logger.error("S3 manager not available")
        return False
    
    migration_manager = S3StructureMigrationManager(s3_manager)
    analysis = migration_manager.analyze_current_structure()
    
    # Print analysis results
    print("\n" + "="*60)
    print("S3 STRUCTURE ANALYSIS RESULTS")
    print("="*60)
    
    # Folder structure
    print("\n📁 FOLDER STRUCTURE:")
    for folder, info in analysis.get('folder_structure', {}).items():
        print(f"  {folder}:")
        print(f"    Files: {info.get('total_files', 0)}")
        print(f"    Size: {info.get('size_total', 0) / (1024*1024):.2f} MB")
        
        patterns = info.get('patterns', {})
        print(f"    Patterns:")
        for pattern, count in patterns.items():
            print(f"      {pattern}: {count}")
    
    # Alignment issues
    issues = analysis.get('alignment_issues', [])
    print(f"\n⚠️  ALIGNMENT ISSUES ({len(issues)} found):")
    for issue in issues:
        print(f"  • {issue.get('type', 'unknown')}: {issue.get('description', 'No description')}")
        if 'file' in issue:
            print(f"    File: {issue['file']}")
    
    # Recommendations
    recommendations = analysis.get('recommendations', [])
    print(f"\n💡 RECOMMENDATIONS ({len(recommendations)} items):")
    for rec in recommendations:
        priority = rec.get('priority', 'medium').upper()
        print(f"  [{priority}] {rec.get('description', 'No description')}")
        print(f"      Action: {rec.get('action', 'undefined')}")
    
    print("="*60)
    return True


def run_batch_results_fix():
    """Fix batch results structure only."""
    logger.info("Running batch results structure fix...")
    
    s3_manager = get_s3_manager()
    if not s3_manager:
        logger.error("S3 manager not available")
        return False
    
    migration_manager = S3StructureMigrationManager(s3_manager)
    results = migration_manager.fix_batch_results_structure()
    
    print("\n" + "="*40)
    print("BATCH RESULTS FIX RESULTS")
    print("="*40)
    print(f"Files moved: {results.get('moved_files', 0)}")
    print(f"Files skipped: {results.get('skipped_files', 0)}")
    print(f"Errors: {results.get('errors', 0)}")
    print("="*40)
    
    return results.get('errors', 0) == 0


def run_csv_generation():
    """Implement CSV output generation for existing batch jobs."""
    logger.info("Running CSV output generation implementation...")
    
    s3_manager = get_s3_manager()
    if not s3_manager:
        logger.error("S3 manager not available")
        return False
    
    migration_manager = S3StructureMigrationManager(s3_manager)
    
    # Get database session
    db = next(get_db())
    try:
        results = migration_manager.implement_csv_output_generation(db)
        
        print("\n" + "="*40)
        print("CSV GENERATION RESULTS")
        print("="*40)
        print(f"Jobs updated: {results.get('jobs_updated', 0)}")
        print(f"CSV files generated: {results.get('csv_files_generated', 0)}")
        print(f"Errors: {results.get('errors', 0)}")
        print("="*40)
        
        return results.get('errors', 0) == 0
        
    finally:
        db.close()


def run_folder_standardization():
    """Standardize S3 folder structure."""
    logger.info("Running folder structure standardization...")
    
    s3_manager = get_s3_manager()
    if not s3_manager:
        logger.error("S3 manager not available")
        return False
    
    migration_manager = S3StructureMigrationManager(s3_manager)
    results = migration_manager.standardize_folder_structure()
    
    print("\n" + "="*40)
    print("FOLDER STANDARDIZATION RESULTS")
    print("="*40)
    print(f"Folders created: {results.get('folders_created', 0)}")
    print(f"Structures aligned: {results.get('structures_aligned', 0)}")
    print(f"Errors: {results.get('errors', 0)}")
    print("="*40)
    
    return results.get('errors', 0) == 0


def run_backup_support():
    """Add backup folder support."""
    logger.info("Adding backup folder support...")
    
    s3_manager = get_s3_manager()
    if not s3_manager:
        logger.error("S3 manager not available")
        return False
    
    migration_manager = S3StructureMigrationManager(s3_manager)
    
    # Get database session
    db = next(get_db())
    try:
        results = migration_manager.add_backups_folder_support(db)
        
        print("\n" + "="*40)
        print("BACKUP SUPPORT RESULTS")
        print("="*40)
        print(f"Backup folders initialized: {results.get('backup_folders_initialized', 0)}")
        print(f"Backup policies created: {results.get('backup_policies_created', 0)}")
        print(f"Errors: {results.get('errors', 0)}")
        print("="*40)
        
        return results.get('errors', 0) == 0
        
    finally:
        db.close()


def run_full_migration():
    """Run comprehensive S3 structure migration."""
    logger.info("Running comprehensive S3 structure migration...")
    
    results = run_s3_migration()
    if not results:
        logger.error("Migration failed")
        return False
    
    # Print detailed results
    print("\n" + "="*60)
    print("COMPREHENSIVE MIGRATION RESULTS")
    print("="*60)
    
    if results.get('success'):
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration completed with errors")
        if 'error' in results:
            print(f"Main error: {results['error']}")
    
    print(f"Total time: {results.get('total_time', 0):.2f} seconds")
    
    # Print each step's results
    steps = [
        ('analysis', 'ANALYSIS'),
        ('batch_results_fix', 'BATCH RESULTS FIX'),
        ('csv_generation', 'CSV GENERATION'),
        ('folder_standardization', 'FOLDER STANDARDIZATION'),
        ('backup_support', 'BACKUP SUPPORT')
    ]
    
    for step_key, step_name in steps:
        step_results = results.get(step_key, {})
        if step_results:
            print(f"\n📊 {step_name}:")
            
            if step_key == 'analysis':
                # Special handling for analysis
                issues = step_results.get('alignment_issues', [])
                recommendations = step_results.get('recommendations', [])
                print(f"  Issues found: {len(issues)}")
                print(f"  Recommendations: {len(recommendations)}")
            else:
                # Standard stats
                for key, value in step_results.items():
                    if isinstance(value, (int, float)):
                        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    print("="*60)
    return results.get('success', False)


def main():
    """Main script entry point."""
    if len(sys.argv) < 2:
        print("Usage: python fix_s3_structure.py <command>")
        print("\nCommands:")
        print("  analyze    - Analyze current S3 structure (read-only)")
        print("  fix-batch  - Fix batch results folder structure")
        print("  add-csv    - Implement CSV output generation")
        print("  std-folder - Standardize folder structure")
        print("  add-backup - Add backup folder support")
        print("  full       - Run comprehensive migration")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        if command == "analyze":
            success = run_analysis_only()
        elif command == "fix-batch":
            success = run_batch_results_fix()
        elif command == "add-csv":
            success = run_csv_generation()
        elif command == "std-folder":
            success = run_folder_standardization()
        elif command == "add-backup":
            success = run_backup_support()
        elif command == "full":
            success = run_full_migration()
        else:
            print(f"Unknown command: {command}")
            success = False
        
        if success:
            print("\n✅ Operation completed successfully")
            sys.exit(0)
        else:
            print("\n❌ Operation completed with errors")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"\n❌ Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()