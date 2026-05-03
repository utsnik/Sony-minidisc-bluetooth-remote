import os
import subprocess
import threading
from typing import Callable, Dict, Optional

try:
    from bleak.uuids import normalize_uuid_str
except ImportError:  # pragma: no cover
    def normalize_uuid_str(uuid: str) -> str:
        return uuid.lower()

try:
    import dbus
    import dbus.exceptions
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib
except ImportError:  # pragma: no cover - non-Linux dev hosts
    dbus = None
    GLib = None


BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISEMENT_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
DEVICE_IFACE = "org.bluez.Device1"
ADAPTER_IFACE = "org.bluez.Adapter1"

A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"

SERVICE_UUID = normalize_uuid_str("0000ffe0-0000-1000-8000-00805f9b34fb")
STATUS_CHAR_UUID = normalize_uuid_str("0000ffe1-0000-1000-8000-00805f9b34fb")
COMMAND_CHAR_UUID = normalize_uuid_str("0000ffe2-0000-1000-8000-00805f9b34fb")
BATTERY_SERVICE_UUID = normalize_uuid_str("0000180f-0000-1000-8000-00805f9b34fb")
BATTERY_LEVEL_CHAR_UUID = normalize_uuid_str("00002a19-0000-1000-8000-00805f9b34fb")


def _to_dbus_byte_array(payload: str):
    return dbus.Array([dbus.Byte(byte) for byte in payload.encode("utf-8")], signature="y")


def _to_dbus_byte_value(value: int):
    return dbus.Array([dbus.Byte(max(0, min(255, int(value))))], signature="y")


if dbus:
    class InvalidArgsException(dbus.exceptions.DBusException):
        _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


    class NotSupportedException(dbus.exceptions.DBusException):
        _dbus_error_name = "org.bluez.Error.NotSupported"


    class FailedException(dbus.exceptions.DBusException):
        _dbus_error_name = "org.bluez.Error.Failed"


    class Application(dbus.service.Object):
        def __init__(self, bus):
            self.path = "/org/bluez/mdremote"
            self.services = []
            super().__init__(bus, self.path)

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def add_service(self, service):
            self.services.append(service)

        @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
        def GetManagedObjects(self):
            response = {}
            for service in self.services:
                response[service.get_path()] = service.get_properties()
                for chrc in service.characteristics:
                    response[chrc.get_path()] = chrc.get_properties()
            return response


    class Service(dbus.service.Object):
        def __init__(self, bus, index, uuid, primary):
            self.path = f"/org/bluez/mdremote/service{index}"
            self.bus = bus
            self.uuid = uuid
            self.primary = primary
            self.characteristics = []
            super().__init__(bus, self.path)

        def get_properties(self):
            return {
                GATT_SERVICE_IFACE: {
                    "UUID": self.uuid,
                    "Primary": self.primary,
                    "Characteristics": dbus.Array(
                        [ch.get_path() for ch in self.characteristics], signature="o"
                    ),
                }
            }

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def add_characteristic(self, characteristic):
            self.characteristics.append(characteristic)

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="ss", out_signature="v")
        def Get(self, interface, prop):
            props = self.get_properties().get(interface)
            if props is None or prop not in props:
                raise InvalidArgsException()
            return props[prop]

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
            props = self.get_properties().get(interface)
            if props is None:
                raise InvalidArgsException()
            return props


    class Characteristic(dbus.service.Object):
        def __init__(self, bus, index, uuid, flags, service):
            self.path = service.path + f"/char{index}"
            self.bus = bus
            self.uuid = uuid
            self.flags = flags
            self.service = service
            super().__init__(bus, self.path)

        def get_properties(self):
            return {
                GATT_CHRC_IFACE: {
                    "Service": self.service.get_path(),
                    "UUID": self.uuid,
                    "Flags": dbus.Array(self.flags, signature="s"),
                }
            }

        def get_path(self):
            return dbus.ObjectPath(self.path)

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="ss", out_signature="v")
        def Get(self, interface, prop):
            props = self.get_properties().get(interface)
            if props is None or prop not in props:
                raise InvalidArgsException()
            return props[prop]

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
            props = self.get_properties().get(interface)
            if props is None:
                raise InvalidArgsException()
            return props

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
        def ReadValue(self, options):
            raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
        def WriteValue(self, value, options):
            raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
            raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
            raise NotSupportedException()

        @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
        def PropertiesChanged(self, interface, changed, invalidated):
            pass


    class StatusCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
            super().__init__(bus, index, STATUS_CHAR_UUID, ["read", "notify"], service)
            self.notifying = False
            self.value = _to_dbus_byte_array("Unknown|Unknown|||Normal|Normal|0x00")
            self._lock = threading.Lock()

        def update_value(self, payload: str):
            with self._lock:
                self.value = _to_dbus_byte_array(payload)
                value = self.value
                notifying = self.notifying
            if notifying:
                self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
        def ReadValue(self, options):
            with self._lock:
                return self.value

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
            with self._lock:
                self.notifying = True

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
            with self._lock:
                self.notifying = False


    class BatteryCharacteristic(Characteristic):
        def __init__(self, bus, index, service, initial_level=0):
            super().__init__(bus, index, BATTERY_LEVEL_CHAR_UUID, ["read", "notify"], service)
            self.notifying = False
            self.value = _to_dbus_byte_value(initial_level)
            self._lock = threading.Lock()

        def update_value(self, level: int):
            with self._lock:
                self.value = _to_dbus_byte_value(level)
                value = self.value
                notifying = self.notifying
            if notifying:
                self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
        def ReadValue(self, options):
            with self._lock:
                return self.value

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
            with self._lock:
                self.notifying = True

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
            with self._lock:
                self.notifying = False


    class CommandCharacteristic(Characteristic):
        def __init__(self, bus, index, service, on_command_cb: Callable[[str], None]):
            super().__init__(
                bus,
                index,
                COMMAND_CHAR_UUID,
                ["write", "write-without-response"],
                service,
            )
            self.on_command_cb = on_command_cb

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
        def WriteValue(self, value, options):
            try:
                if int(options.get("offset", 0)) != 0:
                    raise InvalidArgsException("Command writes do not support offsets")
                cmd = bytes(int(byte) for byte in value).decode("utf-8").strip().upper()
                if cmd:
                    self.on_command_cb(cmd)
            except dbus.exceptions.DBusException:
                raise
            except Exception as exc:
                raise FailedException(str(exc))


    class Advertisement(dbus.service.Object):
        PATH_BASE = "/org/bluez/mdremote/advertisement"

        def __init__(self, bus, index):
            self.path = self.PATH_BASE + str(index)
            self.bus = bus
            self.local_name = "MD_Remote_Adapter"
            super().__init__(bus, self.path)

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def get_properties(self):
            return {
                LE_ADVERTISEMENT_IFACE: {
                    "Type": "peripheral",
                    "ServiceUUIDs": dbus.Array([SERVICE_UUID, BATTERY_SERVICE_UUID], signature="s"),
                    "LocalName": dbus.String(self.local_name),
                    "Includes": dbus.Array(["tx-power"], signature="s"),
                }
            }

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
            if interface != LE_ADVERTISEMENT_IFACE:
                raise InvalidArgsException()
            return self.get_properties()[LE_ADVERTISEMENT_IFACE]

        @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
        def Release(self):
            pass


