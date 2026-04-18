package com.example.mdremote

import android.Manifest
import android.bluetooth.*
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.content.pm.PackageManager
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import java.util.*

class MainActivity : AppCompatActivity() {

    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bluetoothGatt: BluetoothGatt? = null
    private var isGattConnected: Boolean = false
    private lateinit var mediaSession: MediaSession
    
    // UUIDs must match your Python script
    private val SERVICE_UUID = UUID.fromString("0000ffe0-0000-1000-8000-00805f9b34fb")
    private val CHAR_UUID = UUID.fromString("0000ffe1-0000-1000-8000-00805f9b34fb")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize MediaSession (Lock Screen Controls)
        mediaSession = MediaSession(this, "MDRemoteSession").apply {
            setCallback(object : MediaSession.Callback() {
                override fun onPlay() { /* Send BLE Command: Play */ }
                override fun onPause() { /* Send BLE Command: Pause */ }
                override fun onSkipToNext() { /* Send BLE Command: Next */ }
            })
            setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS or MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS)
            isActive = true
        }

        findViewById<Button>(R.id.btnConnect).setOnClickListener {
            startBleScan()
        }

        findViewById<ImageButton>(R.id.btnPlayPause).setOnClickListener { sendBleCommand("PLAY") }
        findViewById<ImageButton>(R.id.btnNext).setOnClickListener { sendBleCommand("NEXT") }
        findViewById<ImageButton>(R.id.btnPrev).setOnClickListener { sendBleCommand("PREV") }
        findViewById<ImageButton>(R.id.btnStop).setOnClickListener { sendBleCommand("STOP") }
        
        findViewById<Button>(R.id.btnMode).setOnClickListener { sendBleCommand("MODE") }
        findViewById<Button>(R.id.btnSound).setOnClickListener { sendBleCommand("SOUND") }
        findViewById<Button>(R.id.btnInfo).setOnClickListener { sendBleCommand("DISPLAY") }
        findViewById<Button>(R.id.btnGroup).setOnClickListener { sendBleCommand("GRP_NEXT") }
    }

    private fun sendBleCommand(cmd: String) {
        val gatt = bluetoothGatt
        if (gatt == null || !isGattConnected) {
            Log.w("MDRemote", "Cannot send command, GATT is not connected")
            return
        }

        val service = gatt.getService(SERVICE_UUID) ?: run {
            Log.w("MDRemote", "BLE service not found")
            return
        }
        val char = service.getCharacteristic(UUID.fromString("0000ffe2-0000-1000-8000-00805f9b34fb")) ?: run {
            Log.w("MDRemote", "Command characteristic not found")
            return
        }
        char.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        char.value = cmd.toByteArray()
        gatt.writeCharacteristic(char)
    }

    private fun startBleScan() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED) {
            // Request permissions logic here
            return
        }
        
        val scanner = BluetoothAdapter.getDefaultAdapter().bluetoothLeScanner
        scanner.startScan(object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult?) {
                result?.device?.let { device ->
                    if (device.name == "MD_Remote_Adapter") {
                        scanner.stopScan(this)
                        connectToDevice(device)
                    }
                }
            }
        })
    }

    private fun connectToDevice(device: BluetoothDevice) {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) return

        bluetoothGatt = device.connectGatt(this, false, object : BluetoothGattCallback() {
            override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                    isGattConnected = true
                    gatt.discoverServices()
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    isGattConnected = false
                }
            }

            override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
                val service = gatt.getService(SERVICE_UUID)
                val characteristic = service.getCharacteristic(CHAR_UUID)
                gatt.setCharacteristicNotification(characteristic, true)
            }

            override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
                val value = characteristic.getStringValue(0)
                // Expected format "Artist|Title"
                val parts = value.split("|")
                val artist = if (parts.isNotEmpty()) parts[0] else ""
                val title = if (parts.size > 1) parts[1] else value

                runOnUiThread {
                    findViewById<Button>(R.id.btnConnect).visibility = android.view.View.GONE
                    findViewById<TextView>(R.id.txtTitle).text = title
                    findViewById<TextView>(R.id.txtArtist).text = artist
                    
                    // Trigger Art Download (Placeholder)
                    // downloadArt(artist, title) 
                    
                    updateMediaSession(title)
                }
            }
        })
    }

    private fun updateMediaSession(title: String) {
        val stateBuilder = PlaybackState.Builder()
            .setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_SKIP_TO_NEXT)
            .setState(PlaybackState.STATE_PLAYING, 0, 1f)
        mediaSession.setPlaybackState(stateBuilder.build())
        
        // Metadata (Title, Artist, Art) update logic goes here
    }
}
