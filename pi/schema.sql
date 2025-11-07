-- CORTEX Database Schema
-- SQLite 3

-- Main table for storing all sensor readings from all nodes.
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,          -- ISO8601 timestamp (e.g., '2025-11-07T10:30:00.123Z')
    mac TEXT NOT NULL,             -- MAC address of the BLE central that received the data
    node_id INTEGER NOT NULL,      -- Unique ID of the source node (0-254)
    seq INTEGER NOT NULL,          -- Packet sequence number from the node
    t_ms INTEGER NOT NULL,         -- Milliseconds since boot of the node
    temp_c REAL,                   -- Temperature (Celsius)
    rh_pct REAL,                   -- Relative Humidity (%)
    pressure_hpa REAL,             -- Barometric Pressure (hPa)
    lux REAL,                      -- Ambient Light (approximated)
    accel_g REAL,                  -- Accelerometer magnitude (g)
    sound_dbfs REAL                -- Sound level (dBFS)
);

-- Table for storing calibration offsets for each node/sensor pair.
CREATE TABLE IF NOT EXISTS calibration (
    node_id INTEGER NOT NULL,
    metric TEXT NOT NULL,          -- e.g., 'temp_c', 'rh_pct', 'lux'
    offset_value REAL NOT NULL,
    last_calibrated_utc TEXT NOT NULL,
    PRIMARY KEY (node_id, metric)
);

-- Table for storing persistent personality state.
CREATE TABLE IF NOT EXISTS personality_state (
    id INTEGER PRIMARY KEY,
    current_state TEXT NOT NULL,   -- e.g., 'Study', 'Chill', 'Sleep', 'Social'
    last_changed_utc TEXT NOT NULL
);

-- Indexes for faster querying
CREATE INDEX IF NOT EXISTS idx_readings_ts_utc ON readings (ts_utc);
CREATE INDEX IF NOT EXISTS idx_readings_node_id_seq ON readings (node_id, seq);
CREATE INDEX IF NOT EXISTS idx_calibration_node_id ON calibration (node_id);

-- Initial personality state
INSERT INTO personality_state (id, current_state, last_changed_utc)
SELECT 1, 'Chill', '1970-01-01T00:00:00Z'
WHERE NOT EXISTS (SELECT 1 FROM personality_state WHERE id = 1);
