import time
import signal
import sys
from md_remote import SonyMDRemote
from bt_manager import BluetoothManager

# CONFIGURATION
MD_DATA_PIN = 14
MD_SYNC_PIN = 15
BT_HEADSET_MAC = "XX:XX:XX:XX:XX:XX"  # Replace with your headset MAC

class MiniDiscBluetoothAdapter:
    def __init__(self):
        self.remote = SonyMDRemote(MD_DATA_PIN, MD_SYNC_PIN)
        self.bt = BluetoothManager()
        self.is_running = True

    def start(self):
        print("Starting Sony MiniDisc Bluetooth Adapter...")
        
        # 1. Initialize MD Remote Protocol
        self.remote.start()
        
        # 2. Setup Bluetooth Audio
        # self.bt.pair_headset(BT_HEADSET_MAC)
        self.bt.setup_a2dp_source()
        
        # 3. Setup Headset Button Control (AVRCP)
        self.bt.setup_avrcp_handler(self._handle_headset_command)
        
        # 4. Start BLE Status Service (Share the command handler with AVRCP)
        self.bt.start_ble_service(self.remote.get_status(), self._handle_headset_command)
        
        # 5. Main Control Loop
        try:
            while self.is_running:
                status = self.remote.get_status()
                # Update BLE service if track info changed
                # self.bt.update_ble_status(status)
                
                print(f"MD Status: {status['status']} | Track: {status['track']} | Title: {status['title']}")
                time.sleep(5)
        except KeyboardInterrupt:
            self.shutdown()

    def _handle_headset_command(self, cmd):
        """Maps headset buttons to MD Remote commands."""
        print(f"Headset Command Received: {cmd}")
        mapping = {
            "PLAY": self.remote.PLAY,
            "PAUSE": self.remote.PAUSE,
            "NEXT": self.remote.NEXT,
            "PREV": self.remote.PREV,
            "STOP": self.remote.STOP,
            "DISPLAY": self.remote.DISPLAY,
            "SOUND": self.remote.SOUND,
            "GRP_NEXT": self.remote.GRP_NEXT,
            "GRP_PREV": self.remote.GRP_PREV,
            "MODE": self.remote.PLAY_MODE
        }
        if cmd in mapping:
            self.remote.send_command(mapping[cmd])

    def shutdown(self):
        print("\nShutting down...")
        self.is_running = False
        self.remote.stop()
        sys.exit(0)

if __name__ == "__main__":
    adapter = MiniDiscBluetoothAdapter()
    adapter.start()
