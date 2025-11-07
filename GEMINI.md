# CORTEX Project Overview for Gemini

This document provides a comprehensive overview of the CORTEX project, intended to serve as instructional context for future interactions with the Gemini CLI.

## 1. Project Overview

CORTEX is a local-first environmental intelligence platform designed for Raspberry Pi. It integrates wireless sensor nodes (Arduino Nano 33 BLE Sense) to collect environmental data, performs all analytics and predictions locally on the Raspberry Pi, and presents insights via a physical TFT display and a local web interface. The core principle is on-device data processing, requiring no cloud services for its primary features.

**Key Components:**

*   **CORTEX Hub (Raspberry Pi):** Written in Python, this is the central processing unit. It handles BLE discovery and connection to nodes, data ingestion and parsing, database writing (SQLite), inter-process communication (IPC) for live data, and runs core analytics routines (sensor fusion, occupancy detection, prediction, personality adaptation).
*   **CORTEX Sensor Nodes (Arduino):** Written in C++, these are low-power BLE devices that collect environmental data (temperature, humidity, pressure, light, acceleration, sound) and transmit it wirelessly to the CORTEX Hub. Each node requires a unique ID.
*   **CORTEX Renderer (Raspberry Pi):** A Python application that drives the physical 3.5" 320x480 TFT touchscreen display, providing a rich interactive UI with dashboards, historical graphs, and spatial awareness visualizations.
*   **CORTEX Web (Raspberry Pi):** A Python FastAPI application providing a LAN-only web interface for live and historical data, including a WebSocket for real-time streaming.
*   **Assets:** JSON files for boot animations, quotes, and UI themes.

**Main Technologies:**

*   **Python 3:** For the Raspberry Pi hub, renderer, and web services. Utilizes `asyncio`, `bleak`, `aiosqlite`, `FastAPI`, `uvicorn`, `Pillow`, `smbus`, `spidev`, `RPi.GPIO`, `pygame`, `numpy`, `scipy`, `scikit-learn`.
*   **C++ (Arduino):** For the sensor node firmware. Utilizes `ArduinoBLE`, `Arduino_HTS221`, `Arduino_BARO`, `Arduino_APDS9960`, `Arduino_LSM9DS1` libraries.
*   **SQLite:** For local data storage on the Raspberry Pi.
*   **BLE (Bluetooth Low Energy):** For communication between the Raspberry Pi hub and Arduino sensor nodes.
*   **Systemd:** For managing and running the Raspberry Pi services automatically on boot.
*   **Makefile:** For automating common development and deployment tasks.

## 2. Building and Running

### 2.1. Arduino Sensor Nodes Setup

For each Arduino Nano 33 BLE Sense board:

