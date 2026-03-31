import subprocess
import time
from typing import Optional

from sdbus import sd_bus_open_system
from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkManagerSettings,
    NetworkDeviceGeneric,
    NetworkConnectionSettings,
)


class NMDBusController:
    """
    Controller for NetworkManager.

    Uses `nmcli device wifi hotspot` for hotspot creation because it has
    NM-internal code paths that correctly handle device state transitions.
    D-Bus is used for device enumeration and best-effort path discovery.

    NOTE: A virtual `ap0` interface is NOT created.  Many drivers (e.g.
    rtw88_8723de) list no valid interface combinations and cannot support
    two simultaneous virtual interfaces.  The hotspot runs directly on the
    physical Wi-Fi adapter (e.g. wlan0).  This means the adapter cannot
    simultaneously act as a Wi-Fi client and a hotspot.
    """

    def __init__(self):
        self.bus = sd_bus_open_system()
        self.nm = NetworkManager(self.bus)
        self.settings = NetworkManagerSettings(self.bus)

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    def get_devices(self):
        return self.nm.get_devices()

    def get_wifi_device_path(self) -> Optional[str]:
        """Return the D-Bus path of the first physical Wi-Fi device."""
        for dev_path in self.get_devices():
            dev = NetworkDeviceGeneric(dev_path, self.bus)
            if dev.device_type == 2:  # NM_DEVICE_TYPE_WIFI
                iface = getattr(dev, "interface", "") or ""
                # Skip virtual interfaces (ap0, ap1 …) if any exist
                if iface.startswith("ap"):
                    continue
                return dev_path
        return None

    def get_device_iface(self, dev_path: str) -> str:
        return NetworkDeviceGeneric(dev_path, self.bus).interface

    def get_wifi_client_ssid(self) -> Optional[str]:
        """
        Return the name of the active Wi-Fi *client* connection, or None.

        Uses `nmcli -t device` terse output.  In client mode NM reports
        the device STATE as "connected"; in hotspot/AP mode it reports
        "connected (locally only)".  We use that distinction so we never
        mistake an active hotspot for an active client connection.
        """
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"],
                capture_output=True,
                text=True,
            )
            for line in res.stdout.strip().splitlines():
                # Terse format: TYPE:STATE:CONNECTION
                # STATE in client mode is exactly "connected" (no suffix).
                # STATE in AP mode is "connected (locally only)".
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                dev_type, state, connection = parts
                if dev_type == "wifi" and state == "connected":
                    # Extra safety: exclude any profile we recognise as a hotspot
                    if not connection.endswith(" Hotspot"):
                        return connection
        except Exception:
            pass
        return None

    def is_hotspot_active(self, con_name: str) -> bool:
        """
        Return True if *con_name* appears in NetworkManager's active
        connection list.  Used by the GUI polling loop to detect when the
        hotspot was terminated externally (e.g. user connected to Wi-Fi
        and NM dropped the AP connection automatically).

        Returns True on any error to avoid false-positive cleanup.
        """
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
                capture_output=True,
                text=True,
            )
            active_names = res.stdout.strip().splitlines()
            return con_name in active_names
        except Exception:
            return True  # safe default — assume still active


    # ------------------------------------------------------------------
    # Hotspot lifecycle
    # ------------------------------------------------------------------

    def start_hotspot(self, ssid: str, password: str) -> tuple[str, str, str, str]:
        """
        Create and activate a Wi-Fi hotspot on the physical Wi-Fi interface.

        Returns:
            (con_name, iface, profile_path, active_conn_path)
            profile_path / active_conn_path are best-effort — may be "".

        Raises RuntimeError on failure.
        """
        # --- discover the physical Wi-Fi interface ----------------------
        wifi_dev_path = self.get_wifi_device_path()
        if not wifi_dev_path:
            raise RuntimeError("No Wi-Fi device found.")
        iface = self.get_device_iface(wifi_dev_path)

        con_name = ssid + " Hotspot"

        # --- remove any stale profile with the same name ----------------
        subprocess.run(
            ["nmcli", "connection", "delete", con_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # --- activate ---------------------------------------------------
        # `nmcli device wifi hotspot` has NM-internal privilege to activate
        # even on a DISCONNECTED device and handles the full wpa_supplicant
        # → hostapd reconfiguration cycle.
        res = subprocess.run(
            [
                "nmcli", "device", "wifi", "hotspot",
                "ifname",   iface,
                "ssid",     ssid,
                "password", password,
                "con-name", con_name,
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "nmcli hotspot failed"
            raise RuntimeError(err)

        # --- protect wired/other connections ----------------------------
        # The hotspot runs in "shared" mode and NM may add a default route
        # for it, displacing the wired default gateway.  Fix this by:
        #   1. ipv4.never-default yes  → NM will NOT install a default route
        #      for the hotspot, so the wired connection keeps its gateway.
        #   2. ipv4.route-metric 1000  → Even if a route is added, a very
        #      high metric means it will never win over the wired route
        #      (which defaults to metric ~100).
        #   3. ipv6.never-default yes  → same protection for IPv6.
        # We then call `nmcli device reapply` to push these settings onto
        # the already-active device without tearing it down.
        subprocess.run(
            [
                "nmcli", "connection", "modify", con_name,
                "ipv4.never-default", "yes",
                "ipv4.route-metric",  "1000",
                "ipv6.never-default", "yes",
                "ipv6.route-metric",  "1000",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # reapply applies the updated profile to the live device without
        # fully deactivating/reactivating the connection.
        subprocess.run(
            ["nmcli", "device", "reapply", iface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # --- best-effort D-Bus path discovery ---------------------------
        time.sleep(0.5)   # give NM a moment to register the active connection
        profile_path, active_conn_path = self._find_connection_paths(con_name, iface)

        return con_name, iface, profile_path, active_conn_path

    def stop_hotspot(self, con_name: str):
        """
        Deactivate and delete hotspot profile via nmcli.
        Errors are tolerated — we want cleanup to proceed regardless.
        """
        subprocess.run(
            ["nmcli", "connection", "down", con_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["nmcli", "connection", "delete", con_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_connection_paths(self, con_name: str, iface: str) -> tuple[str, str]:
        """Look up (profile_path, active_conn_path) — returns "" on failure."""
        profile_path = ""
        active_conn_path = ""

        try:
            for conn_path in self.settings.list_connections():
                conn = NetworkConnectionSettings(conn_path, self.bus)
                s = conn.get_settings()
                conn_id = s.get("connection", {}).get("id", (None, None))
                if isinstance(conn_id, (list, tuple)) and conn_id[-1] == con_name:
                    profile_path = conn_path
                    break
        except Exception:
            pass

        try:
            from sdbus_block.networkmanager import ActiveConnection
            for ac_path in self.nm.active_connections:
                ac = ActiveConnection(ac_path, self.bus)
                for dev_path in (getattr(ac, "devices", None) or []):
                    dev = NetworkDeviceGeneric(dev_path, self.bus)
                    if getattr(dev, "interface", None) == iface:
                        active_conn_path = ac_path
                        break
                if active_conn_path:
                    break
        except Exception:
            pass

        return profile_path, active_conn_path
