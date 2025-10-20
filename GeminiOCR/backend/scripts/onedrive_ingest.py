"""OneDrive daily sync script - Downloads new AWB PDFs to S3"""
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils.onedrive_client import OneDriveClient
from utils.s3_storage import S3StorageManager
from db.models import File, OneDriveSync
from config_loader import config_loader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration
ONEDRIVE_CLIENT_ID = os.getenv('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.getenv('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_TENANT_ID = os.getenv('ONEDRIVE_TENANT_ID')
ONEDRIVE_SHARED_FOLDER_PATH = os.getenv('ONEDRIVE_SHARED_FOLDER_PATH', '/Shared Documents/AWB')
ONEDRIVE_PROCESSED_FOLDER = os.getenv('ONEDRIVE_PROCESSED_FOLDER', '已处理')
AWB_S3_PREFIX = os.getenv('AWB_S3_PREFIX', 'upload/onedrive/airway-bills')

# Database setup
DATABASE_URL = config_loader.get('database_url')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Get database session"""
    return SessionLocal()


def run_onedrive_sync():
    """Run OneDrive sync: Download new AWBs to S3"""
    sync_start = datetime.utcnow()
    db = get_db_session()

    try:
        logger.info("🔄 Starting OneDrive sync...")

        # Initialize clients
        onedrive_client = OneDriveClient(
            client_id=ONEDRIVE_CLIENT_ID,
            client_secret=ONEDRIVE_CLIENT_SECRET,
            tenant_id=ONEDRIVE_TENANT_ID
        )

        s3_manager = S3StorageManager()

        # Connect to OneDrive
        if not onedrive_client.connect():
            raise Exception("Failed to connect to OneDrive")

        # Get source and processed folders
        source_folder = onedrive_client.get_folder(ONEDRIVE_SHARED_FOLDER_PATH)
        if not source_folder:
            raise Exception(f"Source folder not found: {ONEDRIVE_SHARED_FOLDER_PATH}")

        # Get processed folder, create if doesn't exist
        processed_folder = onedrive_client.get_or_create_folder(
            source_folder.parent,
            ONEDRIVE_PROCESSED_FOLDER
        )

        # Get last sync time from database
        last_sync = db.query(OneDriveSync).order_by(
            OneDriveSync.created_at.desc()
        ).first()

        since_date = (last_sync.last_sync_time if last_sync else datetime.utcnow() - timedelta(days=1))
        logger.info(f"📅 Syncing files modified after: {since_date}")

        # List new files
        new_files = onedrive_client.list_new_files(
            source_folder,
            since_date,
            file_extensions=['.pdf']
        )

        if not new_files:
            logger.info("✅ No new files to process")
            # Record sync in DB
            record_sync(db, 'success', 0, 0, None)
            db.close()
            return

        # Process each file
        files_processed = 0
        files_failed = 0
        errors = []

        for file_item in new_files:
            try:
                logger.info(f"📄 Processing: {file_item.name}")

                # Check for duplicates
                source_path = f"onedrive://{file_item.parent.remote_item.get('id')}/{file_item.object_id}"
                existing = db.query(File).filter(File.source_path == source_path).first()

                if existing:
                    logger.info(f"⏭️  File already processed (skipping): {file_item.name}")
                    files_processed += 1
                    continue

                # Download to temp location
                with tempfile.TemporaryDirectory() as temp_dir:
                    if not onedrive_client.download_file(file_item, temp_dir):
                        raise Exception(f"Failed to download {file_item.name}")

                    # Upload to S3 with organized path
                    today = datetime.now()
                    s3_key = f"{AWB_S3_PREFIX}/{today.year:04d}/{today.month:02d}/{today.day:02d}/{file_item.name}"

                    temp_file_path = os.path.join(temp_dir, file_item.name)
                    s3_manager.upload_file(temp_file_path, s3_key)
                    logger.info(f"☁️  Uploaded to S3: {s3_key}")

                    # Record in database
                    file_record = File(
                        file_name=file_item.name,
                        file_path=s3_key,  # Store S3 path
                        file_type='application/pdf',
                        s3_bucket=s3_manager.bucket_name,
                        s3_key=s3_key,
                        source_system='onedrive',
                        source_path=source_path,
                        source_metadata={
                            'onedrive_id': file_item.object_id,
                            'modified': file_item.modified.isoformat() if file_item.modified else None,
                            'created_by': file_item.created_by.split('@')[0] if file_item.created_by else None,
                        }
                    )
                    db.add(file_record)
                    db.commit()
                    logger.info(f"💾 Recorded in DB: {file_item.name}")

                    # Move file to processed folder
                    if processed_folder:
                        onedrive_client.move_file(file_item, processed_folder)
                        logger.info(f"✅ Moved to processed folder: {file_item.name}")

                files_processed += 1

            except Exception as e:
                logger.error(f"❌ Error processing {file_item.name}: {str(e)}")
                files_failed += 1
                errors.append(f"{file_item.name}: {str(e)}")

        # Record final sync status
        error_message = '\n'.join(errors) if errors else None
        record_sync(db, 'success', files_processed, files_failed, error_message)

        logger.info(f"✅ OneDrive sync completed: {files_processed} processed, {files_failed} failed")

    except Exception as e:
        logger.error(f"❌ OneDrive sync failed: {str(e)}")
        record_sync(db, 'failed', 0, 0, str(e))

    finally:
        db.close()
        onedrive_client.close()


def record_sync(db, status: str, files_processed: int, files_failed: int, error_msg: str = None):
    """Record sync status in database"""
    try:
        sync_record = OneDriveSync(
            last_sync_time=datetime.utcnow(),
            sync_status=status,
            files_processed=files_processed,
            files_failed=files_failed,
            error_message=error_msg,
            sync_metadata={
                's3_prefix': AWB_S3_PREFIX,
                'onedrive_folder': ONEDRIVE_SHARED_FOLDER_PATH
            }
        )
        db.add(sync_record)
        db.commit()
        logger.info(f"📊 Recorded sync: {status} ({files_processed} processed, {files_failed} failed)")
    except Exception as e:
        logger.error(f"⚠️  Failed to record sync: {str(e)}")


if __name__ == '__main__':
    run_onedrive_sync()
