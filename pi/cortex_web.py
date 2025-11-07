# cortex_web.py
#
# FastAPI web server for CORTEX.
# - Serves a REST API for historical and last-known data.
# - Provides a WebSocket for streaming live data.
# - Connects to the CORTEX Hub via a TCP socket for IPC.

import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Set

import uvicorn
import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- Configuration Loading ---
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "cortex.db")
IPC_HOST = os.getenv("IPC_HOST", "127.0.0.1")
IPC_PORT = int(os.getenv("IPC_PORT", 6789))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 8000))
ALLOW_CORS = os.getenv("ALLOW_CORS", "false").lower() == "true"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("CortexWeb")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="CORTEX API",
    description="API for the CORTEX environmental sensing hub.",
    version="1.0.0",
)

if ALLOW_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Globals ---
# In-memory cache, populated by the IPC client
last_values_cache: Dict[str, Dict[str, Any]] = {}

# --- IPC Client ---
async def ipc_client():
    """Connects to the hub's IPC server and updates the local cache."""
    while True:
        try:
            reader, writer = await asyncio.open_connection(IPC_HOST, IPC_PORT)
            logger.info(f"Connected to IPC server at {IPC_HOST}:{IPC_PORT}")
            
            while not reader.at_eof():
                data = await reader.readline()
                if not data:
                    continue
                
                try:
                    packet = json.loads(data.decode('utf-8'))
                    mac = packet.get('mac')
                    if mac:
                        last_values_cache[mac] = packet
                        logger.debug(f"Received packet from {mac}, updating cache.")
                        # Broadcast to WebSocket clients
                        await broadcast_to_websockets(packet)
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode JSON from IPC stream: {data}")

        except (ConnectionRefusedError, ConnectionResetError):
            logger.warning("IPC connection failed. Retrying in 5 seconds...")
            last_values_cache.clear() # Clear cache if hub is down
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred in IPC client: {e}")
            await asyncio.sleep(5)

# --- WebSocket Management ---
connected_websockets: Set[WebSocket] = set()

async def broadcast_to_websockets(data: Dict):
    """Broadcasts a JSON message to all connected WebSocket clients."""
    if not connected_websockets:
        return
    
    message = json.dumps(data)
    # Create a copy of the set to avoid issues with concurrent modification
    for websocket in list(connected_websockets):
        try:
            await websocket.send_text(message)
        except WebSocketDisconnect:
            # The disconnect handler will remove the socket from the set
            pass
        except Exception:
            # If sending fails for other reasons, remove the socket
            connected_websockets.remove(websocket)


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    logger.info(f"WebSocket client connected: {websocket.client}")
    try:
        while True:
            # Keep the connection alive, listening for messages (though we don't act on them)
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {websocket.client}")
    finally:
        connected_websockets.remove(websocket)


# --- API Endpoints ---
@app.get("/api/nodes")
async def get_nodes() -> List[Dict[str, Any]]:
    """Returns a list of all currently connected nodes and their last known state."""
    # The 'last_values_cache' values are the node states
    return list(last_values_cache.values())

@app.get("/api/last")
async def get_last_values() -> Dict[str, Dict[str, Any]]:
    """Returns the last known values for all nodes, keyed by MAC address."""
    return last_values_cache

@app.get("/api/history")
async def get_history(node_id: int = -1, limit: int = 100) -> List[Dict]:
    """
    Returns historical readings from the database.
    - `node_id`: Filter by a specific node ID. If -1, returns for all nodes.
    - `limit`: Maximum number of records to return.
    """
    query = "SELECT * FROM readings"
    params = []
    if node_id != -1:
        query += " WHERE node_id = ?"
        params.append(node_id)
    
    query += " ORDER BY ts_utc DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/occupancy")
async def get_occupancy() -> Dict:
    """Returns the current occupancy state. (Placeholder)"""
    # This will be fed by the analytics engine in a future step
    return {"state": "unknown", "confidence": 0.0, "source": "placeholder"}

@app.get("/api/spatial")
async def get_spatial() -> Dict:
    """Returns spatial analytics like gradients. (Placeholder)"""
    return {"fused_center": {}, "gradients": [], "source": "placeholder"}

@app.on_event("startup")
async def startup_event():
    """Tasks to run when the server starts."""
    asyncio.create_task(ipc_client())
    logger.info("Web server startup complete.")

# --- Main Entry ---
if __name__ == "__main__":
    logger.info(f"Starting CORTEX Web Server on {WEB_HOST}:{WEB_PORT}")
    uvicorn.run(
        "cortex_web:app",
        host=WEB_HOST,
        port=WEB_PORT,
        log_level="info",
        reload=False # Important for production
    )
