"""Ableton Link network discovery service using zeroconf."""

from typing import Optional, Dict, List
from datetime import datetime

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceStateChange
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False


# Ableton Link uses this mDNS service type
LINK_SERVICE_TYPE = "_abl-link._udp.local."


class LinkServiceListener:
    """Listener for Ableton Link mDNS service announcements."""
    
    def __init__(self, callback):
        """Initialize the listener.
        
        Args:
            callback: Function to call with (event_type, name, ip, port).
        """
        self.callback = callback
    
    def add_service(self, zc: 'Zeroconf', service_type: str, name: str) -> None:
        """Handle service added."""
        info = zc.get_service_info(service_type, name)
        if info:
            # Get IP addresses
            addresses = info.parsed_addresses()
            ip = addresses[0] if addresses else "unknown"
            port = info.port
            
            # Extract device name from service name
            device_name = name.replace(f".{service_type}", "").replace("._abl-link._udp.local.", "")
            if not device_name:
                device_name = f"Link Device ({ip})"
            
            self.callback("found", device_name, ip, port)
    
    def remove_service(self, zc: 'Zeroconf', service_type: str, name: str) -> None:
        """Handle service removed."""
        device_name = name.replace(f".{service_type}", "").replace("._abl-link._udp.local.", "")
        self.callback("lost", device_name, "", 0)
    
    def update_service(self, zc: 'Zeroconf', service_type: str, name: str) -> None:
        """Handle service update."""
        # Re-process as add to get updated info
        self.add_service(zc, service_type, name)


class LinkScanWorker(QThread):
    """Background worker for Link network scanning."""
    
    device_found = pyqtSignal(str, str, int)  # name, ip, port
    device_lost = pyqtSignal(str, str)        # name, ip
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        self._stop_requested = False
        self._zeroconf: Optional['Zeroconf'] = None
        self._browser: Optional['ServiceBrowser'] = None
    
    def run(self) -> None:
        """Run the Link scanner."""
        if not ZEROCONF_AVAILABLE:
            self.error.emit("zeroconf library not available")
            return
        
        try:
            self._zeroconf = Zeroconf()
            listener = LinkServiceListener(self._on_service_event)
            self._browser = ServiceBrowser(
                self._zeroconf,
                LINK_SERVICE_TYPE,
                listener
            )
            
            # Keep running until stop requested
            while not self._stop_requested:
                self.msleep(100)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Clean up zeroconf resources
            try:
                if self._browser:
                    self._browser.cancel()
                    self._browser = None
            except Exception:
                pass
            
            try:
                if self._zeroconf:
                    self._zeroconf.close()
                    self._zeroconf = None
            except Exception:
                pass
    
    def _on_service_event(self, event: str, name: str, ip: str, port: int) -> None:
        """Handle service event from listener."""
        if event == "found":
            self.device_found.emit(name, ip, port)
        elif event == "lost":
            self.device_lost.emit(name, ip)
    
    def stop(self) -> None:
        """Request stop."""
        self._stop_requested = True


