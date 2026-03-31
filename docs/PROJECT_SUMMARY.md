# 📡 Hotspot GUI — Complete Project Summary

> A Python-based Arch Linux Wi-Fi hotspot orchestrator with a full GUI, CLI, Waybar integration, and Hyprland window rules.

---

## 🧭 What Is This Project?

**Hotspot GUI** is a lightweight, Wayland-native hotspot manager for Arch Linux. It lets you create and destroy a Wi-Fi hotspot directly from a GUI or the command line — similar to the "Mobile Hotspot" feature in Windows — without needing to memorize any `nmcli` or `hostapd` commands.

It wraps **NetworkManager** under the hood using both `nmcli` subprocess calls (for reliable hotspot activation, modification, and teardown) and `sdbus` D-Bus bindings (for device enumeration and connection path discovery). The entire application is written in Python and uses **PyQt6** for the graphical interface.

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Entry Points                              │
│   hotspot (bash script) → python -m src [command]           │
│   Waybar module / Hyprland keybind / terminal               │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│               src/main.py  (Orchestrator)                    │
│  • argparse command dispatch                                 │
│  • CLI commands: start / stop / status / toggle / waybar    │
│  • GUI launcher with single-instance IPC (Unix socket)      │
│  • State file read/write (/tmp/hotspot_gui_state.json)       │
└──────┬────────────────────────────────┬──────────────────────┘
       │                                │
       ▼                                ▼
┌────────────────────┐    ┌─────────────────────────────────────┐
│  src/core/         │    │  src/gui/main_window.py             │
│  nm_dbus.py        │    │  • PyQt6 GUI (OrchestratorMainWindow)│
│  • NMDBusController│    │  • Start/Stop buttons               │
│    - start_hotspot │    │  • SSID + password form             │
│    - stop_hotspot  │    │  • Connected clients list           │
│    - device enum   │    │  • Background QThread workers       │
│    - wifi client   │    │  • 5-second polling timer           │
│      detection     │    │  • hide-on-close behavior           │
│    - hotspot       │    │  • themed warning dialogs           │
│      active check  │    └─────────────────────────────────────┘
│  stats.py          │
│  • NetworkStats    │
│    - reads ARP     │
│      table for     │
│      connected     │
│      clients       │
└────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│               NetworkManager (system daemon)                 │
│  nmcli device wifi hotspot  ← primary activation path       │
│  nmcli connection modify    ← routing metric protection      │
│  nmcli device reapply       ← live profile update           │
│  sdbus / D-Bus              ← device discovery + path lookup │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│               Wi-Fi Hardware (e.g. wlan0)                    │
│  NOTE: hotspot runs on the physical adapter directly.        │
│  Simultaneous client + AP mode is NOT supported on most      │
│  drivers (e.g. rtw88_8723de). The adapter is exclusively     │
│  used for the hotspot while it's active.                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Hotspot_GUI/
├── hotspot                     # Bash launcher script (Waybar / keybind entry)
├── requirements.txt            # Python dependencies
├── hyperland_cust.txt          # Hyprland + Waybar config snippets
├── docs/
│   ├── README.md               # Basic usage and integration guide
│   └── PROJECT_SUMMARY.md      # ← This file
└── src/
    ├── __init__.py
    ├── __main__.py             # Enables `python -m src` entry
    ├── main.py                 # CLI orchestrator + GUI launcher
    ├── constants.py            # Shared paths / identifiers
    ├── core/
    │   ├── __init__.py
    │   ├── nm_dbus.py          # NetworkManager controller (nmcli + D-Bus)
    │   └── stats.py            # Connected client discovery via /proc/net/arp
    └── gui/
        ├── __init__.py
        └── main_window.py      # PyQt6 main window + worker threads
