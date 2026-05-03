import threading
import time
import traceback

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - unavailable on non-Pi dev machines
    GPIO = None


class SonyMDRemote:
    """
    Handles the Sony MiniDisc remote protocol.
    Pins 1 & 3 are used for a single-wire bi-directional serial protocol.
    Pin 4/2 are used for resistive button detection or common ground.
    """

    # Standard Command Bytes (Hex)
    PLAY = 0x01
    PAUSE = 0x02
    STOP = 0x03
    NEXT = 0x04
    PREV = 0x05
    VOL_UP = 0x06
    VOL_DOWN = 0x07
    DISPLAY = 0x08
    SOUND = 0x09
    GRP_NEXT = 0x0A
    GRP_PREV = 0x0B
    PLAY_MODE = 0x0C  # For Shuffle/Repeat cycling

    def __init__(self, data_pin, sync_pin):
        self.data_pin = data_pin
        self.sync_pin = sync_pin
        self.track_title = ""
        self.track_number = 0
        self.playback_status = "STOPPED"
        self.battery_level = 0
        self.eq_mode = "Normal"
        self.play_mode = "Normal"
        self._running = False
        self._thread = None
        self._gpio_initialized = False
        self._lock = threading.RLock()
        self._last_listener_error = 0.0

    def start(self):
        """Initializes the GPIO and starts the background listener thread."""
        with self._lock:
            if self._running:
                return
            self._setup_gpio()
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                print("Warning: MD listener thread did not stop within timeout.")
            self._thread = None
        with self._lock:
            if self._gpio_initialized and GPIO:
                GPIO.output(self.data_pin, GPIO.HIGH)
                GPIO.output(self.sync_pin, GPIO.HIGH)
                GPIO.cleanup([self.data_pin, self.sync_pin])
                self._gpio_initialized = False

    def _setup_gpio(self):
        if not GPIO:
            print("RPi.GPIO not available; running in simulation mode.")
            return
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.data_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.sync_pin, GPIO.OUT, initial=GPIO.HIGH)
        self._gpio_initialized = True

    def _listen_loop(self):
        """
        Background loop to parse incoming data from the MD player.
        Protocol:
        - 11-byte Frame (typically) or 10-byte.
        - Byte 0: Header / Sync.
        - Bytes 1-9: Data / Display Characters.
        - Checksum at the end.
        Note: The protocol is active-low serial.
        """
        print("Listening for Sony MD Serial Data...")
        while self._running:
            try:
                packet = self._read_packet()
                if packet:
                    self._parse_packet(packet)
            except Exception as exc:
                now = time.monotonic()
                if now - self._last_listener_error >= 5.0:
                    self._last_listener_error = now
                    print(f"MD listener error: {exc}")
                    traceback.print_exc(limit=1)

            time.sleep(0.01)

    def _read_packet(self):
        """Simulate reading a packet (bit-banging logic placeholder)."""
        return [0xA5, 0x01, 0x48, 0x65, 0x6C, 0x6C, 0x6F, 0x00, 0x00, 0xFF]

    def _parse_packet(self, packet):
        """Decodes the 10-byte packet into status and text."""
        if len(packet) < 3:
            raise ValueError(f"Short MD packet: expected at least 3 bytes, got {len(packet)}")

        cmd = packet[0]
        with self._lock:
            self.last_cmd = cmd

            if cmd == 0x46:  # Battery
                self.battery_level = max(0, min(100, int(packet[2]) * 25))

            elif cmd == 0x47:  # EQ
                sound_modes = ["Normal", "Bass 1", "Bass 2"]
                idx = packet[2] if packet[2] < len(sound_modes) else 0
                self.eq_mode = sound_modes[idx]

            elif cmd == 0xA1:  # Play Mode
                modes = ["Normal", "All Repeat", "1 Track", "Shuffle"]
                idx = packet[2] if packet[2] < len(modes) else 0
                self.play_mode = modes[idx]

            else:
                self.track_title = "Billie Jean"
                self.playback_status = "PLAYING"

    def send_command(self, command_hex):
        """
        Sends a command byte by GPIO bit-banging on the MD data/sync lines.

        Timing is intentionally conservative (hundreds of microseconds) to remain
        stable in Python userspace on Raspberry Pi.
        """
        if not isinstance(command_hex, int) or not 0 <= command_hex <= 0xFF:
            raise ValueError(f"Invalid MD command byte: {command_hex!r}")

        with self._lock:
            print(f"Sending MD Command: {hex(command_hex)}")
            if not self._gpio_initialized or not GPIO:
                return

            bit_delay = 0.00025  # 250us half-cycle

            def set_lines(data_level, sync_level):
                GPIO.output(self.data_pin, data_level)
                GPIO.output(self.sync_pin, sync_level)

            try:
                # Bus idle is high/high.
                set_lines(GPIO.HIGH, GPIO.HIGH)
                time.sleep(bit_delay)

                # Start frame: pull sync low, then data low.
                set_lines(GPIO.HIGH, GPIO.LOW)
                time.sleep(bit_delay)
                set_lines(GPIO.LOW, GPIO.LOW)
                time.sleep(bit_delay)

                # Shift out command MSB first on data, clocked by sync.
                for bit_index in range(7, -1, -1):
                    bit_val = (command_hex >> bit_index) & 0x01
                    GPIO.output(self.data_pin, GPIO.HIGH if bit_val else GPIO.LOW)

                    GPIO.output(self.sync_pin, GPIO.HIGH)
                    time.sleep(bit_delay)
                    GPIO.output(self.sync_pin, GPIO.LOW)
                    time.sleep(bit_delay)

                # Stop frame and return to idle.
                set_lines(GPIO.HIGH, GPIO.LOW)
                time.sleep(bit_delay)
            finally:
                set_lines(GPIO.HIGH, GPIO.HIGH)
                time.sleep(bit_delay)

    def enter_service_mode(self):
        """
        Attempts to enter Service Mode automatically.
        Prerequisite: User must manually enable the 'HOLD' switch on the player.
        Sequence: Vol- (Hold), Right, Right, Left, Left, Right, Left, Right, Left, Pause, Pause.
        """
        print("Initiating Service Mode Sequence...")
        print("PLEASE ENSURE 'HOLD' SWITCH IS ON!")
        time.sleep(2)

        combo = [
            self.NEXT,
            self.NEXT,
            self.PREV,
            self.PREV,
            self.NEXT,
            self.PREV,
            self.NEXT,
            self.PREV,
            self.PAUSE,
            self.PAUSE,
        ]

        for cmd in combo:
            self.send_command(cmd)
            time.sleep(0.4)

        print("Sequence Complete. Check Player Screen.")

    def get_status(self):
        """Returns current playback metadata."""
        with self._lock:
            return {
                "title": self.track_title,
                "track": self.track_number,
                "status": self.playback_status,
                "battery": self.battery_level if self.battery_level else 75,
                "time": "02:14",
                "disc": "Best of Synthwave",
                "eq": self.eq_mode,
                "play_mode": self.play_mode,
                "debug_cmd": hex(getattr(self, "last_cmd", 0x00)),
            }

    def get_device_id(self):
        """
        Queries the MD Player for its Device ID/Serial.
        Note: The protocol supports capability queries. Bank 5 often contains the ID.
        """
        print("Querying Device ID...")
        return "Sony MZ-N10 (Mock)"


if __name__ == "__main__":
    remote = SonyMDRemote(data_pin=14, sync_pin=15)
    remote.start()
    try:
        print(f"Connected Device: {remote.get_device_id()}")

        while True:
            print(f"Status: {remote.get_status()}")
            time.sleep(2)
    except KeyboardInterrupt:
        remote.stop()
