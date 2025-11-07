# cortex_hub.py
#
# Main CORTEX process. Handles:
# - BLE discovery and connection to nodes
# - Data ingestion and parsing
# - Database writing
# - IPC publishing of live data
# - Running core analytics routines

import asyncio
import logging
import struct
import os
from datetime import datetime
from typing import Dict, Optional, List, Any

import bleak
import aiosqlite
from dotenv import load_dotenv

import json

# Import analytics modules
import algorithms
import predictor
import personality

# --- Globals ---
# In-memory cache for the latest values from each node
last_values_cache: Dict[str, Dict[str, Any]] = {}
# IPC queue for publishing data to other processes (renderer, web)
ipc_queue = asyncio.Queue()
# List of connected IPC clients (for the publisher)
ipc_clients: List[asyncio.StreamWriter] = []

# Analytics state
cortex_personality: Optional[personality.Personality] = None
calibration_data: Dict[int, Dict[str, float]] = {}


# --- Configuration Loading ---
load_dotenv()
CORTEX_SERVICE_UUID = os.getenv("CORTEX_SERVICE_UUID", "6b3a0001-b5a3-f393-e0a9-e50e24dcca9e")
DB_PATH = os.getenv("DB_PATH", "cortex.db")
MIN_RSSI = int(os.getenv("MIN_RSSI", -80))
IPC_HOST = os.getenv("IPC_HOST", "127.0.0.1")
IPC_PORT = int(os.getenv("IPC_PORT", 6789))

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("CortexHub")

# --- BLE Packet Definition ---
# Corresponds to the struct in the Arduino code
# <4sB_BHffff_f
PACKET_FORMAT = "<4sB_BHffff_f" # Using _ for reserved byte, and another f for sound
PACKET_KEYS = [
    "magic", "node_id", "seq", "t_ms", "temp_c", "rh_pct",
    "pressure_hpa", "lux", "accel_g", "sound_dbfs"
]
PACKET_SIZE = 44 # Expected size in bytes

# --- Database Setup ---
async def init_db():
    """Initializes the database from the schema file."""
    async with aiosqlite.connect(DB_PATH) as db:
        with open("schema.sql", "r") as f:
            await db.executescript(f.read())
        await db.commit()
    logger.info(f"Database initialized at {DB_PATH}")

# --- Data Handling ---
def parse_packet(data: bytearray) -> Optional[Dict[str, Any]]:
    """Parses a raw BLE packet."""
    if len(data) != PACKET_SIZE:
        logger.warning(f"Invalid packet size: got {len(data)}, expected {PACKET_SIZE}")
        return None

    # Unpack the data using the format string
    # Note: The struct may have more fields than keys if there's padding
    values = struct.unpack(PACKET_FORMAT, data[:struct.calcsize(PACKET_FORMAT)])
    
    packet = dict(zip(PACKET_KEYS, values))

    # Validate magic bytes
    if packet["magic"] != b'CTX1':
        logger.warning(f"Invalid magic bytes: {packet['magic']}")
        return None
        
    # Decode magic bytes for JSON serialization
    packet["magic"] = packet["magic"].decode('utf-8')

    # Replace NaN with None for JSON compatibility
    for key, value in packet.items():
        if isinstance(value, float) and value != value: # Check for NaN
            packet[key] = None

    return packet

