# 📡 Hotspot Config for Arch

A Python-based GUI application that provides **Windows-like hotspot control** on Arch Linux — built as a high-level orchestrator over NetworkManager using PyQt6.

> One-click hotspot management with Waybar integration, Hyprland window rules, and smart safety features.

---

## ✨ Features

- 🖱️ **One-click Hotspot Toggle** — Start/stop like Windows Mobile Hotspot
- 🎨 **Premium Dark UI** — Custom-themed PyQt6 interface with deep navy/charcoal palette
- 📡 **Real-time Client Monitoring** — Live connected device list via ARP table polling
- 🛡️ **Wi-Fi Conflict Warning** — Warns before disconnecting an active Wi-Fi session
- 🔌 **External Termination Detection** — Auto-detects when hotspot is killed by external tools
- 🌐 **Routing Protection** — Prevents hotspot from displacing your wired internet gateway
- 🧩 **Waybar Integration** — Status bar module with left-click toggle & right-click GUI
- 🪟 **Hyprland Optimized** — Floating window rules with transparency support
- ⌨️ **CLI + GUI Hybrid** — Full command-line interface alongside the graphical app

---

## 📸 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Entry Points                          │
│   hotspot (bash) → python -m src [command]               │
│   Waybar module / Hyprland keybind / terminal            │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│               src/main.py  (Orchestrator)                │
│  • argparse command dispatch                             │
│  • CLI: start / stop / status / toggle / waybar          │
│  • GUI launcher with single-instance IPC (Unix socket)   │
└──────┬──────────────────────────┬────────────────────────┘
       │                          │
       ▼                          ▼
┌────────────────────┐  ┌─────────────────────────────────┐
│  src/core/         │  │  src/gui/main_window.py         │
│  nm_dbus.py        │  │  • PyQt6 GUI                    │
│  • nmcli + D-Bus   │  │  • Themed warning dialogs       │
│  • Wi-Fi detection │  │  • Background QThread workers   │
│  • Route protection│  │  • 5-second polling timer       │
│  stats.py          │  │  • Hide-on-close behavior       │
│  • ARP client list │  └─────────────────────────────────┘
└────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│           NetworkManager → Wi-Fi Hardware                │
└──────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Hotspot_GUI/
├── hotspot                     # Bash launcher (Waybar / keybind entry)
├── requirements.txt            # Python dependencies
├── README.md                   # ← This file
├── docs/
│   ├── README.md               # Integration guide (Waybar, Hyprland)
│   └── PROJECT_SUMMARY.md      # Detailed technical documentation
└── src/
    ├── __init__.py
    ├── __main__.py             # Enables `python -m src` entry
    ├── main.py                 # CLI orchestrator + GUI launcher
    ├── constants.py            # Shared paths / identifiers
    ├── core/
    │   ├── nm_dbus.py          # NetworkManager controller (nmcli + D-Bus)
    │   └── stats.py            # Connected client discovery via /proc/net/arp
    └── gui/
        └── main_window.py      # PyQt6 main window + worker threads
```

---

## ⚙️ Requirements

| Dependency | Purpose |
|---|---|
| Arch Linux | Target OS |
| Python 3.10+ | Runtime |
| PyQt6 ≥ 6.6.0 | GUI framework |
| sdbus + sdbus-networkmanager | D-Bus bindings |
| NetworkManager | System network daemon |
| Waybar | *Optional* — status bar integration |
| Hyprland | *Optional* — window rules |

---

## 🚀 Installation

### Arch User Repository (AUR)

If you are on Arch Linux, the easiest way to install is via the AUR package `hotspot-gui-git`. Use an AUR helper like `yay` or `paru`:

```bash
yay -S hotspot-gui-git
```

This will automatically install all dependencies, the desktop entry, system package, and the CLI tool.

### Manual Installation (Development)

```bash
# Clone the repo
git clone https://github.com/Prasanth-636939/hotspot_config_for_arch.git
cd hotspot_config_for_arch

# Set up virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 💻 Usage

### GUI

```bash
# Launch from the terminal
hotspot-gui gui

# Or use the symlink
hotspot gui
```

### CLI

```bash
hotspot toggle                              # Toggle hotspot on/off
hotspot start --ssid MyNet --password s3cr3t # Start with custom credentials
hotspot status                              # Show status + connected clients
hotspot stop                                # Stop and cleanup
hotspot waybar                              # Output Waybar JSON status
```

---

## 🧩 Waybar Integration

Add to your Waybar `config.jsonc`:

```jsonc
"custom/hotspot-gui": {
    "format": "{}",
    "return-type": "json",
    "exec": "hotspot waybar",
    "interval": 3,
    "on-click": "hotspot toggle",
    "on-click-right": "hotspot gui",
    "tooltip": true
}
```

**Controls:**
- **Left Click** → Toggle hotspot ON/OFF
- **Right Click** → Open GUI
- **Auto Refresh** → Updates every 3 seconds

**Styling** (`style.css`):

```css
#custom-hotspot-gui.active {
    color: #a6e3a1; /* Green when active */
}
#custom-hotspot-gui.inactive {
    color: #6c7086; /* Gray when inactive */
}
```

---

## 🪟 Hyprland Integration

Add to your `hyprland.conf`:

```ini
windowrule = match:class ^HotspotGUI$, float on
windowrule = match:class ^HotspotGUI$, center on
windowrule = match:class ^HotspotGUI$, size 420 500
windowrule = opacity 0.6, match:class ^HotspotGUI$
```

---

## 🛡️ Safety Features

### Wi-Fi Conflict Warning
Starting the hotspot disconnects any active Wi-Fi session (both share the same adapter). The GUI shows a themed warning dialog letting you cancel before disconnecting.

### External Termination Detection
If the hotspot is killed externally (e.g., you connect to Wi-Fi via `nmcli`), the app automatically detects it within 5 seconds and updates the UI.

### Routing Protection
Prevents the hotspot from displacing your wired internet gateway by setting `ipv4.never-default yes` and a high route metric (`1000`).

---

## 📋 Changelog

### v1.6 — Updated UI *(Current)*
- Premium dark theme with deep navy/charcoal palette
- Themed warning dialogs matching application stylesheet
- Visual consistency across all UI components

### v1.5 — Rewrote nm_dbus.py
- Rewrote `nm_dbus.py` for Wi-Fi warning and hotspot disconnection detection
- Added `get_wifi_client_ssid()` — detects active Wi-Fi client connections
- Added `is_hotspot_active()` — polls for external hotspot termination
- Routing protection (never-default + high route metric)

### v1.4 — Bug Fixes
- Updated code to fix bugs
- Improved stability and error handling

---

## 🤝 Contributing

Pull requests and ideas are welcome. Feel free to fork and enhance the project.

---

## 📄 License

GPL-3.0-or-later

---

## ⭐ Support

If you find this project useful, consider giving it a star!
