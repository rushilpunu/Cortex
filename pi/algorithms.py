# algorithms.py
#
# Core analytics functions for the CORTEX system.
# These functions are designed to be called by the hub and operate on
# the live data stream or historical data.

import logging
from typing import Dict, List, Any, Tuple

import numpy as np

# --- Logging Setup ---
logger = logging.getLogger("CortexAlgorithms")

# --- Globals ---
# In-memory store for calibration data (loaded from DB at startup)
calibration_offsets: Dict[int, Dict[str, float]] = {}

# --- Redundancy & Calibration ---

def load_calibration_offsets(offsets: List[Dict]):
    """
    Loads calibration offsets from the database into memory.
    Expected format: [{'node_id': 1, 'metric': 'temp_c', 'offset_value': -0.5}, ...]
    """
    global calibration_offsets
    calibration_offsets.clear()
    for item in offsets:
        node_id = item['node_id']
        if node_id not in calibration_offsets:
            calibration_offsets[node_id] = {}
        calibration_offsets[node_id][item['metric']] = item['offset_value']
    logger.info(f"Loaded calibration offsets for {len(calibration_offsets)} nodes.")

def apply_calibration(packet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies pre-calculated calibration offsets to a data packet.
    This should be called at the point of ingest in the hub.
    """
    node_id = packet.get('node_id')
    if not node_id or node_id not in calibration_offsets:
        return packet

    for metric, offset in calibration_offsets[node_id].items():
        if metric in packet and packet[metric] is not None:
            packet[metric] += offset
            
    return packet

def calibrate_offsets(data: List[Dict]) -> Dict[int, Dict[str, float]]:
    """
    Calculates sensor offsets based on co-located data. (Placeholder)
    
    Args:
        data: A list of data packets from a co-location "burn-in" period.
    
    Returns:
        A dictionary of offsets, e.g., {1: {'temp_c': -0.2}, 2: {'temp_c': 0.1}}
    """
    logger.info("Running offset calibration (placeholder)...")
    # In a real implementation, this would average all nodes and then find
    # the deviation of each node from that average.
    return {1: {'temp_c': 0.0}}


# --- Spatial Awareness ---

def fuse_spatial(nodes_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Fuses sensor values from multiple nodes into a single "room center" estimate.
    
    Args:
        nodes_data: A list of the latest data packets from all active nodes.
        
    Returns:
        A dictionary of fused values, e.g., {'fused_temp_c': 22.5}
    """
    fused = {}
    metrics_to_fuse = ['temp_c', 'rh_pct', 'pressure_hpa', 'lux']
    
    for metric in metrics_to_fuse:
        valid_values = [d[metric] for d in nodes_data if d.get(metric) is not None]
        if valid_values:
            # Using median for robustness against outliers
            fused[f'fused_{metric}'] = np.median(valid_values)
            
    return fused

def spatial_gradient(nodes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates the gradient of metrics across the room. (Placeholder)
    
    Returns:
        A dictionary describing the most significant gradients.
    """
    if len(nodes_data) < 2:
        return {"significant_gradients": []}
        
    # Placeholder logic: just find the min/max temperature
    temps = [(d.get('node_id', 'N/A'), d.get('temp_c')) for d in nodes_data if d.get('temp_c') is not None]
    if not temps:
        return {"significant_gradients": []}

    min_node = min(temps, key=lambda x: x[1])
    max_node = max(temps, key=lambda x: x[1])

    if max_node[1] - min_node[1] > 1.0: # Threshold of 1.0 C
        return {
            "significant_gradients": [{
                "metric": "temp_c",
                "magnitude": max_node[1] - min_node[1],
                "from_node": min_node[0],
                "to_node": max_node[0]
            }]
        }
    return {"significant_gradients": []}


# --- Occupancy Detection ---

def occupancy_state(nodes_data: List[Dict[str, Any]], ble_device_count: int) -> Dict[str, Any]:
    """
    Determines room occupancy state using sensor data. (Placeholder)
    
    This is a placeholder for a more complex rules engine or ML model.
    """
    # Simple rule: if any node has high motion, assume occupied.
    motion_threshold = 1.2 # g
    is_motion = any(d.get('accel_g', 0) > motion_threshold for d in nodes_data)
    
    if is_motion or ble_device_count > 3:
        return {"state": "single", "confidence": 0.6, "source": "rules_v1"}
    else:
        return {"state": "vacant", "confidence": 0.8, "source": "rules_v1"}


# --- Anomaly Detection ---

def detect_spikes(new_value: float, historical_data: List[float], threshold: float = 3.5) -> bool:
    """
    Detects if a new value is a spike compared to historical data using MAD.
    
    Args:
        new_value: The new data point.
        historical_data: A list or numpy array of recent historical values.
        threshold: The number of median absolute deviations for a spike.
        
    Returns:
        True if the value is a spike, False otherwise.
    """
    if not historical_data:
        return False
        
    median = np.median(historical_data)
    mad = np.median([abs(y - median) for y in historical_data])
    
    if mad == 0: # Avoid division by zero
        return new_value != median

    modified_z_score = 0.6745 * (new_value - median) / mad
    
    return abs(modified_z_score) > threshold