class BluetoothManager:
    """
    Manages Bluetooth Classic (A2DP Source) and BLE (Status App).
    Uses BlueZ via DBus and minimal bleak UUID utilities.
    """

    def __init__(self):
        self.paired_device: Optional[str] = None
        self.is_streaming = False

        self.on_command: Optional[Callable[[str], None]] = None
        self.ble_command_cb: Optional[Callable[[str], None]] = None

        self._bus = None
        self._loop = None
        self._ble_thread = None
        self._ble_registered = False
        self._status_char = None
        self._battery_char = None
        self._gatt_manager = None
        self._ad_manager = None
        self._application = None
        self._advertisement = None
        self._ble_lock = threading.RLock()

    def pair_headset(self, mac_address):
        """Pairs and connects to a Bluetooth headset."""
        print(f"Pairing with {mac_address}...")
        try:
            subprocess.run(["bluetoothctl", "pair", mac_address], check=True)
            subprocess.run(["bluetoothctl", "trust", mac_address], check=True)
            subprocess.run(["bluetoothctl", "connect", mac_address], check=True)
            self.paired_device = mac_address
            return True
        except Exception as e:
            print(f"Pairing failed: {e}")
            return False

    def _ensure_dbus(self) -> bool:
        if not dbus:
            print("dbus-python/GLib not available; BlueZ DBus features disabled.")
            return False
        if self._bus:
            return True

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()
        return True

    def _get_managed_objects(self) -> Dict[str, Dict]:
        om = dbus.Interface(self._bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
        return om.GetManagedObjects()

    def _find_adapter_path(self):
        objects = self._get_managed_objects()
        for path, ifaces in objects.items():
            if ADAPTER_IFACE in ifaces and GATT_MANAGER_IFACE in ifaces and LE_ADVERTISEMENT_MANAGER_IFACE in ifaces:
                return path
        return None

    def _find_device_path(self, mac_address: str):
        target = mac_address.upper()
        objects = self._get_managed_objects()
        for path, ifaces in objects.items():
            props = ifaces.get(DEVICE_IFACE)
            if props and str(props.get("Address", "")).upper() == target:
                return path
        return None

    def setup_a2dp_source(self):
        """
        Configures BlueZ + PulseAudio/PipeWire to route audio
        from local input to a paired Bluetooth headset as A2DP sink.
        """
        print("Configuring A2DP audio routing...")
        if not self.paired_device:
            print("No paired headset set; skipping A2DP source setup.")
            return False

        if not self._ensure_dbus():
            return False

        try:
            dev_path = self._find_device_path(self.paired_device)
            if not dev_path:
                print("Paired device not found on BlueZ bus.")
                return False

            dev_obj = self._bus.get_object(BLUEZ_SERVICE_NAME, dev_path)
            props = dbus.Interface(dev_obj, DBUS_PROP_IFACE)
            dev = dbus.Interface(dev_obj, DEVICE_IFACE)

            props.Set(DEVICE_IFACE, "Trusted", dbus.Boolean(True))
            dev.ConnectProfile(A2DP_SINK_UUID)
            dev.Connect()

            # Route local audio to Bluetooth sink if PulseAudio/PipeWire is available.
            mac_underscored = self.paired_device.replace(":", "_")
            card = f"bluez_card.{mac_underscored}"
            sink = f"bluez_sink.{mac_underscored}.a2dp_sink"

            subprocess.run(["pactl", "set-card-profile", card, "a2dp-sink"], check=False)
            subprocess.run(["pactl", "set-default-sink", sink], check=False)

            self.is_streaming = True
            return True
        except Exception as e:
            print(f"Failed to setup A2DP source: {e}")
            return False

    def setup_avrcp_handler(self, on_command_cb):
        """
        Registers command callback used by AVRCP/MPRIS bridges.
        """
        print("Registering MPRIS2 Media Player bridge...")
        self.on_command = on_command_cb

    def _status_payload_from_state(self, status: Dict) -> str:
        def clean_field(value, default=""):
            text = str(value if value is not None else default)
            return text.replace("|", "/").replace("\r", " ").replace("\n", " ").strip()

        full_title = clean_field(status.get("title", "Unknown"), "Unknown")
        parts = full_title.split(" - ")
        artist = parts[0] if len(parts) > 1 else "Unknown"
        title = " - ".join(parts[1:]) if len(parts) > 1 else full_title

        disc = clean_field(status.get("disc", ""))
        time_str = clean_field(status.get("time", "--:--"), "--:--")
        eq = clean_field(status.get("eq", "Normal"), "Normal")
        play_mode = clean_field(status.get("play_mode", "Normal"), "Normal")
        debug = clean_field(status.get("debug_cmd", "0x00"), "0x00")

        return f"{artist}|{title}|{disc}|{time_str}|{eq}|{play_mode}|{debug}"

    def _battery_level_from_state(self, status: Dict) -> int:
        try:
            return max(0, min(100, int(status.get("battery", 0))))
        except (TypeError, ValueError):
            return 0

    def start_ble_service(self, track_info, on_command_cb):
        """
        Starts a BlueZ DBus GATT server for metadata + command writes.
        """
        print("Starting BLE Advertisement: 'MD_Remote_Adapter'...")
        self.ble_command_cb = on_command_cb

        if not self._ensure_dbus():
            return False

        with self._ble_lock:
            if self._ble_registered:
                self.update_ble_status(track_info)
                return True

        if not GLib:
            print("GLib not available; cannot run BlueZ BLE service.")
            return False

        try:
            adapter_path = self._find_adapter_path()
            if not adapter_path:
                print("No BLE-capable BlueZ adapter found.")
                return False

            adapter_obj = self._bus.get_object(BLUEZ_SERVICE_NAME, adapter_path)
            gatt_manager = dbus.Interface(adapter_obj, GATT_MANAGER_IFACE)
            ad_manager = dbus.Interface(adapter_obj, LE_ADVERTISEMENT_MANAGER_IFACE)

            app = Application(self._bus)
            md_service = Service(self._bus, 0, SERVICE_UUID, True)
            status_char = StatusCharacteristic(self._bus, 0, md_service)
            cmd_char = CommandCharacteristic(self._bus, 1, md_service, on_command_cb)
            md_service.add_characteristic(status_char)
            md_service.add_characteristic(cmd_char)
            app.add_service(md_service)

            battery_service = Service(self._bus, 1, BATTERY_SERVICE_UUID, True)
            battery_char = BatteryCharacteristic(
                self._bus, 0, battery_service, self._battery_level_from_state(track_info)
            )
            battery_service.add_characteristic(battery_char)
            app.add_service(battery_service)

            advertisement = Advertisement(self._bus, 0)

            with self._ble_lock:
                self._gatt_manager = gatt_manager
                self._ad_manager = ad_manager
                self._application = app
                self._advertisement = advertisement
                self._status_char = status_char
                self._battery_char = battery_char
                self.update_ble_status(track_info)

            self._loop = GLib.MainLoop()
            registered = {"app": False, "ad": False}
            ready = threading.Event()

            def register_objects():
                def on_success(kind):
                    registered[kind] = True
                    if registered["app"] and registered["ad"]:
                        with self._ble_lock:
                            self._ble_registered = True
                        ready.set()

                def on_error(label, error):
                    print(f"{label} failed: {error}")
                    ready.set()

                gatt_manager.RegisterApplication(
                    app.get_path(),
                    {},
                    reply_handler=lambda: on_success("app"),
                    error_handler=lambda e: on_error("BLE app registration", e),
                )
                ad_manager.RegisterAdvertisement(
                    advertisement.get_path(),
                    {},
                    reply_handler=lambda: on_success("ad"),
                    error_handler=lambda e: on_error("BLE advertisement", e),
                )

            def run_loop():
                try:
                    register_objects()
                    self._loop.run()
                except Exception as exc:
                    print(f"BLE GLib loop failed: {exc}")
                    ready.set()

            self._ble_thread = threading.Thread(target=run_loop, daemon=True)
            self._ble_thread.start()
            if not ready.wait(timeout=5.0):
                print("BLE registration timed out waiting for BlueZ.")
                self.stop_ble_service()
                return False
            with self._ble_lock:
                if self._ble_registered:
                    return True
            self.stop_ble_service()
            return False
        except Exception as e:
            print(f"BLE service failed to start: {e}")
            self.stop_ble_service()
            return False

    def update_ble_status(self, status):
        """Updates the status characteristic with new track metadata."""
        payload = self._status_payload_from_state(status)
        battery_level = self._battery_level_from_state(status)
        print(f"[BLE] Broadcasting: {payload}")
        with self._ble_lock:
            status_char = self._status_char
            battery_char = self._battery_char
            loop = self._loop

        def apply_update():
            if status_char:
                status_char.update_value(payload)
            if battery_char:
                battery_char.update_value(battery_level)
            return False

        if loop and GLib:
            GLib.idle_add(apply_update)
        else:
            apply_update()

    def stop_ble_service(self):
        """Unregisters BLE DBus objects and stops the GLib loop."""
        with self._ble_lock:
            loop = self._loop
            thread = self._ble_thread
            app = self._application
            advertisement = self._advertisement
            gatt_manager = self._gatt_manager
            ad_manager = self._ad_manager

        if not loop:
            return

        stopped = threading.Event()

        def unregister_and_quit():
            try:
                if advertisement and ad_manager:
                    try:
                        ad_manager.UnregisterAdvertisement(advertisement.get_path())
                    except Exception as exc:
                        print(f"BLE advertisement unregister failed: {exc}")
                if app and gatt_manager:
                    try:
                        gatt_manager.UnregisterApplication(app.get_path())
                    except Exception as exc:
                        print(f"BLE app unregister failed: {exc}")
            finally:
                with self._ble_lock:
                    self._ble_registered = False
                    self._status_char = None
                    self._battery_char = None
                    self._application = None
                    self._advertisement = None
                    self._gatt_manager = None
                    self._ad_manager = None
                loop.quit()
                stopped.set()
            return False

        if GLib:
            GLib.idle_add(unregister_and_quit)
        else:
            unregister_and_quit()

        stopped.wait(timeout=3.0)
        if thread:
            thread.join(timeout=3.0)
            if thread.is_alive():
                print("Warning: BLE GLib thread did not stop within timeout.")

        with self._ble_lock:
            if not stopped.is_set():
                self._ble_registered = False
                self._status_char = None
                self._battery_char = None
                self._application = None
                self._advertisement = None
                self._gatt_manager = None
                self._ad_manager = None
            self._loop = None
            self._ble_thread = None

    def shutdown(self):
        self.stop_ble_service()
        self.is_streaming = False


if __name__ == "__main__":
    bt = BluetoothManager()
    bt.setup_a2dp_source()
    bt.start_ble_service({"title": "No Disc"}, lambda cmd: print(cmd))
