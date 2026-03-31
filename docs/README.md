# Arch Linux Network & Hotspot Manager

A Python-based GUI application that provides **Windows-like hotspot control** on Arch Linux — built as a high-level orchestrator over Network services using PyQt6.

---

## Features

* One-click Hotspot Toggle (like Windows Mobile Hotspot)
* Clean PyQt6 GUI Interface
* Real-time Hotspot Status Monitoring
* Smart Backend Orchestration (hostapd / networking stack)
* Waybar Integration (status + controls)
* Hyprland Optimized Window Rules
* CLI + GUI Hybrid Usage

---

## Waybar Integration

This project integrates seamlessly with Waybar, allowing you to control and monitor the hotspot directly from your status bar.

## Configuration (`config.jsonc`)

Add the module to your `modules-right` section:

```jsonc
{
    "layer": "top",
    "position": "top",
    
    // ... your modules-left and modules-center ...

    // 1. Add the module as the FIRST item in modules-right
    "modules-right": [
        "custom/hotspot-gui",  // <-- Right next to the center
        "pulseaudio",
        "network",
        "battery",
        "clock",
        "tray"
    ],


    // ... your other module definitions ...

    // 2. Add the custom module definition at the bottom of the file
    "custom/hotspot-gui": {
        "format": "{}",
        "return-type": "json",
        "exec": "/home/t_s/Hotspot_GUI/hotspot waybar",
        "interval": 3,
        "on-click": "/home/t_s/Hotspot_GUI/hotspot toggle",
        "on-click-right": "/home/t_s/Hotspot_GUI/hotspot gui",
        "tooltip": true
    }

}

```

## Behavior

* **Left Click** → Toggle hotspot ON/OFF
* **Right Click** → Open GUI
* **Auto Refresh** → Updates every 3 seconds

---

## Styling (`style.css`)

Customize hotspot state appearance:

```css
#custom-hotspot-gui.active {
    color: #a6e3a1; /* Active (green) */
}

#custom-hotspot-gui.inactive {
    color: #6c7086; /* Inactive (gray) */
}
```

---

##  Hyprland Integration

Optimized for floating window behavior in Hyprland.

## Configuration (`hyprland.conf`)

```ini
# Hotspot GUI Rules
# Qt sets WM_CLASS to the applicationName — which is "HotspotGUI".

# Float and center
windowrule = match:class ^HotspotGUI$, float on
windowrule = match:class ^HotspotGUI$, center on

# Fixed size
windowrule = match:class ^HotspotGUI$, size 420 500

# Opacity
windowrule = opacity 0.6, match:class ^HotspotGUI$
```

---

## 💻 CLI Usage

You can control the hotspot directly from terminal:

```bash
# Run from the Hotspot_GUI project root with venv active:
python -m src toggle   # Toggle hotspot on/off (uses saved config)
python -m src gui      # Launch or toggle GUI
python -m src waybar   # Output Waybar JSON status block
python -m src start --ssid MyNet --password s3cr3t  # Start with custom SSID
python -m src status   # Show status and connected clients
```

---

## Architecture Overview

```
[ GUI / Waybar / CLI ]
            ↓
[ Python Orchestrator (PyQt6 + argparse) ]
            ↓
[ NetworkManager (sdbus D-Bus, virtual iw interface) ]
            ↓
[ Wi-Fi Hardware ]
```

---

## Requirements

* Arch Linux
* NetworkManager (system default)
* Python 3.10+
* PyQt6
* sdbus-networkmanager
* Waybar (optional)
* Hyprland (optional)

---

## Installation

```bash
git clone https://github.com/yourusername/hotspot-manager.git
cd hotspot-manager

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## Run

```bash
# From the project root, with venv activated:
source venv/bin/activate
python -m src gui
```

---

## Design Philosophy

This project aims to:

* Replace complex Linux networking commands with a **simple GUI**
* Provide a **stable hotspot experience like Windows**
* Integrate deeply with **Wayland ecosystem tools**
* Stay lightweight, modular, and hackable

---

## Future Enhancements

* Connected device monitoring
* VPN sharing over hotspot
* Live password change
* Band selection (2.4GHz / 5GHz)
* System tray integration
* AUR package release

---

## Contributing

Pull requests and ideas are welcome.
Feel free to fork and enhance the project.

---

## License

MIT License

---

## Support

If you like this project, consider giving it a star ⭐
