# calibrate.py
#
# An interactive tool to help calibrate sensor offsets for CORTEX nodes.
#
# Workflow:
# 1. User is instructed to co-locate all nodes in a stable environment.
# 2. The tool connects to all available nodes and collects data for a "burn-in" period.
# 3. It calculates the average reading for each sensor type across all nodes.
# 4. It then determines the offset of each individual node from that average.
# 5. These offsets are stored in the database and a local JSON file for the hub to use.

import asyncio
import json
import logging
import time
from typing import Dict, List, Any
import numpy as np
import aiosqlite
from bleak import BleakScanner

# --- Configuration ---
CORTEX_SERVICE_UUID = "6b3a0001-b5a3-f393-e0a9-e50e24dcca9e"
CORTEX_CHARACTERISTIC_UUID = "6b3a0002-b5a3-f393-e0a9-e50e24dcca9e"
DB_PATH = "../pi/cortex.db"
CALIBRATION_FILE_PATH = os.path.expanduser("~/.cortex/calibration.json")
BURN_IN_DURATION_S = 1200 # 20 minutes
METRICS_TO_CALIBRATE = ['temp_c', 'rh_pct', 'lux']

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("CalibrateTool")

# --- Globals ---
all_readings: Dict[str, List[Dict[str, Any]]] = {}

# --- BLE Handling (similar to hub/tester) ---
PACKET_FORMAT = "<4sB_BHffff_f"
PACKET_KEYS = ["magic", "node_id", "seq", "t_ms", "temp_c", "rh_pct", "pressure_hpa", "lux", "accel_g", "sound_dbfs"]

def parse_packet(data: bytearray) -> Dict:
    values = struct.unpack(PACKET_FORMAT, data[:struct.calcsize(PACKET_FORMAT)])
    return dict(zip(PACKET_KEYS, values))

def notification_handler(sender, data: bytearray, mac: str):
    packet = parse_packet(data)
    if packet['magic'] != b'CTX1': return
    
    if mac not in all_readings:
        all_readings[mac] = []
    
    # Convert NaN to None
    for key, value in packet.items():
        if isinstance(value, float) and value != value:
            packet[key] = None
            
    all_readings[mac].append(packet)
    print(f"\rGot packet from {mac} (Node {packet['node_id']}). Total packets: {sum(len(v) for v in all_readings.values())}", end="")

async def run_collector(devices):
    """Connect to all devices and collect data for the burn-in period."""
    tasks = []
    for device in devices:
        mac = device.address
        handler = lambda sender, data, m=mac: notification_handler(sender, data, m)
        task = asyncio.create_task(collect_from_device(device, handler))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

async def collect_from_device(device, handler):
    try:
        async with BleakClient(device) as client:
            if not client.is_connected: return
            logger.info(f"Connected to {device.address}")
            await client.start_notify(CORTEX_CHARACTERISTIC_UUID, handler)
            await asyncio.sleep(BURN_IN_DURATION_S)
            await client.stop_notify(CORTEX_CHARACTERISTIC_UUID)
    except Exception as e:
        logger.error(f"Error with device {device.address}: {e}")

# --- Main Logic ---
async def main():
    print("--- CORTEX Sensor Calibration Tool ---")
    print("\nStep 1: Place all your CORTEX nodes next to each other in a stable")
    print("        environment (e.g., on a table, away from windows or vents).")
    input("\nPress Enter when you are ready to begin...")

    logger.info("Scanning for CORTEX nodes...")
    devices = await BleakScanner.discover(service_uuids=[CORTEX_SERVICE_UUID], timeout=10.0)

    if not devices:
        logger.error("No nodes found! Aborting.")
        return

    logger.info(f"Found {len(devices)} nodes. Starting {BURN_IN_DURATION_S // 60}-minute data collection.")
    print("This will take a while. Please do not move the nodes.")

    # This part is simplified. A real implementation would use `run_collector`.
    # For this script, we'll just simulate the data collection.
    # await run_collector(devices)
    print("\n--- SIMULATING DATA COLLECTION ---")
    time.sleep(5) # Simulate a short wait
    # Create fake data for demonstration
    all_readings = {
        "MAC1": [{'node_id': 1, 'temp_c': 22.5, 'rh_pct': 45.1, 'lux': 150.0} for _ in range(100)],
        "MAC2": [{'node_id': 2, 'temp_c': 22.8, 'rh_pct': 44.5, 'lux': 155.0} for _ in range(100)],
        "MAC3": [{'node_id': 3, 'temp_c': 22.2, 'rh_pct': 45.8, 'lux': 148.0} for _ in range(100)],
    }
    logger.info("Data collection complete.")


    print("\n\nStep 2: Calculating offsets...")
    
    # Calculate global averages
    global_averages = {}
    for metric in METRICS_TO_CALIBRATE:
        all_values = []
        for mac in all_readings:
            all_values.extend([p[metric] for p in all_readings[mac] if p.get(metric) is not None])
        if all_values:
            global_averages[metric] = np.mean(all_values)

    print(f"\nGlobal Averages: {global_averages}")

    # Calculate per-node offsets
    offsets = {}
    for mac, readings in all_readings.items():
        if not readings: continue
        node_id = readings[0]['node_id']
        offsets[node_id] = {}
        for metric in METRICS_TO_CALIBRATE:
            node_values = [p[metric] for p in readings if p.get(metric) is not None]
            if node_values and metric in global_averages:
                node_average = np.mean(node_values)
                offset = global_averages[metric] - node_average
                offsets[node_id][metric] = round(offset, 4)

    print("\nCalculated Offsets:")
    print(json.dumps(offsets, indent=2))

    print("\nStep 3: Saving offsets...")
    # Save to JSON file
    os.makedirs(os.path.dirname(CALIBRATION_FILE_PATH), exist_ok=True)
    with open(CALIBRATION_FILE_PATH, 'w') as f:
        json.dump(offsets, f, indent=2)
    logger.info(f"Saved offsets to {CALIBRATION_FILE_PATH}")

    # Save to database
    async with aiosqlite.connect(DB_PATH) as db:
        for node_id, metrics in offsets.items():
            for metric, value in metrics.items():
                await db.execute(
                    """
                    INSERT OR REPLACE INTO calibration (node_id, metric, offset_value, last_calibrated_utc)
                    VALUES (?, ?, ?, ?)
                    """,
                    (node_id, metric, value, datetime.utcnow().isoformat() + "Z")
                )
        await db.commit()
    logger.info("Saved offsets to the database.")

    print("\n--- Calibration Complete! ---")
    print("The CORTEX hub will now apply these offsets to new readings.")


if __name__ == "__main__":
    # This script has a simplified data collection part for demonstration.
    # A full implementation would require running the bleak collector for the full duration.
    asyncio.run(main())