```

---

## 🔍 Module-by-Module Breakdown

### `hotspot` (Bash Launcher)

The top-level entry point. It:
- Resolves the project root using `${BASH_SOURCE[0]}` / `$(dirname ...)`
- Resolves the **venv Python** at `$SCRIPT_DIR/venv/bin/python`
- Validates the venv exists and is executable — prints a helpful setup error if not
- Delegates all arguments to `python -m src "$@"` via `exec` (replacing the shell process, no subprocess overhead)

Used by Waybar (`exec`, `on-click`, `on-click-right`) and Hyprland keybinds.

---

### `src/constants.py`

Single source of truth for all shared paths:

| Constant | Value | Purpose |
|---|---|---|
| `STATE_FILE` | `/tmp/hotspot_gui_state.json` | Runtime hotspot state (shared between GUI & CLI) |
| `SOCKET_PATH` | `/tmp/hotspot_gui.sock` | Unix domain socket for GUI single-instance IPC |
| `CONFIG_FILE` | `~/.config/hotspot_gui.json` | Persistent user config (SSID + password) |

---

### `src/main.py` — The Orchestrator

Handles all CLI subcommands and GUI launching via `argparse`:

| Command | What It Does |
|---|---|
| `start [--ssid] [--password]` | Starts the hotspot using saved or given credentials; warns if Wi-Fi is active (interactive only) |
| `stop` | Stops and removes the active hotspot connection |
| `status` | Prints hotspot state + connected clients |
| `waybar` | Prints a JSON block for Waybar (text, class, tooltip) |
| `toggle` | Reads state file; starts if inactive, stops if active; non-interactive (no Wi-Fi warning prompt) |
| _(no command / `gui`)_ | Launches the PyQt6 GUI (single-instance via Unix socket) |

**Single-Instance IPC:**  
When `gui` is called and a socket already exists, the launcher sends `TOGGLE` to the existing window via the Unix socket — making it show/hide. This avoids spawning multiple window instances.

**State File:**  
The JSON state file at `/tmp/hotspot_gui_state.json` contains `con_name`, `iface`, `ssid`, `profile_path`, and `active_conn_path`. Both the CLI and GUI read/write this file to stay in sync.

**`QT_STYLE_OVERRIDE` removal:**  
Before launching the GUI, `os.environ.pop("QT_STYLE_OVERRIDE", None)` is called to prevent the system's Qt style from overriding the application's custom dark stylesheet.

---

### `src/core/nm_dbus.py` — `NMDBusController`

The networking backend. Uses a **hybrid approach**:

- **`nmcli` subprocess** for hotspot creation, modification, and teardown — more reliable than raw D-Bus because NetworkManager's internal `nmcli` code paths correctly handle wpa_supplicant → hostapd reconfiguration.
- **`sdbus` D-Bus** for device enumeration (finding the physical Wi-Fi adapter) and best-effort connection path discovery after activation.

#### Key Methods

| Method | Description |
|---|---|
| `get_devices()` | Returns all NM device D-Bus paths |
| `get_wifi_device_path()` | Returns the D-Bus path of the first physical Wi-Fi device (skips `ap*` virtual interfaces) |
| `get_device_iface(path)` | Returns the interface name (e.g. `wlan0`) for a device D-Bus path |
| `get_wifi_client_ssid()` | Returns the active Wi-Fi *client* SSID via `nmcli -t device`, or `None`. Distinguishes client mode (`connected`) from AP mode (`connected (locally only)`) |
| `is_hotspot_active(con_name)` | Checks `nmcli connection show --active` to see if the named hotspot is still running; returns `True` on error (safe default) |
| `start_hotspot(ssid, pw)` | Full activation sequence — see below |
| `stop_hotspot(con_name)` | Runs `nmcli connection down` + `nmcli connection delete`; errors are tolerated |
| `_find_connection_paths(con_name, iface)` | D-Bus lookup of `(profile_path, active_conn_path)` post-activation; returns `("", "")` on failure |

#### `start_hotspot()` Activation Sequence

1. **Device discovery** — finds the physical Wi-Fi interface via D-Bus
2. **Stale profile cleanup** — `nmcli connection delete <con_name>` (silently, so duplicate profiles don't accumulate)
3. **Activation** — `nmcli device wifi hotspot ifname <iface> ssid <ssid> password <pw> con-name <con_name>`
4. **Routing protection** — modifies the newly created profile:
   - `ipv4.never-default yes` — NM will NOT install a default route via the hotspot
   - `ipv4.route-metric 1000` — hotspot route metric is much higher than wired (≈100), so it never wins
   - `ipv6.never-default yes` + `ipv6.route-metric 1000` — same for IPv6
5. **Live reapply** — `nmcli device reapply <iface>` pushes the updated profile onto the already-active device without tearing it down
6. **Path discovery** — 0.5 s sleep → `_find_connection_paths()` via D-Bus

**Design Decision:** A virtual `ap0` interface is **not** created. Most consumer Wi-Fi drivers (e.g. `rtw88_8723de`) don't support concurrent virtual interfaces. The hotspot runs directly on `wlan0`.

---

### `src/core/stats.py` — `NetworkStats`

Reads `/proc/net/arp` to find connected clients on a given interface.

- Filters out incomplete ARP entries (`00:00:00:00:00:00`)
- Filters by interface name if provided
- Returns a list of `{ ip, mac, device }` dicts

Used by both the CLI `status` command and the GUI's polling timer.

---

### `src/gui/main_window.py` — `OrchestratorMainWindow`

The PyQt6 GUI window.

#### Layout

- `QGroupBox` — SSID + Password configuration form (`QFormLayout`)
- `QHBoxLayout` — Status label + Start / Stop buttons
- `QGroupBox` — Connected Clients list (`QListWidget`)

When the hotspot is active, the SSID and password inputs are disabled to prevent accidental edits.

#### Theme

Dark mode using a deep navy/charcoal palette with blue accent tones. The stylesheet is stored in a named `APP_STYLE` string constant (not an inline literal) so it can be retrieved via `self.styleSheet()` and reused by child dialogs.

**Color palette:**

| Token | Hex | Used For |
|---|---|---|
| Background deep | `#0b0b0f` | Window, base widget background |
| Background mid | `#101116` | GroupBox, list, input surfaces |
| Background light | `#15161e` | Input fields, pressed states |
| Background hover | `#1e202a` | Button + item default surface |
| Border subtle | `#282a36` | Widget borders |
| Border hover | `#3b3f52` | Hover borders |
| Accent primary | `#7994c6` | Button text, group titles, accent |
| Accent hover | `#92aadb` | Hover text, selected items |
| Accent pressed | `#617cac` | Pressed text |
| Text primary | `#c0c4d4` | Body text |
| Text muted | `#a4a8b6` | Labels |
| Text bright | `#e2e4ed` | Input field text |
| Text disabled | `#3b3f52` | Disabled button text |

