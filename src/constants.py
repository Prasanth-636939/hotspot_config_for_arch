"""
Shared constants for Hotspot GUI.
Single source of truth for paths and identifiers used across all modules.
"""

import os

# Runtime state file – bridges state between CLI and GUI sessions
STATE_FILE = "/tmp/hotspot_gui_state.json"

# Unix socket path for single-instance IPC (GUI window toggle)
SOCKET_PATH = "/tmp/hotspot_gui.sock"

# Persistent user configuration file (SSID / password)
CONFIG_FILE = os.path.expanduser("~/.config/hotspot_gui.json")
