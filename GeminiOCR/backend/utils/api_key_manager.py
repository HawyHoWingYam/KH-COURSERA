import json
import random
import logging
from functools import wraps
import time
import os

logger = logging.getLogger(__name__)

class ApiKeyManager:
    def __init__(self, config_path='env/config.json'):
        self.config_path = config_path
        self._load_keys()
        self.current_key_index = random.randint(0, len(self.api_keys) - 1) if self.api_keys else 0
        
    def _load_keys(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Handle both formats: single key or array of keys
            if 'api_keys' in config and isinstance(config['api_keys'], list):
                self.api_keys = config['api_keys']
            elif 'api_key' in config:
                self.api_keys = [config['api_key']]
            else:
                self.api_keys = []
                logger.error("No API keys found in config file")
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            self.api_keys = []
            
    def get_current_key(self):
        """Get the currently selected API key"""
        if not self.api_keys:
            raise ValueError("No API keys available")
        return self.api_keys[self.current_key_index]
    
    def rotate_key(self):
        """Rotate to the next API key in the list"""
        if len(self.api_keys) <= 1:
            logger.warning("Only one API key available, cannot rotate")
            return self.get_current_key()
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Rotated to API key index {self.current_key_index}")
        return self.get_current_key()

# Create a singleton instance
key_manager = ApiKeyManager()

def with_api_key_retry(max_retries=2):
    """
    Decorator to retry API calls with different keys on failure
    
    Usage:
    @with_api_key_retry()
    def call_gemini_api(api_key, ...):
        # Your API call logic here
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            last_exception = None
            
            while retries < max_retries:
                try:
                    # Get current API key and inject it into the function call
                    api_key = key_manager.get_current_key()
                    if 'api_key' in kwargs:
                        kwargs['api_key'] = api_key
                    else:
                        # Try to find where to inject the API key based on function signature
                        # This assumes the first parameter is the API key
                        args = list(args)
                        args[0] = api_key
                        args = tuple(args)
                    
                    # Call the original function
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    logger.warning(f"API call failed with key {key_manager.current_key_index}: {str(e)}")
                    key_manager.rotate_key()
                    retries += 1
                    
            # If we've exhausted all retries, raise the last exception
            logger.error(f"All API keys failed after {max_retries} attempts")
            raise last_exception
            
        return wrapper
    return decorator