#### Threading

Hotspot start/stop are offloaded to `QThread` workers to keep the UI responsive:

| Worker | Signal | Result |
|---|---|---|
| `HotspotStartThread` | `finished(bool, str, str, str, str, str)` | success, error_msg, con_name, iface, profile_path, active_conn_path |
| `HotspotStopThread` | `finished(bool, str)` | success, error_msg |

#### Polling

A `QTimer` fires every **5 seconds** to call `_update_stats()`, which:
1. Re-syncs the state file via `_sync_state()`
2. Detects external hotspot termination (see *Safety Feature 2* below)
3. Refreshes the connected clients list from `/proc/net/arp`

#### Hide-on-Close

`closeEvent` is overridden to:
1. Wait up to 5 s for any running `start_thread` / `stop_thread` to finish
2. Call `event.ignore()` + `self.hide()` — the window is hidden but never destroyed

This allows the IPC `TOGGLE` command to bring it back without re-launching the process.

#### IPC Slot

`toggle_visibility()` is a `@pyqtSlot` invoked via `QMetaObject.invokeMethod` from the IPC server thread using a `QueuedConnection` — ensuring it runs on the main GUI thread safely.

#### Config Persistence

SSID and password are saved to `~/.config/hotspot_gui.json` on each `Start` click and loaded back when the window first opens. Defaults are `Arch_Hotspot_123` / `12345678`.

#### Themed Dialogs — `_themed_warning()`

PyQt6's static `QMessageBox.warning()` renders dialogs using the system platform theme, completely ignoring the parent window's stylesheet. This causes dialogs to appear with the OS's default bright colors, breaking visual consistency.

