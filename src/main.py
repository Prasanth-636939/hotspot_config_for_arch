import sys
import os
import json
import socket
import argparse
from threading import Thread, Event

from .core.nm_dbus import NMDBusController
from .core.stats import NetworkStats
from .constants import STATE_FILE, SOCKET_PATH, CONFIG_FILE


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def get_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"con_name": None, "iface": None, "ssid": None}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def load_saved_config() -> tuple[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                return cfg.get("ssid", "Arch_Hotspot_123"), cfg.get("password", "12345678")
        except (json.JSONDecodeError, OSError):
            pass
    return "Arch_Hotspot_123", "12345678"


def _is_active(state: dict) -> bool:
    return bool(state.get("con_name") or state.get("active_conn_path"))


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cli_start(ssid: str, password: str, interactive: bool = True):
    state = get_state()
    if _is_active(state):
        print("Hotspot is already running.")
        return

    dbus_ctrl = NMDBusController()

    # Warn if Wi-Fi is currently connected in client mode.
    # Both client and AP modes share the physical adapter, so starting the
    # hotspot will disconnect any active Wi-Fi session.
    # Only prompt when running interactively (i.e. the explicit `start`
    # sub-command from a terminal).  The `toggle` path is non-interactive
    # because it is called by Waybar and keybinds.
    if interactive:
        wifi_ssid = dbus_ctrl.get_wifi_client_ssid()
        if wifi_ssid:
            print(f"⚠  Wi-Fi is currently connected to: '{wifi_ssid}'")
            print("   Starting the hotspot will disconnect it (same adapter).")
            try:
                answer = input("   Continue? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            if answer != "y":
                print("Aborted.")
                return

    print(f"Starting hotspot: {ssid}")
    try:
        con_name, iface, profile_path, active_conn_path = dbus_ctrl.start_hotspot(ssid, password)
    except RuntimeError as e:
        print(f"Error: {e}")
        return

    save_state({
        "con_name":         con_name,
        "iface":            iface,
        "active_conn_path": active_conn_path,
        "profile_path":     profile_path,
        "ssid":             ssid,
    })
    print(f"Hotspot started successfully on {iface}.")


def cli_stop():
    state = get_state()
    con_name = state.get("con_name") or (
        (state.get("ssid") or "") + " Hotspot" if state.get("ssid") else None
    )
    if not con_name:
        print("Hotspot is not running.")
        return

    print("Stopping hotspot…")
    dbus_ctrl = NMDBusController()
    try:
        dbus_ctrl.stop_hotspot(con_name)
    except Exception as e:
        print(f"Warning during stop: {e}")

    clear_state()
    print("Hotspot stopped successfully.")


def cli_status():
    state = get_state()
    if not _is_active(state):
        print("Status: Inactive")
        return

    iface = state.get("iface")
    print(f"Status: Active  (SSID: {state.get('ssid')}, Interface: {iface})")
    clients = NetworkStats(None).get_active_clients(iface)
    print(f"Connected Clients: {len(clients)}")
    for c in clients:
        print(f"  - {c['ip']}  ({c['mac']})  on {c['device']}")


def cli_waybar():
    state = get_state()
    if not _is_active(state):
        print(json.dumps({"text": "󰤭 ", "class": "inactive", "tooltip": "Hotspot Inactive"}))
        return

    iface = state.get("iface")
    clients = NetworkStats(None).get_active_clients(iface)
    count = len(clients)
    ssid = state.get("ssid", "Unknown")
    print(json.dumps({
        "text":    f"󰤨 {count}",
        "class":   "active",
        "tooltip": f"Hotspot Active: {ssid}\nInterface: {iface}\nClients: {count}",
    }))


# ---------------------------------------------------------------------------
# GUI launcher
# ---------------------------------------------------------------------------

def start_gui():
    if os.path.exists(SOCKET_PATH):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(SOCKET_PATH)
                s.sendall(b"TOGGLE")
            return
        except socket.error:
            os.remove(SOCKET_PATH)

    os.environ.pop("QT_STYLE_OVERRIDE", None)

    from PyQt6.QtWidgets import QApplication
    from .gui.main_window import OrchestratorMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("HotspotGUI")

    dbus_ctrl = NMDBusController()
    main_win = OrchestratorMainWindow(dbus_ctrl)

    stop_event = Event()

    def ipc_server():
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(1)
        server.settimeout(1.0)
        while not stop_event.is_set():
            try:
                conn, _ = server.accept()
                with conn:
                    data = conn.recv(1024)
                    if data == b"TOGGLE":
                        import PyQt6.QtCore as QtCore
                        QtCore.QMetaObject.invokeMethod(
                            main_win,
                            "toggle_visibility",
                            QtCore.Qt.ConnectionType.QueuedConnection,
                        )
            except socket.timeout:
                continue
            except Exception:
                pass
        server.close()

    Thread(target=ipc_server, daemon=True).start()

    main_win.show()
    try:
        app.exec()
    finally:
        stop_event.set()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Arch Linux Wi-Fi Hotspot Orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    parser_start = subparsers.add_parser("start", help="Start the hotspot")
    parser_start.add_argument("--ssid",     default=None)
    parser_start.add_argument("--password", default=None)

    subparsers.add_parser("stop")
    subparsers.add_parser("status")
    subparsers.add_parser("waybar")
    subparsers.add_parser("toggle")
    subparsers.add_parser("gui")

    args = parser.parse_args()

    if args.command == "start":
        saved_ssid, saved_pass = load_saved_config()
        cli_start(args.ssid or saved_ssid, args.password or saved_pass)
    elif args.command == "stop":
        cli_stop()
    elif args.command == "status":
        cli_status()
    elif args.command == "waybar":
        cli_waybar()
    elif args.command == "toggle":
        state = get_state()
        if _is_active(state):
            cli_stop()
        else:
            ssid, password = load_saved_config()
            cli_start(ssid, password, interactive=False)
    else:
        start_gui()


if __name__ == "__main__":
    main()
