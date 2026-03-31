import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFormLayout,
    QListWidget, QGroupBox, QMessageBox,
)

from PyQt6.QtCore import QTimer, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent

from ..constants import STATE_FILE, CONFIG_FILE
from ..core.stats import NetworkStats


# ---------------------------------------------------------------------------
# Background worker threads
# ---------------------------------------------------------------------------

class HotspotStartThread(QThread):
    """Runs start_hotspot() off the main thread."""
    # success, error_msg, con_name, iface, profile_path, active_conn_path
    finished = pyqtSignal(bool, str, str, str, str, str)

    def __init__(self, dbus_ctrl, ssid: str, password: str):
        super().__init__()
        self.dbus_ctrl = dbus_ctrl
        self.ssid = ssid
        self.password = password

    def run(self):
        try:
            con_name, iface, profile_path, active_conn_path = self.dbus_ctrl.start_hotspot(
                self.ssid, self.password
            )
            self.finished.emit(True, "", con_name, iface, profile_path, active_conn_path)
        except Exception as e:
            self.finished.emit(False, str(e), "", "", "", "")


class HotspotStopThread(QThread):
    """Runs stop_hotspot() off the main thread."""
    finished = pyqtSignal(bool, str)

    def __init__(self, dbus_ctrl, con_name: str):
        super().__init__()
        self.dbus_ctrl = dbus_ctrl
        self.con_name = con_name

    def run(self):
        try:
            self.dbus_ctrl.stop_hotspot(self.con_name)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class OrchestratorMainWindow(QMainWindow):
    def __init__(self, dbus_ctrl):
        super().__init__()
        self.dbus_ctrl = dbus_ctrl
        self.stats = NetworkStats(dbus_ctrl)
        self.setWindowTitle("Arch Linux Hotspot & Wi-Fi Orchestrator")

        # ---- Global theme stylesheet ----------------------------------------
        APP_STYLE = """
            QMainWindow { background-color: #0b0b0f; }
            QWidget {
                color: #c0c4d4;
                font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
                font-size: 13px;
                background-color: #0b0b0f;
            }
            QGroupBox {
                border: 1px solid #1e202a;
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #101116;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #7994c6;
                font-weight: 600;
            }
            QLineEdit {
                background-color: #15161e;
                border: 1px solid #282a36;
                border-radius: 4px;
                padding: 6px;
                color: #e2e4ed;
            }
            QLineEdit:focus { border: 1px solid #7994c6; background-color: #1a1c23; }
            QPushButton {
                background-color: #1e202a;
                color: #7994c6;
                border: 1px solid #282a36;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #282a36; color: #92aadb; border: 1px solid #3b3f52; }
            QPushButton:pressed { background-color: #15161e; color: #617cac; }
            QPushButton:disabled { background-color: #101116; color: #3b3f52; border: 1px solid #1e202a; }
            QLabel { color: #a4a8b6; background-color: transparent; }
            QListWidget {
                background-color: #101116;
                border: 1px solid #1e202a;
                border-radius: 4px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #15161e; border-radius: 3px; }
            QListWidget::item:selected { background-color: #1e202a; color: #92aadb; }
            /* ---- QMessageBox theming ---------------------------------------- */
            QMessageBox {
                background-color: #101116;
                color: #c0c4d4;
            }
            QMessageBox QLabel {
                color: #c0c4d4;
                background-color: transparent;
                font-size: 13px;
                min-width: 340px;
            }
            QMessageBox QPushButton {
                background-color: #1e202a;
                color: #7994c6;
                border: 1px solid #282a36;
                border-radius: 4px;
                padding: 6px 20px;
                font-weight: 500;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover { background-color: #282a36; color: #92aadb; border: 1px solid #3b3f52; }
            QMessageBox QPushButton:pressed { background-color: #15161e; color: #617cac; }
            QMessageBox QDialogButtonBox QPushButton[default="true"] {
                background-color: #7994c6;
                color: #0b0b0f;
                border: 1px solid #92aadb;
                font-weight: 700;
            }
            QMessageBox QDialogButtonBox QPushButton[default="true"]:hover {
                background-color: #92aadb;
            }
        """
        self.setStyleSheet(APP_STYLE)

        main_layout = QVBoxLayout()
        saved_ssid, saved_password = self._load_config()

        # -- Configuration ---------------------------------------------------
        config_group = QGroupBox("Hotspot Configuration")
        form_layout = QFormLayout()
        self.ssid_input = QLineEdit(saved_ssid)
        self.pass_input = QLineEdit(saved_password)
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("SSID:", self.ssid_input)
        form_layout.addRow("Password:", self.pass_input)
        config_group.setLayout(form_layout)

        # -- Controls --------------------------------------------------------
        control_layout = QHBoxLayout()
        self.status_label = QLabel("Hotspot Status: Inactive")
        self.start_btn = QPushButton("Start Hotspot")
        self.stop_btn  = QPushButton("Stop Hotspot")
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)

        # -- Connected clients -----------------------------------------------
        clients_group = QGroupBox("Connected Clients")
        clients_layout = QVBoxLayout()
        self.clients_list = QListWidget()
        clients_layout.addWidget(self.clients_list)
        clients_group.setLayout(clients_layout)

        # -- Assemble --------------------------------------------------------
        main_layout.addWidget(config_group)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(clients_group)

        self.start_btn.clicked.connect(self.start_hotspot)
        self.stop_btn.clicked.connect(self.stop_hotspot)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Runtime state
        self._con_name:        str       = ""
        self._iface:           str       = ""
        self.active_conn_path: str       = ""
        self.profile_path:     str       = ""
        self._current_ssid:    str | None = None

        self._sync_state()

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_stats)
        self.timer.start(5000)

    # -----------------------------------------------------------------------
    # IPC slot
    # -----------------------------------------------------------------------

    @pyqtSlot()
    def toggle_visibility(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        """Wait for in-progress threads, then hide rather than destroy."""
        for attr in ("start_thread", "stop_thread"):
            thread: QThread | None = getattr(self, attr, None)
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(5000)
        event.ignore()
        self.hide()

    # -----------------------------------------------------------------------
    # Config persistence
    # -----------------------------------------------------------------------

    def _load_config(self) -> tuple[str, str]:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                    return cfg.get("ssid", "Arch_Hotspot_123"), cfg.get("password", "12345678")
            except (json.JSONDecodeError, OSError):
                pass
        return "Arch_Hotspot_123", "12345678"

    def _save_config(self, ssid: str, password: str):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump({"ssid": ssid, "password": password}, f, indent=2)
        except OSError:
            pass

    # -----------------------------------------------------------------------
    # State file helpers
    # -----------------------------------------------------------------------

    def _is_active(self, state: dict) -> bool:
        return bool(state.get("con_name") or state.get("active_conn_path"))

    def _sync_state(self):
        """Read STATE_FILE and sync UI."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                if self._is_active(state):
                    self._con_name        = state.get("con_name", "")
                    self._iface           = state.get("iface", "")
                    self.active_conn_path = state.get("active_conn_path", "")
                    self.profile_path     = state.get("profile_path", "")
                    self._current_ssid    = state.get("ssid")
                    iface_info = f" on {self._iface}" if self._iface else ""
                    self.status_label.setText(
                        f"Status: Active  (SSID: {self._current_ssid}{iface_info})"
                    )
                    self.start_btn.setEnabled(False)
                    self.stop_btn.setEnabled(True)
                    self.ssid_input.setEnabled(False)
                    self.pass_input.setEnabled(False)
                    return
            except (json.JSONDecodeError, OSError):
                pass

        self._con_name        = ""
        self._iface           = ""
        self.active_conn_path = ""
        self.profile_path     = ""
        self._current_ssid    = None
        self.status_label.setText("Status: Inactive")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.ssid_input.setEnabled(True)
        self.pass_input.setEnabled(True)

    def _persist_state(self, ssid: str, con_name: str, iface: str):
        state = {
            "con_name":         con_name,
            "iface":            iface,
            "active_conn_path": self.active_conn_path,
            "profile_path":     self.profile_path,
            "ssid":             ssid,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

    # -----------------------------------------------------------------------
    # Hotspot controls
    # -----------------------------------------------------------------------

    def start_hotspot(self):
        ssid     = self.ssid_input.text().strip()
        password = self.pass_input.text()
        if not ssid:
            self.status_label.setText("Status: SSID cannot be empty.")
            return

        # ---- Feature 1: warn if Wi-Fi is already connected in client mode ----
        # Both client mode and hotspot mode share the physical Wi-Fi adapter,
        # so starting the hotspot will forcibly disconnect any active Wi-Fi
        # client session.  Give the user a chance to cancel.
        wifi_ssid = self.dbus_ctrl.get_wifi_client_ssid()
        if wifi_ssid:
            reply = self._themed_warning(
                "Wi-Fi Is Currently In Use",
                f"<b>Wi-Fi is connected to:</b><br><br>"
                f"&nbsp;&nbsp;&nbsp;<i>{wifi_ssid}</i><br><br>"
                "Starting the hotspot will <b>disconnect Wi-Fi</b> because "
                "both share the same wireless adapter.<br><br>"
                "Do you want to continue?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        # ----------------------------------------------------------------------

        self.status_label.setText("Status: Starting…")
        self.start_btn.setEnabled(False)
        self._save_config(ssid, password)

        self.start_thread = HotspotStartThread(self.dbus_ctrl, ssid, password)
        self.start_thread.finished.connect(self._on_start_finished)
        self.start_thread.start()


    def _on_start_finished(
        self, success: bool, error_message: str,
        con_name: str, iface: str, profile_path: str, active_conn_path: str
    ):
        if not success:
            self.status_label.setText(f"Status: Error – {error_message}")
            self.start_btn.setEnabled(True)
            return

        self._con_name        = con_name
        self._iface           = iface
        self.profile_path     = profile_path
        self.active_conn_path = active_conn_path
        self._current_ssid    = self.ssid_input.text().strip()

        self._persist_state(self._current_ssid, con_name, iface)
        self._sync_state()
        self._update_stats()

    # -----------------------------------------------------------------------
    # Themed dialog helper
    # -----------------------------------------------------------------------

    def _themed_warning(self, title: str, text: str) -> QMessageBox.StandardButton:
        """Show a Yes/No warning dialog that matches the application's dark theme."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setTextFormat(0x1)  # Qt.TextFormat.RichText (integer 1)
        msg.setText(text)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        # Explicitly propagate the dark stylesheet so the dialog isn't
        # painted by the system/platform theme.
        msg.setStyleSheet(self.styleSheet())
        return msg.exec()

    def stop_hotspot(self):
        self.status_label.setText("Status: Stopping…")
        self.stop_btn.setEnabled(False)
        self.clients_list.clear()

        con_name = self._con_name or (self._current_ssid or "") + " Hotspot"
        self.stop_thread = HotspotStopThread(self.dbus_ctrl, con_name)
        self.stop_thread.finished.connect(self._on_stop_finished)
        self.stop_thread.start()

    def _on_stop_finished(self, success: bool, error_message: str):
        if not success:
            self.status_label.setText(f"Status: Error – {error_message}")
            self.stop_btn.setEnabled(True)
            return

        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        self._sync_state()

    # -----------------------------------------------------------------------
    # Stats polling
    # -----------------------------------------------------------------------

    def _update_stats(self):
        self._sync_state()

        if not (self._con_name or self.active_conn_path):
            self.clients_list.clear()
            return

        # ---- Feature 2: detect external hotspot termination ------------------
        # If the user connects to a Wi-Fi network via any external tool (NM
        # applet, nmcli, etc.), NM drops the hotspot AP connection to reclaim
        # the adapter.  The state file still says "active", but NM no longer
        # lists the connection as active.  Detect this mismatch and auto-clean.
        if self._con_name and not self.dbus_ctrl.is_hotspot_active(self._con_name):
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            self._sync_state()          # resets UI to Inactive
            self.clients_list.clear()
            self.status_label.setText("Status: Inactive  (stopped — Wi-Fi connected externally)")
            return
        # ----------------------------------------------------------------------

        clients = self.stats.get_active_clients(self._iface or None)
        self.clients_list.clear()
        if not clients:
            self.clients_list.addItem("No clients connected.")
        else:
            for c in clients:
                self.clients_list.addItem(
                    f"IP: {c['ip']}  |  MAC: {c['mac']}  |  Interface: {c['device']}"
                )