The `_themed_warning(title, text)` helper fixes this by:
1. Instantiating `QMessageBox` directly (as a child of the main window)
2. Setting `RichText` format (`0x1`) so HTML in the message body renders correctly
3. Calling `msg.setStyleSheet(self.styleSheet())` to explicitly propagate the dark theme
4. Returning the `StandardButton` the user clicked

The `APP_STYLE` stylesheet includes `QMessageBox`-specific selectors:

| Selector | Effect |
|---|---|
| `QMessageBox` | Dark background `#101116` |
| `QMessageBox QLabel` | Themed text, transparent background, min-width for readability |
| `QMessageBox QPushButton` | Themed buttons (same as main UI) with extra horizontal padding |
| `QPushButton[default="true"]` | Accent fill (`#7994c6`) on the default button to make it visually distinct |

---

## 🛡️ Safety Features

### Feature 1 — Wi-Fi Client Conflict Warning

Both client and AP modes share the same physical Wi-Fi adapter. Starting the hotspot will forcibly disconnect any active Wi-Fi session.

**In the GUI:** `start_hotspot()` calls `get_wifi_client_ssid()` before beginning. If a client connection is found, `_themed_warning()` is shown with the SSID name and a Yes/No prompt. Cancelling aborts the start — no state is changed.

**In the CLI:** Only shown when `interactive=True` (i.e. the explicit `start` subcommand). The `toggle` path is **non-interactive** because it is triggered by Waybar/keybinds where there is no TTY to prompt on.

### Feature 2 — External Hotspot Termination Detection

If the user connects to a Wi-Fi network using any external tool (NM applet, `nmcli`, etc.), NetworkManager drops the hotspot AP connection to reclaim the adapter. The state file still says "active", but NM no longer lists the connection.

Every polling cycle, `_update_stats()` calls `is_hotspot_active(con_name)` which runs `nmcli connection show --active`. If the hotspot name is no longer present:
- State file is deleted
- UI is reset to "Inactive"
- Status label shows `"Status: Inactive  (stopped — Wi-Fi connected externally)"`

### Feature 3 — Routing Protection (No Wired Gateway Displacement)

The hotspot runs in "shared" mode. By default, NM may add a default route for the hotspot interface, displacing the wired connection's default gateway (breaking internet on the host machine).

After activation, `start_hotspot()` immediately modifies the profile:
- `ipv4.never-default yes` — prevent NM from installing a default route for the hotspot
- `ipv4.route-metric 1000` — even if a route is added, the very high metric ensures the wired route always wins
- Same for `ipv6`

Then `nmcli device reapply <iface>` pushes those settings live without disconnecting.

---

## 🔄 Data Flow: Starting a Hotspot

```
User clicks "Start" in GUI
    │
    ▼
OrchestratorMainWindow.start_hotspot()
    │  1. Validates SSID is not empty
    │  2. get_wifi_client_ssid() → show _themed_warning() if Wi-Fi active
    │  3. Saves config to ~/.config/hotspot_gui.json
    │
    ▼
HotspotStartThread.run()
    │
    ▼
NMDBusController.start_hotspot(ssid, password)
    │  1. sdbus → find physical wlan interface
    │  2. nmcli connection delete <old profile>  (cleanup)
    │  3. nmcli device wifi hotspot ifname wlan0 ssid ... password ...
    │  4. nmcli connection modify → never-default + route-metric
    │  5. nmcli device reapply <iface>
    │  6. sleep 0.5s → sdbus D-Bus path discovery
    │
    ▼
Returns (con_name, iface, profile_path, active_conn_path)
    │
    ▼
_on_start_finished() → writes /tmp/hotspot_gui_state.json
                      → _sync_state() updates UI
                      → _update_stats() refreshes client list
```

---

## 🔄 Data Flow: Polling Cycle (every 5 s)

