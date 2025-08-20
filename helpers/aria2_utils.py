import aria2p
import asyncio
import logging
import os
import aiohttp
import subprocess
import time
import json
import re
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

class Aria2Manager:
    def __init__(self):
        self.client = None
        self.api = None
        self.initialized = False
        self.session = None
        self.manual_mode = False
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filenames to remove problematic characters"""
        if not filename:
            return f"file_{int(time.time())}.mkv"
            
        # Remove any invalid characters but keep spaces and common symbols
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
        
        # Ensure the filename is not empty after sanitization
        if not sanitized.strip():
            sanitized = f"file_{int(time.time())}.mkv"
            
        # Remove any leading/trailing spaces and dots
        sanitized = sanitized.strip().strip('.')
        
        # Limit length to avoid filesystem issues
        if len(sanitized) > 200:
            name, ext = os.path.splitext(sanitized)
            if not ext:
                ext = '.mkv'
            sanitized = name[:200 - len(ext)] + ext
            
        return sanitized
    
    async def initialize(self):
        """Initialize aria2c client with proper authentication handling"""
        try:
            if not settings.ARIA2_ENABLED:
                logger.info("Aria2c is disabled in configuration")
                return False
            
            logger.info(f"Attempting to connect to aria2c at {settings.ARIA2_HOST}:{settings.ARIA2_PORT}")
            
            # First, test if aria2c is running with a simple connection test
            if not await self.is_aria2c_running():
                logger.warning("Aria2c is not running, attempting to start...")
                if not await self.start_aria2c():
                    logger.error("Failed to start aria2c")
                    return False
            
            # Now try to connect with proper authentication
            try:
                self.client = aria2p.Client(
                    host=settings.ARIA2_HOST,
                    port=settings.ARIA2_PORT,
                    secret=settings.ARIA2_SECRET,
                    timeout=10
                )
                self.api = aria2p.API(self.client)
                
                # Test connection with a simple method
                version_info = self.api.client.get_version()
                logger.info(f"✅ Successfully connected to aria2c version {version_info['version']}")

                
            except aria2p.ClientException as e:
                if "Unauthorized" in str(e) or "401" in str(e):
                    logger.error("❌ Authentication failed - wrong secret key?")
                    logger.info("Please check your ARIA2_SECRET in config.py matches the aria2c config")
                    return False
                else:
                    raise e
            
            # Set options for better performance
            options = {
                "max-concurrent-downloads": str(settings.ARIA2_MAX_CONCURRENT_DOWNLOADS),
                "max-connection-per-server": str(settings.ARIA2_MAX_CONNECTION_PER_SERVER),
                "split": str(settings.ARIA2_SPLIT),
            }
            
            try:
                self.api.set_global_options(options)
            except Exception as e:
                logger.warning(f"Could not set global options: {e}")
            
            self.session = aiohttp.ClientSession()
            self.initialized = True
            logger.info("Aria2c client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize aria2c: {e}")
            self.initialized = False
            return False
    async def upload_file(self, file_path: str, endpoint: str, headers: dict = None) -> bool:
        """Upload a file to external storage (placeholder method)"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found for upload: {file_path}")
                return False
                
            logger.info(f"Would upload {file_path} to {endpoint}")
            # This is a placeholder - you need to implement actual upload logic
            # For now, just return True to indicate "success"
            return True
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False
    async def is_aria2c_running(self) -> bool:
        """Check if aria2c process is running"""
        try:
            result = subprocess.run(['pgrep', '-x', 'aria2c'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    async def start_aria2c(self) -> bool:
        """Start aria2c manually with proper configuration"""
        try:
            # Create config directory
            os.makedirs('/root/.config/aria2', exist_ok=True)
            os.makedirs('/root/downloads', exist_ok=True)
            
            # Use the secret from config (if available) or generate new one
            secret = settings.ARIA2_SECRET if settings.ARIA2_SECRET else "default_secret_123"
            
            # Create config file
            config_content = f"""dir=/root/downloads
max-concurrent-downloads={settings.ARIA2_MAX_CONCURRENT_DOWNLOADS}
max-connection-per-server={settings.ARIA2_MAX_CONNECTION_PER_SERVER}
split={settings.ARIA2_SPLIT}
min-split-size=1M
continue=true
file-allocation=prealloc
log-level=info
log=/root/aria2.log
enable-rpc=true
rpc-listen-all=true
rpc-listen-port={settings.ARIA2_PORT}
rpc-allow-origin-all=true
rpc-secret={secret}
max-overall-download-limit=0
max-download-limit=0
"""
            
            with open('/root/.config/aria2/aria2.conf', 'w') as f:
                f.write(config_content)
            
            # Start aria2c
            process = subprocess.Popen([
                'aria2c', '--conf-path=/root/.config/aria2/aria2.conf', '-D'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for startup
            await asyncio.sleep(3)
            
            if await self.is_aria2c_running():
                self.manual_mode = True
                logger.info("✅ Aria2c started manually")
                return True
            else:
                logger.error("❌ Failed to start aria2c manually")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start aria2c manually: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test if we can communicate with aria2c"""
        if not self.api:
            return False
            
        try:
            # Use a simple method to test connection
            self.api.client.get_version()
            return True
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False
    
    async def download_file(self, url: str, download_path: str, filename: str) -> Optional[str]:
        """Download a file using aria2c with proper error handling"""
        if not self.initialized or not await self.test_connection():
            logger.warning("Aria2c not available for download")
            return None
            
        # Validate inputs
        if not url or not download_path or not filename:
            logger.error(f"Invalid parameters for download: url={url}, path={download_path}, filename={filename}")
            return None
            
        try:
            # Ensure download directory exists
            os.makedirs(download_path, exist_ok=True)
            
            # Sanitize filename
            safe_filename = self.sanitize_filename(filename)
            if not safe_filename:
                logger.error(f"Failed to sanitize filename: {filename}")
                return None
                
            options = {
                "dir": download_path,
                "out": safe_filename,
            }
            
            logger.info(f"Starting aria2c download: {safe_filename} to {download_path}")
            
            # Add URI with timeout handling
            try:
                download = self.api.add_uris([url], options=options)
            except Exception as e:
                logger.error(f"Failed to add URI to aria2c: {e}")
                return None
                
            # Wait for completion with timeout
            timeout = 3600
            start_time = time.time()
            check_interval = 2  # Check every 2 seconds
            
            while download.is_active:
                current_time = time.time()
                if current_time - start_time > timeout:
                    try:
                        self.api.remove([download])
                        logger.error(f"Download timed out: {safe_filename}")
                    except:
                        pass
                    raise TimeoutError("Download timed out")
                
                try:
                    download.update()
                    # Log progress every 10 seconds
                    if int(current_time - start_time) % 10 == 0:
                        logger.debug(f"Download progress: {download.progress_string()} - {safe_filename}")
                except Exception as e:
                    logger.warning(f"Error updating download status: {e}")
                    
                await asyncio.sleep(check_interval)
                
            if download.is_complete:
                file_path = download.files[0].path
                if os.path.exists(file_path):
                    logger.info(f"✅ Download completed: {file_path}")
                    return file_path
                else:
                    logger.error(f"Download completed but file not found: {file_path}")
                    return None
            else:
                error_msg = download.error_message or "Unknown error"
                logger.error(f"❌ Download failed: {error_msg} - {safe_filename}")
                return None
                
        except Exception as e:
            logger.error(f"Aria2c download error: {e}")
            return None
    
    async def get_download_status(self) -> Dict[str, Any]:
        """Get current download status"""
        if not self.initialized or not await self.test_connection():
            return {"status": "not_connected"}
            
        try:
            stats = self.api.get_global_stats()
            downloads = self.api.get_downloads()
            
            return {
                "download_speed": stats.download_speed,
                "upload_speed": stats.upload_speed,
                "num_active": stats.num_active,
                "num_waiting": stats.num_waiting,
                "num_stopped": stats.num_stopped,
                "total_downloads": len(downloads)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        
        if self.manual_mode:
            # Kill manually started aria2c
            try:
                subprocess.run(['pkill', '-x', 'aria2c'], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
                logger.info("Stopped manually started aria2c")
            except:
                pass
        
        self.initialized = False

# Global instance
aria2_manager = Aria2Manager()
