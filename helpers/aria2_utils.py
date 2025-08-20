import os
import subprocess
import socket
import time
import logging
import aria2p

logger = logging.getLogger(__name__)


class Aria2Helper:
    def __init__(self, host="http://localhost", port=6800, secret=""):
        self.host = host
        self.port = port
        self.secret = secret
        self.aria2 = None
        self.api = None
        self.process = None

    def is_port_in_use(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def start_aria2c(self):
        """Start aria2c manually if not already running"""
        if self.is_port_in_use(self.port):
            logger.info("ℹ️ Aria2c already running on port %s", self.port)
            return True

        cmd = [
            "aria2c",
            f"--enable-rpc",
            f"--rpc-listen-port={self.port}",
            f"--rpc-allow-origin-all",
            f"--rpc-listen-all=false",
        ]
        if self.secret:
            cmd.append(f"--rpc-secret={self.secret}")

        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.warning("⚡ Starting aria2c manually...")
            time.sleep(3)  # give aria2c time to boot
            if not self.is_port_in_use(self.port):
                logger.error("❌ Failed to start aria2c on port %s", self.port)
                return False
            logger.info("✅ Aria2c started manually")
            return True
        except Exception as e:
            logger.error("❌ Error starting aria2c: %s", str(e))
            return False

    def initialize(self):
        """Initialize aria2c connection"""
        try:
            if not self.is_port_in_use(self.port):
                if not self.start_aria2c():
                    logger.error("❌ Aria2c is not running and could not be started")
                    return False

            self.aria2 = aria2p.Client(
                host=f"{self.host}:{self.port}/jsonrpc",
                secret=self.secret
            )
            self.api = aria2p.API(self.aria2)

            version_info = self.api.client.get_version()
            logger.info(f"✅ Successfully connected to aria2c v{version_info['version']}")
            return True
        except Exception as e:
            logger.error("Failed to initialize aria2c: %s", str(e))
            return False

    def add_download(self, url, options=None):
        """Add new download to aria2"""
        if not self.api:
            logger.error("❌ Aria2 API not initialized")
            return None
        try:
            return self.api.add_uris([url], options=options or {})
        except Exception as e:
            logger.error("❌ Failed to add download: %s", str(e))
            return None

    def get_download_status(self):
        """Return global download stats"""
        if not self.api:
            logger.error("❌ Aria2 API not initialized")
            return None
        try:
            stats = self.api.get_global_stats()
            downloads = self.api.get_downloads()

            return {
                "download_speed": stats["downloadSpeed"],
                "upload_speed": stats["uploadSpeed"],
                "num_active": stats["numActive"],
                "num_waiting": stats["numWaiting"],
                "num_stopped": stats["numStopped"],
                "total_downloads": len(downloads)
            }
        except Exception as e:
            logger.error("❌ Failed to fetch stats: %s", str(e))
            return None

    def shutdown(self):
        """Stop aria2c"""
        try:
            if self.api:
                self.api.shutdown()
            if self.process:
                self.process.terminate()
                logger.info("🛑 Aria2c terminated")
        except Exception as e:
            logger.error("❌ Error shutting down aria2c: %s", str(e))