class LinkScanner(QObject):
    """Service for discovering Ableton Link devices on the network."""
    
    # Signals
    device_found = pyqtSignal(str, str, int)  # name, ip, port
    device_lost = pyqtSignal(str, str)        # name, ip
    scan_started = pyqtSignal()
    scan_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._worker: Optional[LinkScanWorker] = None
        self._devices: Dict[str, dict] = {}  # ip -> device info
        
        # Periodic cleanup timer
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_stale_devices)
    
    @property
    def is_available(self) -> bool:
        """Check if Link scanning is available."""
        return ZEROCONF_AVAILABLE
    
    @property
    def is_running(self) -> bool:
        """Check if scanner is running."""
        return self._worker is not None and self._worker.isRunning()
    
    def start(self) -> None:
        """Start scanning for Link devices."""
        if not self.is_available:
            self.error_occurred.emit("Link scanning not available - install python-zeroconf")
            return
        
        if self.is_running:
            return
        
        self._worker = LinkScanWorker()
        self._worker.device_found.connect(self._on_device_found)
        self._worker.device_lost.connect(self._on_device_lost)
        self._worker.error.connect(self.error_occurred.emit)
        self._worker.start()
        
        # Start cleanup timer (every 30 seconds)
        self._cleanup_timer.start(30000)
        
        self.scan_started.emit()
    
    def stop(self) -> None:
        """Stop scanning."""
        self._cleanup_timer.stop()
        
        if not self._worker:
            self.scan_stopped.emit()
            return
        
        worker = self._worker
        self._worker = None
        
        # Request stop
        worker.stop()
        
        # Disconnect all signals to prevent crashes
        try:
            worker.device_found.disconnect()
            worker.device_lost.disconnect()
            worker.error.disconnect()
        except (TypeError, RuntimeError):
            pass  # Signals may already be disconnected
        
        # Wait for thread to finish
        if worker.isRunning():
            worker.quit()  # Request graceful shutdown
            if not worker.wait(5000):  # Wait up to 5 seconds
                # If still running, try to terminate
                worker.terminate()
                worker.wait(2000)  # Wait a bit more
        
        # Schedule worker for deletion
        worker.deleteLater()
        
        self.scan_stopped.emit()
    
    def _on_device_found(self, name: str, ip: str, port: int) -> None:
        """Handle device found."""
        self._devices[ip] = {
            'name': name,
            'ip': ip,
            'port': port,
            'last_seen': datetime.utcnow(),
            'active': True
        }
        
        self.device_found.emit(name, ip, port)
    
    def _on_device_lost(self, name: str, ip: str) -> None:
        """Handle device lost."""
        if ip in self._devices:
            self._devices[ip]['active'] = False
        
        self.device_lost.emit(name, ip)
    
    def _cleanup_stale_devices(self) -> None:
        """Remove devices not seen recently."""
        now = datetime.utcnow()
        stale_ips = []
        
        for ip, info in self._devices.items():
            if info['active']:
                delta = now - info['last_seen']
                if delta.total_seconds() > 60:  # 1 minute timeout
                    stale_ips.append(ip)
        
        for ip in stale_ips:
            info = self._devices[ip]
            info['active'] = False
            self.device_lost.emit(info['name'], ip)
    
    def get_active_devices(self) -> List[dict]:
        """Get list of currently active devices.
        
        Returns:
            List of device info dictionaries.
        """
        return [d for d in self._devices.values() if d['active']]
    
    def get_all_devices(self) -> List[dict]:
        """Get list of all discovered devices.
        
        Returns:
            List of device info dictionaries.
        """
        return list(self._devices.values())
    
    def get_device_count(self) -> int:
        """Get count of active devices.
        
        Returns:
            Number of active devices.
        """
        return sum(1 for d in self._devices.values() if d['active'])


def get_wifi_name() -> Optional[str]:
    """Get the current WiFi network name.
    
    Returns:
        SSID of connected network, or None.
    """
    import subprocess
    import sys
    
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":")[1].strip()
                    
        elif sys.platform == "darwin":
            result = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "SSID:" in line:
                    return line.split(":")[1].strip()
                    
        else:
            # Linux
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if line.startswith("yes:"):
                    return line.split(":")[1]
                    
    except Exception:
        pass
    
    return None


def get_link_tips() -> List[str]:
    """Get helpful tips for Ableton Link setup.
    
    Returns:
        List of tip strings.
    """
    return [
        "All devices must be connected to the same WiFi network",
        "For best results, use a 5GHz WiFi network",
        "Avoid networks with client isolation enabled",
        "Wired Ethernet connections provide the lowest latency",
        "Ensure your firewall allows UDP traffic on port 20808",
        "Close other network-intensive applications for better sync",
        "Keep devices physically close for better WiFi performance",
    ]
