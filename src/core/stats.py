# Data Acquisition logic
import os


class NetworkStats:
    def __init__(self, dbus_controller):
        self.dbus_ctrl = dbus_controller

    def get_active_clients(self, iface: str | None = None) -> list:
        """
        Read /proc/net/arp and return connected clients on *iface*.

        Args:
            iface: Network interface to filter on (e.g. "wlan0").
                   Pass None to return ALL non-zero ARP entries (not recommended).

        Returns a list of dicts: {'ip', 'mac', 'device'}.
        """
        clients = []
        try:
            if not os.path.exists("/proc/net/arp"):
                return clients

            with open("/proc/net/arp", "r") as f:
                f.readline()    # skip header
                for line in f:
                    parts = line.split()
                    if len(parts) >= 6:
                        ip     = parts[0]
                        mac    = parts[3]
                        device = parts[5]

                        if mac == "00:00:00:00:00:00":
                            continue
                        if iface is not None and device != iface:
                            continue

                        clients.append({"ip": ip, "mac": mac, "device": device})
        except Exception as e:
            print(f"Error reading ARP table: {e}")

        return clients
