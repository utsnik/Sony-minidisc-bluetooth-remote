import os
import subprocess

class BluetoothManager:
    """
    Manages Bluetooth Classic (A2DP Source) and BLE (Status App).
    Uses BlueZ via DBus or command-line utilities.
    """
    
    def __init__(self):
        self.paired_device = None
        self.is_streaming = False

    def pair_headset(self, mac_address):
        """Pairs and connects to a Bluetooth headset."""
        print(f"Pairing with {mac_address}...")
        # bluetoothctl commands
        try:
            subprocess.run(["bluetoothctl", "pair", mac_address], check=True)
            subprocess.run(["bluetoothctl", "trust", mac_address], check=True)
            subprocess.run(["bluetoothctl", "connect", mac_address], check=True)
            self.paired_device = mac_address
            return True
        except Exception as e:
            print(f"Pairing failed: {e}")
            return False

    def setup_a2dp_source(self):
        """
        Configures PulseAudio/PipeWire to route audio 
        from USB ADC to Bluetooth Headset.
        """
        print("Configuring A2DP audio routing...")
        # 1. Load module-loopback in PulseAudio
        # 2. Set sink to the Bluetooth device
        # os.system("pactl load-module module-loopback source=... sink=...")
        pass

    def setup_avrcp_handler(self, on_command_cb):
        """
        Registers an MPRIS2 interface on DBus. 
        This allows BlueZ to forward headset button presses to this script.
        
        on_command_cb: function(command_name) 
        """
        print("Registering MPRIS2 Media Player bridge...")
        # In a real Pi implementation, you'd use 'mpris2' or 'pydbus' library:
        # 1. Create a DBus object at /org/mpris/MediaPlayer2/MDRemote
        # 2. Implement org.mpris.MediaPlayer2.Player methods (Play, Pause, Next, Prev)
        # 3. In each method, call on_command_cb(CMD)
        
        self.on_command = on_command_cb
        
        # Example: if a 'Next' button is pressed on the headset, BlueZ triggers 
        # the MPRIS 'Next' method.
        pass

    def start_ble_service(self, track_info, on_command_cb):
        """
        Starts a BLE GATT server to broadcast track info to the phone app.
        Also listens for commands from the app.
        """
        print("Starting BLE Advertisement: 'MD_Remote_Adapter'...")
        # ...
        
        # 4. Setup Command Characteristic (Write):
        #    Characteristic 3 (Write): Command String ("PLAY", "NEXT", etc.)
        self.ble_command_cb = on_command_cb
        
        # NOTE: When a write arrives from the App, it triggers self.ble_command_cb(CMD)
        pass

    def update_ble_status(self, status):
        """Updates the characteristics with new track info."""
        if status.get('title'):
            # Format: "Artist|Title|Disc|Time"
            # Note: MD often combines Artist/Title. We might need heuristic splitting in md_remote.py later.
            # For now, assuming title contains "Artist - Title" or just Title.
            
            # Mocking Artist split for demo if not present
            full_title = status.get('title', 'Unknown')
            parts = full_title.split(' - ')
            artist = parts[0] if len(parts) > 1 else "Unknown"
            title = parts[1] if len(parts) > 1 else full_title
            
            disc = status.get('disc', '')
            time_str = status.get('time', '--:--')
            eq = status.get('eq', 'Normal')
            play_mode = status.get('play_mode', 'Normal')
            debug = status.get('debug_cmd', '0x00')
            
            payload = f"{artist}|{title}|{disc}|{time_str}|{eq}|{play_mode}|{debug}"
            
            print(f"[BLE] Broadcasting: {payload}")
            # valid_characteristic.write(payload.encode('utf-8'))


# Example Usage
if __name__ == "__main__":
    bt = BluetoothManager()
    # bt.pair_headset("00:11:22:33:44:55")
    bt.setup_a2dp_source()
    bt.start_ble_service({"title": "No Disc"})
