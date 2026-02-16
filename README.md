# Sony MiniDisc Bluetooth Remote (Modernized) 💿✨

**Bring your 90s MiniDisc player into the 2020s.**
This project turns a Raspberry Pi into a "smart" Bluetooth adapter for Sony MiniDisc portables. It connects to the player's proprietary 4-pin remote port to read metadata and send commands, while simultaneously acting as a Bluetooth Audio source for your modern headphones.

![Concept](https://raw.githubusercontent.com/utsnik/Sony_MD_Bluetooth/main/doc/concept.png)

## 🌟 Features

*   **Dual Mode Bluetooth**: 
    *   **Audio**: Streams high-quality A2DP audio to your wireless headphones.
    *   **Data**: Broadcasts track info via BLE to your Phone/Laptop.
*   **Parallel Control**: Control playback using:
    *   Headset Buttons (AVRCP) 🎧
    *   Web App / Android App 📱
    *   Original Player Buttons ⏯️
*   **Advanced Remote Feautres**:
    *   Full Metadata Display (Artist, Title, Disc Name, Time)
    *   Player Status Monitoring (Battery Level, EQ Mode, Play Mode)
    *   "Raw Debug" Mode for protocol reverse-engineering.
*   **Zero-Install Web App**: Just open a web page to see album art and control your player.

## 📂 Project Structure

*   `main.py`: The central hub. Orchestrates the remote protocol and Bluetooth services.
*   `md_remote.py`: Driver for the Sony Wired Remote Protocol (GPIO bit-banging).
*   `bt_manager.py`: Handles BlueZ (Linux Bluetooth Stack), A2DP, BLE, and AVRCP.
*   `index.html`: **The Web App.** A standalone file you can host anywhere to control the Pi.
*   `android_app/`: Source code for the native Android companion app.

## 🔌 Hardware Setup

### Wiring
You need to splice a Sony 4-pin remote connector (from an old broken remote) to the Raspberry Pi GPIO headers.

| MD Pin | Function | RPi Pin | Note |
|---|---|---|---|
| **1** | Data (IO) | **GPIO 14** (TXD) | via 1kΩ Resistor |
| **3** | Sync (IO) | **GPIO 15** (RXD) | via 1kΩ Resistor |
| **2/4** | GND | **GND** | |

**Audio Input:**
Connect the MD Player's 3.5mm Headphone Jack -> **USB Sound Card (Line In)** on the Pi.

## 🚀 Installation

1.  **Clone this repo**:
    ```bash
    git clone https://github.com/utsnik/Sony_MD_Bluetooth.git
    cd Sony_MD_Bluetooth
    ```

2.  **Install Dependencies** (Raspberry Pi OS):
    ```bash
    sudo apt-get update
    sudo apt-get install python3-pip bluez pulseaudio-module-bluetooth libglib2.0-dev
    pip3 install RPi.GPIO bleak dbus-python
    ```

3.  **Pair your Headset**:
    ```bash
    bluetoothctl
    scan on
    pair <HEADSET_MAC>
    trust <HEADSET_MAC>
    connect <HEADSET_MAC>
    ```

4.  **Configure**:
    Edit `main.py` and set your headset's MAC address if you want auto-connect.

## ▶️ Usage

Run the adapter:
```bash
sudo python3 main.py
```

### 📱 Connecting the App
1.  **Web App**: Open `index.html` in Chrome (PC/Android) or Bluefy (iOS). Click **Connect**.
2.  **Android App**: Build and install the APK from `android_app/`. Tap **Connect**.

## 🛠️ Debugging
The Web App includes a "Raw Cmd" footer. If you press a button on the MD player that isn't recognized, the Hex code will appear there. You can add it to `md_remote.py` to map new features!
