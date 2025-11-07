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

# --- Globals ---
# In-memory cache for the latest values from each node
last_values_cache: Dict[str, Dict[str, Any]] = {}
# IPC queue for publishing data to other processes (renderer, web)
ipc_queue = asyncio.Queue()
# List of connected IPC clients (for the publisher)
ipc_clients: List[asyncio.StreamWriter] = []


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
    async with aiosqlite.connect(DB_PATH) as db:
        while True:
            packet, mac = await queue.get()
            ts_utc = datetime.utcnow().isoformat() + "Z"
            
            # Apply calibration offsets here (to be implemented)

            await db.execute(
                """
                INSERT INTO readings (ts_utc, mac, node_id, seq, t_ms, temp_c, rh_pct, pressure_hpa, lux, accel_g, sound_dbfs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_utc, mac, packet['node_id'], packet['seq'], packet['t_ms'],
                    packet['temp_c'], packet['rh_pct'], packet['pressure_hpa'],
                    packet['lux'], packet['accel_g'], packet['sound_dbfs']
                )
            )
            await db.commit()
            
            # Update in-memory cache
            packet['ts_utc'] = ts_utc
            packet['mac'] = mac
            last_values_cache[mac] = packet
            
            # Put data onto IPC queue for other services
            await ipc_queue.put(packet)
            
            queue.task_done()
            logger.debug(f"Wrote packet from Node {packet['node_id']} (Seq: {packet['seq']}) to DB.")

# --- BLE Client Logic ---
async def notification_handler(sender, data: bytearray, db_queue: asyncio.Queue, mac: str):
    """Handles incoming BLE notifications."""
    logger.debug(f"Received data from {mac}: {data.hex()}")
    packet = parse_packet(data)
    if packet:
        await db_queue.put((packet, mac))

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


# --- Main Application Logic ---
async def main():
    """Main entry point for the CORTEX Hub."""
    await init_db()
    
    db_queue = asyncio.Queue()
    asyncio.create_task(db_writer(db_queue))
    
    # Start the IPC publisher and server
    ipc_server = await asyncio.start_server(handle_ipc_client, IPC_HOST, IPC_PORT)
    asyncio.create_task(ipc_publisher())
    logger.info(f"IPC server started on {IPC_HOST}:{IPC_PORT}")


    while True:
        logger.info("Starting BLE scan for CORTEX nodes...")
        try:
            devices = await bleak.BleakScanner.discover(
                service_uuids=[CORTEX_SERVICE_UUID], timeout=10.0
            )
        except bleak.exc.BleakError as e:
            logger.error(f"BLE scan failed. Is the adapter powered on? Error: {e}")
            await asyncio.sleep(10)
            continue

        for device in devices:
            if device.rssi < MIN_RSSI:
                logger.debug(f"Ignoring {device.name} due to weak signal ({device.rssi} < {MIN_RSSI})")
                continue
            
            # Check if we are already trying to connect to this device
            # A simple way is to check active tasks. A more robust way would be a connection manager.
            if device.address not in [t.get_name() for t in asyncio.all_tasks()]:
                task = asyncio.create_task(run_ble_client(device, db_queue))
                task.set_name(device.address) # Name the task by the device address for tracking

        logger.info(f"Scan finished. Found {len(devices)} nodes. Waiting before next scan...")
        await asyncio.sleep(15) # Wait before scanning again


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CORTEX Hub shutting down.")