```
QTimer.timeout → _update_stats()
    │
    ├─ _sync_state()        → re-reads state file, updates UI labels & button states
    │
    ├─ if hotspot inactive  → clear client list, return
    │
    ├─ is_hotspot_active()  → nmcli check; if no longer active:
    │       delete state file → _sync_state() → status "externally stopped"
    │
    └─ NetworkStats.get_active_clients() → /proc/net/arp → update QListWidget
```

---

## 🖥️ Waybar Integration

The `hotspot waybar` command outputs a JSON block:

```json
// When active
{ "text": "󰤨 2", "class": "active", "tooltip": "Hotspot Active: MySSID\nInterface: wlan0\nClients: 2" }

// When inactive
{ "text": "󰤭 ", "class": "inactive", "tooltip": "Hotspot Inactive" }
```

CSS classes `.active` / `.inactive` are applied for color theming in Waybar's `style.css`.

Typical Waybar `config.jsonc` entries:

```jsonc
{
  "exec":            "/home/t_s/Hotspot_GUI/hotspot waybar",
  "on-click":        "/home/t_s/Hotspot_GUI/hotspot toggle",
  "on-click-right":  "/home/t_s/Hotspot_GUI/hotspot gui"
}
```

---

## 🪟 Hyprland Integration

The GUI window has `WM_CLASS = HotspotGUI` (set via `QApplication.setApplicationName("HotspotGUI")`).

Window rules applied:
- `float on` — floats the window
- `center on` — centers it on screen
- `size 420 500` — fixed dimensions
- `opacity 0.6` — slight transparency

---

## ⚙️ Requirements

| Dependency | Purpose |
|---|---|
| Python 3.10+ | Type hints (`str \| None`), match statements |
| PyQt6 ≥ 6.6.0 | GUI framework |
| sdbus | D-Bus bindings for Python |
| sdbus-networkmanager | NetworkManager D-Bus API wrappers |
| NetworkManager | System network daemon (`nmcli` must be available) |
| Waybar | Optional — for status bar integration |
| Hyprland | Optional — for window rule integration |

---

## 🚀 Quick Start

```bash
# 1. Clone and set up venv
git clone <repo>
cd Hotspot_GUI
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Launch the GUI
python -m src gui

# 3. Or use CLI directly
python -m src start --ssid "MyNet" --password "s3cr3t"
python -m src status
python -m src toggle
python -m src stop

# 4. Or use the bash wrapper (works without activating venv)
./hotspot gui
./hotspot toggle
./hotspot waybar
```

---

## 🧠 Key Design Decisions

| Decision | Rationale |
|---|---|
| **`nmcli` for hotspot activation** | Bypasses NetworkManager's "device unavailable" restriction that blocks raw D-Bus calls on disconnected virtual interfaces |
| **`sdbus` for device discovery** | Clean Python API for querying device types, interface names, and active connection paths |
| **State file at `/tmp/`** | Bridges state between separate CLI invocations and the live GUI without a persistent daemon |
| **Unix socket for IPC** | Lightweight single-instance guard — Waybar's right-click doesn't spawn duplicate GUI windows |
| **`QThread` for hotspot ops** | Prevents GUI freeze during `nmcli` execution (which can take 1–3 seconds) |
| **Hide-on-close** | Allows Waybar's right-click to toggle the window without restarting the Python process |
| **No `ap0` virtual interface** | Avoids driver incompatibility on consumer hardware that doesn't support concurrent virtual interfaces |
| **Routing metric protection** | `ipv4/ipv6.never-default` + high route metric prevents the hotspot from displacing the wired default gateway |
| **`_themed_warning()` for dialogs** | PyQt6 static `QMessageBox` methods use the system theme and ignore the parent stylesheet — instantiating manually and calling `setStyleSheet(self.styleSheet())` is the only reliable way to enforce the dark theme in popups |
| **`QT_STYLE_OVERRIDE` removal** | Clears any system-set Qt style override before launching the GUI so the custom stylesheet is always applied cleanly |
| **Non-interactive `toggle`** | `toggle` is called by Waybar/keybinds with no TTY — disabling the Wi-Fi conflict prompt avoids hanging on a blocked `input()` call |

---

*Last updated: March 2026 (v1.3 — themed warning dialogs, routing protection, external termination detection)*
