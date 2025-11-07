# test_ble.py
#
# A simple command-line tool to discover, connect to, and receive
# data from a CORTEX node. Useful for debugging the node firmware
# and the BLE protocol.

import asyncio
import struct
import logging
from bleak import BleakScanner, BleakClient

# --- Configuration ---
CORTEX_SERVICE_UUID = "6b3a0001-b5a3-f393-e0a9-e50e24dcca9e"
CORTEX_CHARACTERISTIC_UUID = "6b3a0002-b5a3-f393-e0a9-e50e24dcca9e"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BLE_Tester")

# --- Packet Definition ---
PACKET_FORMAT = "<4sB_BHffff_f"
PACKET_KEYS = [
    "magic", "node_id", "seq", "t_ms", "temp_c", "rh_pct",
    "pressure_hpa", "lux", "accel_g", "sound_dbfs"
]
PACKET_SIZE = 44

def parse_and_print_packet(data: bytearray):
    """Unpacks and prints the CORTEX packet."""
    if len(data) != PACKET_SIZE:
        logger.warning(f"Received packet of incorrect size: {len(data)} bytes")
        return

    try:
        values = struct.unpack(PACKET_FORMAT, data[:struct.calcsize(PACKET_FORMAT)])
        packet = dict(zip(PACKET_KEYS, values))

        if packet["magic"] != b'CTX1':
            logger.warning(f"Invalid magic bytes: {packet['magic']}")
            return

        print("--- CORTEX Packet Received ---")
        print(f"  Magic:      {packet['magic'].decode()}")
        print(f"  Node ID:    {packet['node_id']}")
        print(f"  Sequence:   {packet['seq']}")
        print(f"  Timestamp:  {packet['t_ms']} ms")
        print(f"  Temp:       {packet['temp_c']:.2f} °C")
        print(f"  Humidity:   {packet['rh_pct']:.2f} %")
        print(f"  Pressure:   {packet['pressure_hpa']:.2f} hPa")
        print(f"  Light:      {packet['lux']:.2f} lux")
        print(f"  Motion:     {packet['accel_g']:.3f} g")
        print(f"  Sound:      {packet['sound_dbfs']:.2f} dBFS")
        print("------------------------------\n")

    except struct.error as e:
        logger.error(f"Failed to unpack packet: {e}")

def notification_handler(sender, data: bytearray):
    """Callback for BLE notifications."""
    parse_and_print_packet(data)

async def main():
    """Scan for a CORTEX node and connect to it."""
    logger.info("Scanning for CORTEX nodes...")
    device = await BleakScanner.find_device_by_service_uuids(
        [CORTEX_SERVICE_UUID], timeout=10.0
    )

    if not device:
        logger.error("No CORTEX node found. Make sure it's advertising.")
        return

    logger.info(f"Found node: {device.name} ({device.address})")

    async with BleakClient(device) as client:
        if not client.is_connected:
            logger.error(f"Failed to connect to {device.address}")
            return

        logger.info(f"Connected. Subscribing to notifications...")
        await client.start_notify(CORTEX_CHARACTERISTIC_UUID, notification_handler)
        
        print("\nReceiving data... Press Ctrl+C to stop.")
        
        # Keep the script running to receive notifications
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping...")
