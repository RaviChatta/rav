import aria2p
import asyncio
import logging
import os
import aiohttp
import json
from typing import Optional, List, Dict, Any
from config import settings
from urllib.parse import urlparse
import tempfile
import shutil

logger = logging.getLogger(__name__)

class Aria2Manager:
    def __init__(self):
        self.client = None
        self.api = None
        self.initialized = False
        self.session = None
        
    async def initialize(self):
        """Initialize aria2c client and session"""
        try:
            if not settings.ARIA2_ENABLED:
                logger.info("Aria2c is disabled in configuration")
                return False
                
            self.client = aria2p.Client(
                host=settings.ARIA2_HOST,
                port=settings.ARIA2_PORT,
                secret=settings.ARIA2_SECRET,
                timeout=30
            )
            self.api = aria2p.API(self.client)
            
            # Set options for faster downloads
            options = {
                "max-concurrent-downloads": str(settings.ARIA2_MAX_CONCURRENT_DOWNLOADS),
                "max-connection-per-server": str(settings.ARIA2_MAX_CONNECTION_PER_SERVER),
                "split": str(settings.ARIA2_SPLIT),
                "max-overall-download-limit": settings.ARIA2_MAX_OVERALL_DOWNLOAD_LIMIT,
                "max-download-limit": settings.ARIA2_MAX_DOWNLOAD_LIMIT,
                "max-overall-upload-limit": settings.ARIA2_MAX_OVERALL_UPLOAD_LIMIT or "0",
                "max-upload-limit": settings.ARIA2_MAX_UPLOAD_LIMIT or "0",
            }
            
            self.api.set_global_options(options)
            
            # Create aiohttp session for uploads
            self.session = aiohttp.ClientSession()
            
            self.initialized = True
            logger.info("Aria2c client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize aria2c: {e}")
            self.initialized = False
            return False
    
    async def download_file(self, url: str, download_path: str, filename: str) -> Optional[str]:
        """Download a file using aria2c"""
        if not self.initialized:
            return None
            
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            
            # Add download to aria2c
            options = {
                "dir": os.path.dirname(download_path),
                "out": filename,
            }
            
            download = self.api.add_uris([url], options=options)
            
            # Wait for download to complete with timeout
            timeout = 3600  # 1 hour timeout
            start_time = time.time()
            
            while download.is_active:
                if time.time() - start_time > timeout:
                    self.api.remove([download])
                    raise TimeoutError("Download timed out")
                
                await asyncio.sleep(2)
                download.update()
                
            if download.is_complete:
                return download.files[0].path
            else:
                logger.error(f"Download failed: {download.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Aria2c download error: {e}")
            return None
    
    async def upload_file(self, file_path: str, upload_url: str, headers: Dict[str, str] = None) -> bool:
        """Upload a file using aria2c's RPC method (for supported protocols)"""
        if not self.initialized or not self.session:
            return False
            
        try:
            # For HTTP/HTTPS uploads
            if upload_url.startswith(('http://', 'https://')):
                with open(file_path, 'rb') as f:
                    async with self.session.put(upload_url, data=f, headers=headers) as response:
                        return response.status == 200
            else:
                logger.warning(f"Unsupported upload protocol: {upload_url}")
                return False
                
        except Exception as e:
            logger.error(f"Aria2c upload error: {e}")
            return False
    
    async def get_download_status(self, gid: str) -> Dict[str, Any]:
        """Get detailed status of a download"""
        if not self.initialized:
            return {}
            
        try:
            download = self.api.get_download(gid)
            return {
                "status": download.status,
                "completed_length": download.completed_length,
                "total_length": download.total_length,
                "download_speed": download.download_speed,
                "upload_speed": download.upload_speed,
                "progress": download.progress,
                "connections": download.connections,
                "error_message": download.error_message
            }
        except:
            return {}
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        self.initialized = False

# Global instance
aria2_manager = Aria2Manager()
