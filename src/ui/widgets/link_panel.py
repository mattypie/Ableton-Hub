"""Ableton Link network monitoring panel."""

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...database import LinkDevice, get_session
from ..theme import AbletonTheme


class DeviceCard(QFrame):
    """Card displaying a Link device."""

    def __init__(self, device: LinkDevice, parent: QWidget | None = None):
        super().__init__(parent)

        self.device = device
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the card UI."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedSize(200, 120)

        # Style based on status
        if self.device.is_active:
            border_color = AbletonTheme.COLORS["success"]
            status_text = "Online"
            status_color = AbletonTheme.COLORS["success"]
        else:
            border_color = AbletonTheme.COLORS["border"]
            status_text = "Offline"
            status_color = AbletonTheme.COLORS["text_disabled"]

        self.setStyleSheet(f"""
            DeviceCard {{
                background-color: {AbletonTheme.COLORS['surface']};
                border: 2px solid {border_color};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Device name
        name_label = QLabel(self.device.device_name)
        font = name_label.font()
        font.setBold(True)
        if font.pointSize() > 0:
            font.setPointSize(12)
        else:
            font.setPixelSize(16)
        name_label.setFont(font)
        layout.addWidget(name_label)

        # Device type
        if self.device.device_type:
            type_label = QLabel(self.device.device_type)
            type_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
            layout.addWidget(type_label)

        layout.addStretch()

        # Status row
        status_row = QHBoxLayout()

        status_indicator = QLabel("●")
        status_indicator.setStyleSheet(f"color: {status_color};")
        status_row.addWidget(status_indicator)

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color};")
        status_row.addWidget(status_label)

        status_row.addStretch()

        layout.addLayout(status_row)

        # IP and last seen
        ip_label = QLabel(f"IP: {self.device.ip_address}")
        ip_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']}; font-size: 10px;")
        layout.addWidget(ip_label)

        if self.device.last_seen:
            delta = datetime.utcnow() - self.device.last_seen
            if delta.total_seconds() < 60:
                seen_text = "Just now"
            elif delta.total_seconds() < 3600:
                seen_text = f"{int(delta.total_seconds() // 60)}m ago"
            else:
                seen_text = self.device.last_seen.strftime("%H:%M")

            seen_label = QLabel(f"Seen: {seen_text}")
            seen_label.setStyleSheet(
                f"color: {AbletonTheme.COLORS['text_secondary']}; font-size: 10px;"
            )
            layout.addWidget(seen_label)


class LinkPanel(QWidget):
    """Panel for monitoring Ableton Link network."""

    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._devices: list[LinkDevice] = []
        self._scanner = None
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_devices)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()

        title = QLabel("Link Network")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet(f"color: {AbletonTheme.COLORS['text_disabled']};")
        header.addWidget(self.status_indicator)

        self.status_label = QLabel("Not scanning")
        self.status_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
        header.addWidget(self.status_label)

        # Control buttons
        self.scan_btn = QPushButton("Start Scanning")
        self.scan_btn.clicked.connect(self._toggle_scanning)
        header.addWidget(self.scan_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_devices)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Network info
        info_group = QGroupBox("Network Information")
        info_layout = QVBoxLayout(info_group)

        self.wifi_label = QLabel("WiFi: Detecting...")
        info_layout.addWidget(self.wifi_label)

        self.devices_count_label = QLabel("Devices: 0 online")
        info_layout.addWidget(self.devices_count_label)

        layout.addWidget(info_group)

        # Devices grid
        devices_label = QLabel("Connected Devices")
        devices_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(devices_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.devices_container = QWidget()
        self.devices_layout = QGridLayout(self.devices_container)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setSpacing(16)
        self.devices_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.devices_container)
        layout.addWidget(scroll)

        # Tips section
        tips_group = QGroupBox("Link Tips")
        tips_layout = QVBoxLayout(tips_group)

        tips = [
            "• All devices must be on the same WiFi network",
            "• Ensure your firewall allows Link traffic (UDP port 20808)",
            "• For best results, use a 5GHz WiFi network",
            "• Wired connections provide the lowest latency",
        ]

        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
            tips_layout.addWidget(tip_label)

        layout.addWidget(tips_group)

        # Initial load
        self._refresh_devices()
        self._detect_wifi()

    def _toggle_scanning(self) -> None:
        """Toggle Link network scanning."""
        if self._scanner is None:
            self._start_scanning()
        else:
            self._stop_scanning()

    def _start_scanning(self) -> None:
        """Start Link network scanning."""
        from ...services.link_scanner import LinkScanner

        self._scanner = LinkScanner()
        self._scanner.device_found.connect(self._on_device_found)
        self._scanner.device_lost.connect(self._on_device_lost)
        self._scanner.start()

        self.scan_btn.setText("Stop Scanning")
        self.status_indicator.setStyleSheet(f"color: {AbletonTheme.COLORS['success']};")
        self.status_label.setText("Scanning...")

        # Start refresh timer
        self._refresh_timer.start(5000)  # Refresh every 5 seconds

    def _stop_scanning(self) -> None:
        """Stop Link network scanning."""
        self._refresh_timer.stop()

        if self._scanner:
            self._scanner.stop()
            self._scanner = None

        self._refresh_timer.stop()

        self.scan_btn.setText("Start Scanning")
        self.status_indicator.setStyleSheet(f"color: {AbletonTheme.COLORS['text_disabled']};")
        self.status_label.setText("Not scanning")

    def _on_device_found(self, device_name: str, ip_address: str, port: int) -> None:
        """Handle a device being found."""
        session = get_session()
        try:
            # Check if device exists
            device = (
                session.query(LinkDevice)
                .filter(LinkDevice.device_name == device_name, LinkDevice.ip_address == ip_address)
                .first()
            )

            if device:
                device.is_active = True
                device.last_seen = datetime.utcnow()
                device.session_count += 1
            else:
                device = LinkDevice(
                    device_name=device_name, ip_address=ip_address, port=port, is_active=True
                )
                session.add(device)

            session.commit()
            self._refresh_devices()
        finally:
            session.close()

    def _on_device_lost(self, device_name: str, ip_address: str) -> None:
        """Handle a device going offline."""
        session = get_session()
        try:
            device = (
                session.query(LinkDevice)
                .filter(LinkDevice.device_name == device_name, LinkDevice.ip_address == ip_address)
                .first()
            )

            if device:
                device.is_active = False
                session.commit()
                self._refresh_devices()
        finally:
            session.close()

    def _refresh_devices(self) -> None:
        """Refresh the devices display."""
        session = get_session()
        try:
            self._devices = (
                session.query(LinkDevice)
                .order_by(LinkDevice.is_active.desc(), LinkDevice.last_seen.desc())
                .all()
            )

            self._populate_devices()

            # Update count
            online = sum(1 for d in self._devices if d.is_active)
            self.devices_count_label.setText(
                f"Devices: {online} online, {len(self._devices)} total"
            )
        finally:
            session.close()

    def _populate_devices(self) -> None:
        """Populate the devices grid."""
        # Clear existing
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._devices:
            empty_label = QLabel("No devices found. Start scanning to discover Link devices.")
            empty_label.setStyleSheet(f"color: {AbletonTheme.COLORS['text_secondary']};")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.devices_layout.addWidget(empty_label, 0, 0)
            return

        columns = 3
        for idx, device in enumerate(self._devices):
            card = DeviceCard(device)
            row = idx // columns
            col = idx % columns
            self.devices_layout.addWidget(card, row, col)

    def _detect_wifi(self) -> None:
        """Detect the current WiFi network."""
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":")[1].strip()
                        self.wifi_label.setText(f"WiFi: {ssid}")
                        return
            elif sys.platform == "darwin":
                result = subprocess.run(
                    [
                        "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                        "-I",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "SSID:" in line:
                        ssid = line.split(":")[1].strip()
                        self.wifi_label.setText(f"WiFi: {ssid}")
                        return

            self.wifi_label.setText("WiFi: Unknown")
        except Exception:
            self.wifi_label.setText("WiFi: Could not detect")

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        self._refresh_devices()

    def cleanup(self) -> None:
        """Clean up resources."""
        self._refresh_timer.stop()
        self._stop_scanning()
        # Give thread time to stop
        import time

        time.sleep(0.1)

    def hideEvent(self, event) -> None:
        """Handle hide event."""
        super().hideEvent(event)
        # Optionally stop scanning when hidden
