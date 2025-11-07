# CORTEX Development & Testing Checklist

This checklist is for verifying that all core features of the CORTEX system are implemented and working correctly.

## Phase 1: Core Bring-Up

- [ ] **Node Firmware:**
  - [ ] `cortex_node.ino` compiles and uploads to Nano 33 BLE Sense.
  - [ ] Node advertises the correct CORTEX service UUID.
  - [ ] Node can be connected to via a generic BLE scanner.
  - [ ] `CTX1` packet is received and has the correct 44-byte length.
  - [ ] Sensor values are plausible (not all zero or `NaN` unless a sensor is disconnected).
  - [ ] Node correctly resumes advertising after a disconnect.
- [ ] **Hub Service:**
  - [ ] `cortex_hub.py` starts without errors.
  - [ ] Hub discovers and connects to a CORTEX node.
  - [ ] Hub correctly parses the `CTX1` packet.
  - [ ] Live data is printed to the console.
  - [ ] Data is correctly inserted into the `cortex.db` SQLite database.
  - [ ] Hub correctly handles `NaN` values from the node.
  - [ ] Hub automatically reconnects if the node disconnects and reappears.

## Phase 2: UI & Web

- [ ] **Renderer / UI:**
  - [ ] `cortex_renderer.py` starts and opens a window.
  - [ ] Boot animation plays correctly.
  - [ ] Live dashboard displays data received from the hub via IPC.
  - [ ] AI Mood Orb color changes based on data.
  - [ ] Ambient visuals are running and react to sound/light.
  - [ ] Sparkline trend view can be toggled.
  - [ ] Auto night mode activates in low light / at the correct time.
  - [ ] E-Ink sleep screen activates when idle.
- [ ] **Web API:**
  - [ ] `cortex_web.py` starts the FastAPI server.
  - [ ] `GET /api/last` returns valid JSON with the latest sensor readings.
  - [ ] `GET /api/history` returns historical data from the database.
  - [ ] `GET /api/occupancy` returns the current occupancy state.
  - [ ] WebSocket at `/ws/stream` connects and streams live data frames.

## Phase 3: Analytics & Features

- [ ] **Calibration:**
  - [ ] `tools/calibrate.py` script runs.
  - [ ] Script guides user through co-location process.
  - [ ] Offsets are calculated and stored in `calibration.json` and the database.
  - [ ] Hub applies these offsets to incoming data.
- [ ] **Spatial Awareness:**
  - [ ] With 2+ nodes, fused "room center" values are calculated.
  - [ ] Spatial gradients are calculated and exposed via the API.
  - [ ] UI mini-map correctly displays node locations and status.
- [ ] **Occupancy:**
  - [ ] `occupancy_state` algorithm correctly identifies `vacant`, `single`, `multiple`.
  - [ ] Entry/exit events are triggered by door sensor spikes.
  - [ ] BLE sniffer data is incorporated into the occupancy logic.
- [ ] **Prediction:**
  - [ ] `forecast_linear` provides short-term predictions for temperature/CO2 proxy.
  - [ ] Time-to-threshold estimates are generated.
- [ ] **Voice (Optional):**
  - [ ] "Hey Cortex" wake word is detected.
  - [ ] Voice commands like "status" and "night mode" are correctly interpreted and acted upon.

## Phase 4: System & Deployment

- [ ] **Configuration:**
  - [ ] `.env` file is correctly read by all services.
  - [ ] Toggling services via `.env` works as expected.
- [ ] **Services:**
  - [ ] `Makefile` targets (`install`, `clean`, etc.) work correctly.
  - [ ] `systemd` services can be installed, started, and stopped.
  - [ ] Services automatically start on boot.
- [ ] **Documentation:**
  - [ ] `README.md` is complete with setup and usage instructions.
  - [ ] All hardware and wiring is documented.
  - [ ] Troubleshooting guide covers common issues.
