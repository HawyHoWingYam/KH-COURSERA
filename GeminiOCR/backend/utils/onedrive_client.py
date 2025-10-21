"""OneDrive integration client using O365 library"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from O365 import Account
from O365.drive import File as O365File, Folder as O365Folder

logger = logging.getLogger(__name__)


class OneDriveClient:
    """Client for OneDrive operations"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        target_user_upn: Optional[str] = None,
        scopes: Optional[List[str]] = None
    ):
        """Initialize OneDrive client

        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            tenant_id: Azure AD tenant ID
            target_user_upn: Target user UPN for app-only access (e.g., user@domain.com)
            scopes: OAuth scopes (default: Files.ReadWrite.All)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.target_user_upn = target_user_upn

        if scopes is None:
            scopes = ['https://graph.microsoft.com/Files.ReadWrite.All']

        self.scopes = scopes
        self.account = None
        self.storage = None
        self.drive = None

    def connect(self) -> bool:
        """Authenticate and establish connection"""
        try:
            credentials = (self.client_id, self.client_secret)

            # Create account with client credentials flow
            self.account = Account(
                credentials,
                auth_flow_type='credentials',
                tenant_id=self.tenant_id
            )

            # Authenticate
            if not self.account.is_authenticated:
                self.account.authenticate()

            # Get storage for specific user (app-only) or default (delegated auth)
            if self.target_user_upn:
                # Access specific user's OneDrive using app-only authentication
                self.storage = self.account.storage(resource=self.target_user_upn)
                logger.info(f"✅ Connected to OneDrive (app-only mode for user: {self.target_user_upn})")
            else:
                # Access default drive (delegated auth - requires user context)
                self.storage = self.account.storage()
                logger.info("✅ Connected to OneDrive (default drive)")

            self.drive = self.storage.get_default_drive()
            logger.info("✅ Successfully obtained drive object")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to OneDrive: {str(e)}")
            return False

    def get_folder(self, folder_path: str) -> Optional[O365Folder]:
        """Get folder by path

        Args:
            folder_path: Folder path (e.g., "/Shared Documents/AWB")

        Returns:
            Folder object or None if not found
        """
        if not self.drive:
            logger.error("❌ Drive not connected. Call connect() first.")
            return None

        try:
            # Remove leading/trailing slashes
            folder_path = folder_path.strip('/')

            # Get folder by path
            folder = self.drive.get_item_by_path(folder_path)

            if folder and folder.is_folder:
                logger.info(f"✅ Found folder: {folder_path}")
                return folder
            else:
                logger.warning(f"⚠️ Path not found or not a folder: {folder_path}")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting folder {folder_path}: {str(e)}")
            return None

    def list_new_files(
        self,
        folder: O365Folder,
        since_date: datetime,
        file_extensions: Optional[List[str]] = None
    ) -> List[O365File]:
        """List new files in folder modified after since_date

        Args:
            folder: Folder object
            since_date: Only return files modified after this date
            file_extensions: Filter by extensions (e.g., ['.pdf', '.xlsx'])

        Returns:
            List of new files
        """
        if not folder:
            return []

        try:
            if file_extensions is None:
                file_extensions = ['.pdf']

            # Ensure since_date is timezone-aware (UTC)
            if since_date.tzinfo is None:
                # Make it aware in UTC
                since_date = since_date.replace(tzinfo=timezone.utc)

            new_files = []

            # Get items in folder
            for item in folder.get_items():
                # Check if file and modified after since_date
                if item.is_file:
                    # Check modification time
                    modified = item.modified
                    if modified and modified >= since_date:
                        # Check extension
                        if any(item.name.lower().endswith(ext) for ext in file_extensions):
                            new_files.append(item)
                            logger.info(f"✅ Found new file: {item.name} (modified: {modified})")

            logger.info(f"✅ Found {len(new_files)} new files")
            return new_files

        except Exception as e:
            logger.error(f"❌ Error listing files: {str(e)}")
            return []

    def download_file(self, file_item: O365File, local_path: str) -> bool:
        """Download file to local path

        Args:
            file_item: File object
            local_path: Local directory to download to

        Returns:
            True if successful, False otherwise
        """
        if not file_item:
            return False

        try:
            file_item.download(to_path=local_path)
            logger.info(f"✅ Downloaded file: {file_item.name} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error downloading file {file_item.name}: {str(e)}")
            return False

    def move_file(
        self,
        file_item: O365File,
        target_folder: O365Folder,
        new_name: Optional[str] = None
    ) -> bool:
        """Move file to target folder

        Args:
            file_item: File object
            target_folder: Target folder object
            new_name: Optional new filename

        Returns:
            True if successful, False otherwise
        """
        if not file_item or not target_folder:
            return False

        try:
            file_item.move(target_folder, name=new_name)
            logger.info(f"✅ Moved file: {file_item.name} to {target_folder.name}")
            return True

        except Exception as e:
            logger.error(f"❌ Error moving file {file_item.name}: {str(e)}")
            return False

    def get_or_create_folder(
        self,
        parent_folder: O365Folder,
        folder_name: str
    ) -> Optional[O365Folder]:
        """Get or create folder in parent

        Args:
            parent_folder: Parent folder
            folder_name: Name of folder to get/create

        Returns:
            Folder object or None on error
        """
        if not parent_folder:
            return None

        try:
            # Try to get existing folder
            for item in parent_folder.get_items():
                if item.is_folder and item.name == folder_name:
                    logger.info(f"✅ Found existing folder: {folder_name}")
                    return item

            # Create new folder if not found
            new_folder = parent_folder.create_child_folder(folder_name)
            logger.info(f"✅ Created new folder: {folder_name}")
            return new_folder

        except Exception as e:
            logger.error(f"❌ Error getting/creating folder {folder_name}: {str(e)}")
            return None

    def close(self) -> None:
        """Close connection"""
        if self.account:
            try:
                # O365 doesn't require explicit close, but good practice
                logger.info("✅ OneDrive client closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing client: {str(e)}")