async def db_writer(queue: asyncio.Queue):
    """A coroutine that reads from a queue and writes to the database."""
    global last_values_cache
    async with aiosqlite.connect(DB_PATH) as db:
        while True:
            packet, mac = await queue.get()
            ts_utc = datetime.utcnow().isoformat() + "Z"
            
            # Apply calibration offsets
            calibrated_packet = algorithms.apply_calibration(packet.copy())

            await db.execute(
                """
                INSERT INTO readings (ts_utc, mac, node_id, seq, t_ms, temp_c, rh_pct, pressure_hpa, lux, accel_g, sound_dbfs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_utc, mac, calibrated_packet['node_id'], calibrated_packet['seq'], calibrated_packet['t_ms'],
                    calibrated_packet['temp_c'], calibrated_packet['rh_pct'], calibrated_packet['pressure_hpa'],
                    calibrated_packet['lux'], calibrated_packet['accel_g'], calibrated_packet['sound_dbfs']
                )
            )
            await db.commit()
            
            # Update in-memory cache with calibrated data
            calibrated_packet['ts_utc'] = ts_utc
            calibrated_packet['mac'] = mac
            last_values_cache[mac] = calibrated_packet
            
            # Put data onto IPC queue for other services
            await ipc_queue.put({"type": "reading", "data": calibrated_packet})
            
            queue.task_done()
            logger.debug(f"Wrote packet from Node {calibrated_packet['node_id']} (Seq: {calibrated_packet['seq']}) to DB.")

# --- BLE Client Logic ---
def notification_handler(sender, data: bytearray, db_queue: asyncio.Queue, mac: str):
    """Handles incoming BLE notifications."""
    logger.debug(f"Received data from {mac}: {data.hex()}")
    packet = parse_packet(data)
    if packet:
        # Schedule the async operation as a task
        asyncio.create_task(db_queue.put((packet, mac)))

async def run_ble_client(device: bleak.BLEDevice, db_queue: asyncio.Queue):
    """Manages the connection and subscription for a single CORTEX node."""
    logger.info(f"Attempting to connect to {device.name} ({device.address})...")
    
    async with bleak.BleakClient(device) as client:
        if not client.is_connected:
            logger.warning(f"Failed to connect to {device.address}")
            return

        logger.info(f"Connected to {device.address}")
        
        # The characteristic UUID we want to subscribe to
        char_uuid = CORTEX_SERVICE_UUID.replace("0001", "0002")

        # Create a partial function to pass extra arguments to the handler
        handler = lambda sender, data: notification_handler(sender, data, db_queue, device.address)
        
        try:
            await client.start_notify(char_uuid, handler)
            logger.info(f"Subscribed to notifications on {char_uuid} for {device.address}")
            
            # Keep the connection alive
            while client.is_connected:
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Error with device {device.address}: {e}")
        
        finally:
            logger.warning(f"Disconnected from {device.address}")
            if device.address in last_values_cache:
                del last_values_cache[device.address]

# --- IPC Publisher ---
async def handle_ipc_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles a new IPC client connection."""
    addr = writer.get_extra_info('peername')
    logger.info(f"IPC client connected: {addr}")
    ipc_clients.append(writer)
    try:
        # Keep the connection open, but do nothing with incoming data
        while not reader.at_eof():
            _ = await reader.read(100)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info(f"IPC client disconnected: {addr}")
        ipc_clients.remove(writer)
        writer.close()
        await writer.wait_closed()

async def ipc_publisher():
    """Publishes data from the IPC queue to all connected clients."""
    while True:
        data = await ipc_queue.get()
        message = json.dumps(data).encode('utf-8') + b'\n'
        
        disconnected_clients = []
        for client in ipc_clients:
            if not client.is_closing():
                try:
                    client.write(message)
                    await client.drain()
                except (ConnectionResetError, BrokenPipeError):
                    logger.warning(f"IPC client disconnected abruptly: {client.get_extra_info('peername')}")
                    disconnected_clients.append(client)
            else:
                disconnected_clients.append(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            if client in ipc_clients:
                ipc_clients.remove(client)

        ipc_queue.task_done()
        logger.debug(f"[IPC PUB] Sent data to {len(ipc_clients)} clients.")

# --- Analytics Processor ---
async def analytics_processor():
    """Periodically runs analytics and publishes results."""
    global cortex_personality
    async with aiosqlite.connect(DB_PATH) as db:
        cortex_personality = personality.Personality(db)
        await cortex_personality.load_state()

        while True:
            await asyncio.sleep(5) # Run analytics every 5 seconds

            if not last_values_cache:
                logger.debug("No node data in cache for analytics.")
                continue

            nodes_data = list(last_values_cache.values())
            
            # 1. Spatial Awareness
            fused_data = algorithms.fuse_spatial(nodes_data)
            spatial_gradients = algorithms.spatial_gradient(nodes_data)

            # 2. Occupancy Detection (Placeholder for BLE device count)
            # For now, assume 0 BLE devices detected
            ble_device_count = 0 
            occupancy = algorithms.occupancy_state(nodes_data, ble_device_count)

            # 3. Personality Update
            cortex_personality.update(fused_data, occupancy["state"])
            personality_state = cortex_personality.get_current_properties()

            # 4. Prediction (Simplified for now, needs historical data)
            # This would typically query the DB for recent history
            prediction_result = predictor.forecast_linear([], 30) # Empty history for now

            # Aggregate and send via IPC
            analytics_results = {
                "type": "analytics",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "fused_data": fused_data,
                "spatial_gradients": spatial_gradients,
                "occupancy": occupancy,
                "personality_state": personality_state,
                "prediction": prediction_result
            }
            await ipc_queue.put(analytics_results)
            logger.debug("Analytics processed and published.")


# --- Main Application Logic ---
async def main():
    """Main entry point for the CORTEX Hub."""
    global calibration_data
    await init_db()
    
    # Load calibration data at startup
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT node_id, metric, offset_value FROM calibration")
        calibration_rows = await cursor.fetchall()
        algorithms.load_calibration_offsets([dict(row) for row in calibration_rows])
    
    db_queue = asyncio.Queue()
    asyncio.create_task(db_writer(db_queue))
    
    # Start the IPC publisher and server
    ipc_server = await asyncio.start_server(handle_ipc_client, IPC_HOST, IPC_PORT)
    asyncio.create_task(ipc_publisher())
    logger.info(f"IPC server started on {IPC_HOST}:{IPC_PORT}")

    # Start the analytics processor
    asyncio.create_task(analytics_processor())


    # The main BLE scanner loop
    while True:
        logger.info("Starting BLE scan for CORTEX nodes...")
        processed_in_this_scan = set()

        try:
            # Define the core scanning logic in a separate async function
            async def scan_logic():
                async with bleak.BleakScanner() as scanner:
                    async for device, advertisement_data in scanner.advertisement_data():
                        # Check if it's a CORTEX node
                        if CORTEX_SERVICE_UUID not in advertisement_data.service_uuids:
                            continue
                        
                        # Check if we've already processed this device in this scan cycle
                        if device.address in processed_in_this_scan:
                            continue

                        rssi = advertisement_data.rssi
                        if rssi < MIN_RSSI:
                            logger.debug(f"Ignoring {device.name} due to weak signal ({rssi} < {MIN_RSSI})")
                            continue

                        # Check if we already have an active connection task for this device
                        if device.address not in [t.get_name() for t in asyncio.all_tasks()]:
                            logger.info(f"Found CORTEX node: {device.name} ({rssi} dBm)")
                            task = asyncio.create_task(run_ble_client(device, db_queue))
                            task.set_name(device.address)
                            processed_in_this_scan.add(device.address)

            # Run the scan logic with a 10-second timeout
            await asyncio.wait_for(scan_logic(), timeout=10.0)

        except asyncio.TimeoutError:
            logger.info(f"Scan finished. Found {len(processed_in_this_scan)} new nodes in this cycle.")
        except bleak.exc.BleakError as e:
            logger.error(f"BLE scan failed. Is the adapter powered on? Error: {e}")

        await asyncio.sleep(15) # Wait before scanning again


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CORTEX Hub shutting down.")
