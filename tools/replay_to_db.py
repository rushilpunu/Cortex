# replay_to_db.py
#
# A utility to read a log file containing raw CORTEX packets (e.g., from
# a test run) and insert them into the database. This is useful for
# developing and testing analytics without a live node.

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
import aiosqlite

# --- Configuration ---
DB_PATH = "../pi/cortex.db"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ReplayTool")

# This is a simplified version of the hub's parsing logic
PACKET_FORMAT = "<4sB_BHffff_f"
PACKET_KEYS = [
    "magic", "node_id", "seq", "t_ms", "temp_c", "rh_pct",
    "pressure_hpa", "lux", "accel_g", "sound_dbfs"
]

async def replay(log_file: str, mac: str):
    """Reads the log file and inserts data into the database."""
    logger.info(f"Replaying packets from '{log_file}' into '{DB_PATH}'")
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.error(f"Log file not found: {log_file}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        packets_replayed = 0
        start_time = datetime.utcnow()

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            try:
                # Assuming the log file contains hex strings of the packets
                data = bytes.fromhex(line)
                
                # This is a simplified parser, assuming valid packets
                values = struct.unpack(PACKET_FORMAT, data[:struct.calcsize(PACKET_FORMAT)])
                packet = dict(zip(PACKET_KEYS, values))

                if packet["magic"] != b'CTX1':
                    logger.warning(f"Skipping line {i+1}: invalid magic bytes")
                    continue

                # Create a realistic timestamp
                ts_utc = (start_time + timedelta(milliseconds=i * 200)).isoformat() + "Z"

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
                packets_replayed += 1

            except (ValueError, struct.error) as e:
                logger.warning(f"Skipping line {i+1}: could not parse packet. Error: {e}")
        
        await db.commit()
        logger.info(f"Replay complete. Inserted {packets_replayed} packets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay CORTEX packet logs to the database.")
    parser.add_argument("logfile", help="Path to the log file containing hex-encoded packets, one per line.")
    parser.add_argument("--mac", default="00:11:22:33:44:55", help="A fake MAC address to use for the replayed node.")
    
    args = parser.parse_args()

    asyncio.run(replay(args.logfile, args.mac))
