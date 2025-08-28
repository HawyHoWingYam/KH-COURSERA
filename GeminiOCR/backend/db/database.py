from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import json
import urllib.parse
import logging

logger = logging.getLogger(__name__)

# Read database URL from config.json
with open('env/config.json') as f:
    config = json.load(f)
    DATABASE_URL = config['database_url']

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define Base for model inheritance
Base = declarative_base()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_database_url():
    """
    Get database URL either from AWS Secrets Manager or fallback to config.json
    """
    try:
        # Try to get database credentials from AWS Secrets Manager
        # ... existing code ...
        
    except Exception as e:
        logger.warning(f"Failed to load credentials from AWS Secrets Manager: {e}")
        logger.info("Falling back to config.json for database credentials")
        
        # Fallback to config.json
        try:
            with open('env/config.json') as f:
                config = json.load(f)
                database_url = config.get('database_url')
                
                # If the URL contains special characters, ensure it's properly formatted
                if database_url:
                    # Parse the URL to extract components
                    parts = database_url.split('@')
                    if len(parts) == 2:
                        auth_part = parts[0]
                        host_part = parts[1]
                        
                        # Extract username and password
                        auth_parts = auth_part.split('://', 1)[1].split(':', 1)
                        if len(auth_parts) == 2:
                            username = auth_parts[0]
                            password = auth_parts[1]
                            
                            # URL encode the password to handle special characters
                            encoded_password = urllib.parse.quote_plus(password)
                            
                            # Reconstruct the URL
                            protocol = auth_part.split('://', 1)[0]
                            database_url = f"{protocol}://{username}:{encoded_password}@{host_part}"
                    
                    return database_url
                else:
                    raise ValueError("Database URL not found in config.json and AWS Secrets Manager unavailable")
        except Exception as config_error:
            logger.error(f"Failed to load database URL from config.json: {config_error}")
            raise ValueError(f"Database configuration not available: {config_error}")