1.  **Install Arduino IDE and Libraries:**
    *   Download and install the [Arduino IDE](https://www.arduino.cc/en/software).
    *   Install "Arduino Mbed OS Nano Boards" via `Tools > Board > Boards Manager...`.
    *   Install `ArduinoBLE`, `Arduino_HTS221`, `Arduino_BARO`, `Arduino_APDS9960`, `Arduino_LSM9DS1` via `Tools > Library Manager...`.
2.  **Configure and Upload Firmware:**
    *   Open `arduino/cortex_node/cortex_node.ino` in the IDE.
    *   **Crucially, edit `config.h` to set a unique `NODE_ID` (e.g., 1, 2, 3) for each board.** Optionally change `LOCAL_NAME`.
    *   Connect the Arduino, select the correct board and port, then upload the sketch.

### 2.2. Raspberry Pi Hub Setup

1.  **Flash OS:** Flash Raspberry Pi OS (64-bit recommended) onto a microSD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2.  **System Configuration:**
    *   Run `sudo raspi-config`.
    *   Enable `SPI` and `I2C` under `Interface Options`.
    *   Set GPU memory to `128MB` under `Advanced Options`.
    *   Reboot.
3.  **Install System Dependencies:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3-venv python3-pip git libopenjp2-7 libtiff5
    ```
4.  **Clone the Repository:**
    ```bash
    cd ~
    git clone https://github.com/your-username/Cortex.git # Adjust URL if forked
    cd Cortex
    ```
5.  **TFT Display & Touch Driver (XPT2046):**
    *   Follow your screen manufacturer's instructions. Typically involves cloning `https://github.com/goodtft/LCD-show.git` and running a script like `sudo ./LCD35-show`. Reboot after installation.
6.  **Python Environment Setup:**
    *   Navigate to the `pi` directory: `cd pi`
    *   Run `make install`. This creates a Python virtual environment (`venv`) and installs all `requirements.txt` dependencies.
7.  **Configure CORTEX:**
    *   Copy the sample environment file: `cp cortex.env.sample .env`
    *   Edit `pi/.env` to customize settings (e.g., `CORTEX_SERVICE_UUID`, `DB_PATH`, `MIN_RSSI`, `IPC_HOST`, `IPC_PORT`).

### 2.3. Running the Services

#### Manual Run (for Testing/Debugging)

Open three separate terminal windows/tabs, navigate to `~/Cortex/pi` in each, and run:

*   **Hub:** `make run-hub`
*   **Web Server:** `make run-web`
*   **Renderer:** `make run-renderer`

#### Systemd Services (Recommended for Automatic Startup)

1.  **Important:** If the project is not located at `/home/pi/Cortex`, you **must** edit the `WorkingDirectory` and `ExecStart` paths in `cortex_hub.service`, `cortex_renderer.service`, and `cortex_web.service` files located in the `pi/` directory.
2.  **Install and Start:**
    ```bash
    cd ~/Cortex/pi
    sudo make services-install
    sudo make services-start
    ```
3.  **Check Status:** `sudo systemctl status cortex_hub.service`, `sudo systemctl status cortex_web.service`, `sudo systemctl status cortex_renderer.service`.

### 2.4. Sensor Calibration

For accurate readings, especially with multiple nodes:

1.  Place all active nodes close together.
2.  From `~/Cortex`, activate the virtual environment (`source venv/bin/activate`).
3.  Run the calibration tool: `python tools/calibrate.py`. Follow on-screen instructions.

### 2.5. Accessing the Web UI

Once `cortex_web.service` is running, access the web interface from a browser on the same LAN:

*   **API:** `http://<your-pi-ip>:8000/api/last`
*   **API Docs:** `http://<your-pi-ip>:8000/docs`
*   **WebSocket:** `ws://<your-pi-ip>:8000/ws/stream`

## 3. Development Conventions

*   **Python Virtual Environment:** The project uses a `venv` for Python dependencies, managed by the `Makefile`.
*   **Makefile for Automation:** Common tasks like `install`, `run-hub`, `run-web`, `run-renderer`, `services-install`, `services-start` are defined in the `Makefile` in the `pi/` directory.
*   **Systemd for Deployment:** Services are designed to run as `systemd` units for automatic startup and management on the Raspberry Pi.
*   **BLE Packet Format:** A specific `PACKET_FORMAT` (defined in `pi/cortex_hub.py`) is used for BLE communication, corresponding to a struct in the Arduino firmware. Consistency between `cortex_hub.py` and `cortex_node.ino` is crucial.
*   **Configuration:** Environment variables, loaded from `pi/.env` (which is copied from `cortex.env.sample`), are used for configuration.
*   **Logging:** Standard Python `logging` module is used with `INFO` level by default.
*   **Asynchronous Programming:** Python components heavily utilize `asyncio` for concurrent operations (BLE, IPC, web server).
*   **Database Schema:** `pi/schema.sql` defines the SQLite database structure.
*   **Analytics Modules:** `algorithms.py`, `predictor.py`, `personality.py` contain the core logic for data processing and intelligence.
*   **Assets:** UI elements, boot animations, and textual content are stored in JSON files under the `assets/` directory.
