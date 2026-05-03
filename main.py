import signal
import time

from bt_manager import BluetoothManager
from md_remote import SonyMDRemote

# CONFIGURATION
MD_DATA_PIN = 14
MD_SYNC_PIN = 15
BT_HEADSET_MAC = "XX:XX:XX:XX:XX:XX"  # Replace with your headset MAC


class MiniDiscBluetoothAdapter:
    def __init__(self):
        self.remote = SonyMDRemote(MD_DATA_PIN, MD_SYNC_PIN)
        self.bt = BluetoothManager()
        self.is_running = False

    def start(self):
        print("Starting Sony MiniDisc Bluetooth Adapter...")

        try:
            self.remote.start()

            # Uncomment if you want automatic reconnect during startup.
            # self.bt.pair_headset(BT_HEADSET_MAC)
            self.bt.setup_a2dp_source()

            self.bt.setup_avrcp_handler(self._handle_headset_command)
            self.bt.start_ble_service(self.remote.get_status(), self._handle_headset_command)

            self.is_running = True
        except Exception:
            self.shutdown()
            raise

    def run_main_loop(self):
        while self.is_running:
            status = self.remote.get_status()
            self.bt.update_ble_status(status)
            print(
                f"MD Status: {status['status']} | Track: {status['track']} | Title: {status['title']}"
            )
            time.sleep(5)

    def _handle_headset_command(self, cmd):
        """Maps headset/app commands to MD Remote command bytes."""
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
            "MODE": self.remote.PLAY_MODE,
        }
        command = mapping.get(cmd)
        if command is not None:
            self.remote.send_command(command)

    def handle_shutdown_signal(self, signum, _frame):
        print(f"\nReceived signal {signum}; shutting down...")
        self.shutdown()

    def shutdown(self):
        self.is_running = False
        self.bt.shutdown()
        self.remote.stop()


def main():
    adapter = MiniDiscBluetoothAdapter()
    signal.signal(signal.SIGINT, adapter.handle_shutdown_signal)
    signal.signal(signal.SIGTERM, adapter.handle_shutdown_signal)

    adapter.start()
    try:
        adapter.run_main_loop()
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    main()
