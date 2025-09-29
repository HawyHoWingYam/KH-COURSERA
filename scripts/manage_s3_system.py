#!/usr/bin/env python3
"""
S3 System Management Script
Comprehensive management tool for S3 file storage system improvements.
"""

import sys
import os
import logging
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent / "GeminiOCR" / "backend"
sys.path.insert(0, str(backend_dir))

from utils.s3_structure_migration import S3StructureMigrationManager, run_s3_migration
from utils.enhanced_file_manager import EnhancedFileManager, standardize_s3_structure
from utils.backup_manager import S3BackupManager, initialize_backup_system, BackupType
from utils.s3_storage import get_s3_manager
from db.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3SystemManager:
    """Comprehensive S3 system management."""
    
    def __init__(self):
        self.s3_manager = get_s3_manager()
        if not self.s3_manager:
            raise RuntimeError("S3 manager not available. Check AWS credentials and configuration.")
        
        self.migration_manager = S3StructureMigrationManager(self.s3_manager)
        self.enhanced_file_manager = EnhancedFileManager(self.s3_manager)
        self.backup_manager = S3BackupManager(self.s3_manager)
    
    def run_comprehensive_setup(self) -> Dict:
        """Run comprehensive S3 system setup and improvements."""
        print("🚀 Starting comprehensive S3 system setup...")
        print("="*70)
        
        setup_results = {
            'start_time': datetime.now().isoformat(),
            'steps_completed': [],
            'steps_failed': [],
            'total_time': 0,
            'success': True
        }
        
        steps = [
            ('analyze_current_structure', '📊 Analyzing current S3 structure'),
            ('fix_structure_issues', '🔧 Fixing structure alignment issues'),
            ('standardize_folders', '📁 Standardizing folder structure'),
            ('initialize_backups', '💾 Initializing backup system'),
            ('generate_missing_csvs', '📈 Generating missing CSV outputs'),
            ('cleanup_and_optimize', '🧹 Cleanup and optimization'),
            ('create_system_backup', '🗄️ Creating system backup')
        ]
        
        start_time = datetime.now()
        
        try:
            for step_method, step_description in steps:
                print(f"\n{step_description}")
                print("-" * 50)
                
                try:
                    method = getattr(self, step_method)
                    result = method()
                    
                    setup_results['steps_completed'].append({
                        'step': step_method,
                        'description': step_description,
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    print(f"✅ {step_description} - Completed")
                    
                except Exception as e:
                    error_info = {
                        'step': step_method,
                        'description': step_description,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    setup_results['steps_failed'].append(error_info)
                    
                    print(f"❌ {step_description} - Failed: {e}")
                    logger.error(f"Step {step_method} failed: {e}")
        
        except Exception as e:
            setup_results['success'] = False
            setup_results['global_error'] = str(e)
            print(f"\n❌ Setup failed with global error: {e}")
        
        finally:
            end_time = datetime.now()
            setup_results['end_time'] = end_time.isoformat()
            setup_results['total_time'] = (end_time - start_time).total_seconds()
            
            self._print_setup_summary(setup_results)
        
        return setup_results
    
    def analyze_current_structure(self):
        """Analyze current S3 structure."""
        return self.migration_manager.analyze_current_structure()
    
    def fix_structure_issues(self):
        """Fix S3 structure alignment issues."""
        db = next(get_db())
        try:
            return self.migration_manager.run_comprehensive_migration(db)
        finally:
            db.close()
    
    def standardize_folders(self):
        """Standardize folder structure."""
        return self.enhanced_file_manager.enforce_folder_structure()
    
    def initialize_backups(self):
        """Initialize backup system."""
        return self.backup_manager.initialize_backup_structure()
    
    def generate_missing_csvs(self):
        """Generate missing CSV output files."""
        db = next(get_db())
        try:
            return self.migration_manager.implement_csv_output_generation(db)
        finally:
            db.close()
    
    def cleanup_and_optimize(self):
        """Cleanup and optimize S3 storage."""
        cleanup_results = {
            'old_backups_cleaned': 0,
            'space_freed': 0,
            'optimizations_applied': 0
        }
        
        try:
            # Cleanup old backups
            backup_cleanup = self.backup_manager.cleanup_old_backups()
            cleanup_results['old_backups_cleaned'] = backup_cleanup.get('backups_deleted', 0)
            cleanup_results['space_freed'] = backup_cleanup.get('space_freed', 0)
            
            # Get folder statistics for optimization insights
            stats = self.enhanced_file_manager.get_folder_statistics()
            cleanup_results['folder_statistics'] = stats
            cleanup_results['optimizations_applied'] = 1
            
        except Exception as e:
            cleanup_results['error'] = str(e)
        
        return cleanup_results
    
    def create_system_backup(self):
        """Create comprehensive system backup."""
        db = next(get_db())
        try:
            # Create database backup
            db_backup = self.backup_manager.create_database_backup(db)
            
            # Create configuration backup
            config_backup = self.backup_manager.create_configuration_backup(db)
            
            return {
                'database_backup': db_backup,
                'configuration_backup': config_backup
            }
        finally:
            db.close()
    
    def _print_setup_summary(self, results):
        """Print comprehensive setup summary."""
        print("\n" + "="*70)
        print("🏁 COMPREHENSIVE S3 SETUP SUMMARY")
        print("="*70)
        
        print(f"⏱️  Total setup time: {results['total_time']:.2f} seconds")
        print(f"✅ Steps completed: {len(results['steps_completed'])}")
        print(f"❌ Steps failed: {len(results['steps_failed'])}")
        
        if results['success']:
            print("\n🎉 Setup completed successfully!")
        else:
            print("\n⚠️  Setup completed with some issues")
        
        # Print completed steps summary
        if results['steps_completed']:
            print("\n📋 COMPLETED STEPS:")
            for step in results['steps_completed']:
                print(f"  ✅ {step['description']}")
                # Print key metrics if available
                result = step.get('result', {})
                if isinstance(result, dict):
                    for key, value in result.items():
                        if key in ['files_migrated', 'folders_created', 'jobs_updated', 'files_backed_up']:
                            print(f"      {key}: {value}")
        
        # Print failed steps
        if results['steps_failed']:
            print("\n⚠️  FAILED STEPS:")
            for step in results['steps_failed']:
                print(f"  ❌ {step['description']}: {step['error']}")
        
        print("="*70)
    
    def run_health_check(self):
        """Run comprehensive S3 system health check."""
        print("🏥 Running S3 System Health Check...")
        print("="*50)
        
        health_results = {
            's3_connectivity': False,
            'folder_structure': {},
            'backup_system': {},
            'recent_activity': {},
            'recommendations': []
        }
        
        try:
            # Check S3 connectivity
            s3_health = self.s3_manager.get_health_status()
            health_results['s3_connectivity'] = s3_health.get('accessible', False)
            print(f"S3 Connectivity: {'✅ Healthy' if health_results['s3_connectivity'] else '❌ Issues'}")
            
            # Check folder structure
            folder_stats = self.enhanced_file_manager.get_folder_statistics()
            health_results['folder_structure'] = folder_stats
            
            print(f"\n📁 Folder Structure:")
            for folder, stats in folder_stats.items():
                if isinstance(stats, dict):
                    file_count = stats.get('file_count', 0)
                    print(f"  {folder}: {file_count} files")
            
            # Check backup system
            backups = self.backup_manager.list_available_backups()
            health_results['backup_system'] = backups
            
            print(f"\n💾 Backup System:")
            for backup_type, backup_list in backups.items():
                if backup_type != 'error' and isinstance(backup_list, list):
                    print(f"  {backup_type}: {len(backup_list)} backups")
            
            # Generate recommendations
            recommendations = self._generate_health_recommendations(health_results)
            health_results['recommendations'] = recommendations
            
            if recommendations:
                print(f"\n💡 Recommendations:")
                for rec in recommendations:
                    print(f"  • {rec}")
        
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            health_results['error'] = str(e)
        
        return health_results
    
    def _generate_health_recommendations(self, health_results):
        """Generate health recommendations based on check results."""
        recommendations = []
        
        if not health_results['s3_connectivity']:
            recommendations.append("Fix S3 connectivity issues")
        
        folder_stats = health_results.get('folder_structure', {})
        
        # Check for empty critical folders
        for folder in ['results', 'exports']:
            if folder in folder_stats:
                stats = folder_stats[folder]
                if isinstance(stats, dict) and stats.get('file_count', 0) == 0:
                    recommendations.append(f"Generate missing files in {folder} folder")
        
        # Check backup recency
        backup_system = health_results.get('backup_system', {})
        if not backup_system.get('database'):
            recommendations.append("Create initial database backup")
        
        return recommendations


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(description='S3 System Management Tool')
    parser.add_argument('command', choices=[
        'setup', 'health', 'migrate', 'backup', 'analyze', 'standardize'
    ], help='Command to execute')
    
    parser.add_argument('--company-id', type=int, help='Company ID for specific operations')
    parser.add_argument('--backup-type', choices=['database', 'configurations'], 
                       help='Type of backup to create')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Perform dry run without making changes')
    
    args = parser.parse_args()
    
    try:
        manager = S3SystemManager()
        
        if args.command == 'setup':
            result = manager.run_comprehensive_setup()
            success = result.get('success', False)
            
        elif args.command == 'health':
            result = manager.run_health_check()
            success = 'error' not in result
            
        elif args.command == 'migrate':
            db = next(get_db())
            try:
                if args.dry_run:
                    result = manager.migration_manager.analyze_current_structure()
                else:
                    result = manager.migration_manager.run_comprehensive_migration(db)
                success = result.get('success', False)
            finally:
                db.close()
                
        elif args.command == 'backup':
            if args.backup_type == 'database':
                db = next(get_db())
                try:
                    result = manager.backup_manager.create_database_backup(db)
                    success = result.get('status') == 'completed'
                finally:
                    db.close()
            elif args.backup_type == 'configurations':
                db = next(get_db())
                try:
                    result = manager.backup_manager.create_configuration_backup(db, args.company_id)
                    success = result.get('status') == 'completed'
                finally:
                    db.close()
            else:
                result = manager.backup_manager.initialize_backup_structure()
                success = result.get('success', False)
                
        elif args.command == 'analyze':
            result = manager.migration_manager.analyze_current_structure()
            success = True
            
        elif args.command == 'standardize':
            result = manager.enhanced_file_manager.enforce_folder_structure()
            success = result.get('success', False)
            
        else:
            print(f"Unknown command: {args.command}")
            success = False
            result = {'error': 'Unknown command'}
        
        # Print results summary
        print(f"\n{'✅ Success' if success else '❌ Failed'}")
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"\n❌ Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()