# CORTEX: A Local-First Environmental Intelligence Hub

CORTEX is a dorm-room-scale environmental sensing platform that runs entirely on a Raspberry Pi. It ingests data from one or more wireless sensor nodes, performs all analytics and predictions locally, and presents the insights through a rich physical display and a local web interface.

**The core principle of CORTEX is that all data processing and intelligence runs on-device.** No cloud services are required for any of its primary features, from occupancy detection to trend forecasting.

![CORTEX Diagram](https://i.imgur.com/your-diagram-image.png) <!-- Placeholder for a diagram -->

## Features

- **Local-First Analytics:** All sensor fusion, occupancy detection, anomaly detection, and trend prediction happens on the Raspberry Pi.
- **Wireless Sensor Nodes:** Uses Arduino Nano 33 BLE Sense boards to create a mesh-ready network of sensors.
- **Rich Interactive UI:** A 320x480 TFT touchscreen provides a high-fidelity dashboard with tappable metric cards, historical graphs, and spatial awareness visualizations.
- **Web & WebSocket API:** A LAN-only web interface provides access to live and historical data, with a WebSocket for real-time streaming.
- **Adaptive Personality:** The system's "mood" (e.g., Study, Chill, Sleep) adapts to environmental patterns, changing UI themes and alert sensitivity.
- **Redundancy & Calibration:** Built-in tools to calibrate sensors and automatically handle node dropouts.
- **Optional Voice Control:** A fully local "Hey Cortex" wake-word and command system (off by default).

---

## Hardware Requirements

### Hub

- **Raspberry Pi:** A Pi 4 Model B (2GB or more) is recommended for running the full stack (hub, renderer, web).
- **Display:** A 3.5" 320x480 TFT display with an **XPT2046 touch controller**. These are widely available and often connect directly to the GPIO pins.
- **Storage:** A high-quality 16GB+ microSD card.
- **Power Supply:** A reliable USB-C power supply (5V, 3A).

### Sensor Node(s)

- **Arduino:** One or more Arduino Nano 33 BLE Sense or Nano 33 BLE Sense Rev2 boards.
- **Power:** A way to power the Arduinos (e.g., USB power bank, wall adapter).

---

## Setup

### 1. Arduino Sensor Node

For each Arduino node you want to create:

1.  **Install Arduino IDE:** Download and install the [Arduino IDE](https://www.arduino.cc/en/software).
2.  **Install Board & Libraries:**
    - Open the IDE and go to `Tools > Board > Boards Manager...`.
    - Search for "Arduino Mbed OS Nano Boards" and install it.
    - Go to `Tools > Library Manager...` and install the following libraries:
        - `ArduinoBLE`
        - `Arduino_HTS221`
        - `Arduino_BARO`
        - `Arduino_APDS9960`
        - `Arduino_LSM9DS1`
3.  **Configure the Node:**
    - Open the `arduino/cortex_node/cortex_node.ino` sketch in the IDE.
    - Open the `config.h` file in a separate tab.
    - **Crucially, change `NODE_ID` to a unique number (1, 2, 3, etc.) for each node you program.**
    - You can also change `LOCAL_NAME` to something descriptive (e.g., "CortexNode-Desk").
4.  **Upload the Sketch:**
    - Connect the Arduino to your computer.
    - Select the correct board (`Arduino Nano 33 BLE`) and Port under the `Tools` menu.
    - Click the "Upload" button.

Once uploaded, the node will immediately start advertising as a CORTEX device.

### 2. Raspberry Pi Hub

1.  **Flash OS:** Flash a fresh installation of Raspberry Pi OS (64-bit recommended) onto your microSD card.
2.  **System Configuration:**
    - Run `sudo raspi-config`.
    - Go to `Interface Options` and enable `SPI` and `I2C`.
    - Go to `Advanced Options` and set GPU memory to 128MB.
    - Finish and reboot.
3.  **Install Dependencies:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3-venv python3-pip git libopenjp2-7 libtiff5
    ```
4.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/Cortex.git
    cd Cortex
    ```
5.  **Set up Python Environment:**
    - The provided `Makefile` handles this automatically.
    ```bash
    make -C pi install
    ```
    This will create a virtual environment (`venv`) and install all required Python packages.
6.  **Configure CORTEX:**
    - Copy the sample environment file:
      ```bash
      cp pi/cortex.env.sample pi/.env
      ```
    - Edit `pi/.env` to your needs. For a first run, the defaults are usually fine.
7.  **TFT Display & Touch Driver (XPT2046):**
    - Most screens with an XPT2046 controller are supported by the open-source `LCD-show` driver repository. This process installs the kernel modules for both the display and the touch input.
      ```bash
      # Example for a common 3.5" display. Your commands may vary slightly.
      git clone https://github.com/goodtft/LCD-show.git
      cd LCD-show/
      # The exact script depends on your screen model. This is a common one.
      sudo ./LCD35-show 
      ```
    - **Follow the manufacturer's instructions carefully.** After running the script and rebooting, the Pi will use the TFT as its primary display, and touch input will be mapped to behave like a standard mouse.

---

## Usage

### Running the Services

The easiest way to run the CORTEX services is using the `Makefile`.

- **To run the hub manually (for debugging):**
  ```bash
  make -C pi run-hub
  ```
- **To run the renderer manually:**
  ```bash
  make -C pi run-renderer
  ```
- **To run the web server manually:**
  ```bash
  make -C pi run-web
  ```

### Systemd Services (Recommended)

For the hub to run automatically on boot, install the provided `systemd` services.

**Important:** The service files assume the project is located at `/home/pi/Cortex`. If you cloned it elsewhere, you **must** edit the `WorkingDirectory` and `ExecStart` paths in all `*.service` files inside the `pi/` directory.

```bash
# From within the Cortex/pi directory
sudo make services-install
sudo make services-start
```

You can check the status of a service with `sudo systemctl status cortex_hub.service`.

### Sensor Calibration

For the most accurate readings, you should calibrate your sensors.

1.  Place all nodes close together in a stable environment.
2.  Run the calibration tool:
    ```bash
    # Activate the virtual environment first
    source venv/bin/activate
    python tools/calibrate.py
    ```
3.  Follow the on-screen instructions. The tool will automatically collect data, calculate offsets, and save them for the hub to use.

### Accessing the Web UI

- **API:** `http://<your-pi-ip>:8000/api/last`
- **API Docs:** `http://<your-pi-ip>:8000/docs`
- **WebSocket:** `ws://<your-pi-ip>:8000/ws/stream`

---

## Troubleshooting

- **BLE Connection Issues:**
  - Ensure the `bluetooth` service is running (`sudo systemctl status bluetooth`).
  - Check the hub's logs for RSSI values. If a node is too far away, it may be ignored. You can adjust `MIN_RSSI` in the `.env` file.
  - Use the `tools/test_ble.py` script to independently verify that a node is advertising and sending data correctly.

- **TFT Display or Touch Not Working:**
  - Double-check that you ran the correct driver installation script for your specific screen model (e.g., `LCD35-show`).
  - After the driver install and reboot, run `ls /dev/input/event*`. You should see one or more event devices. One of them is your touchscreen. If not, the driver did not install correctly.
  - Ensure the `DISPLAY` environment variable is set correctly if running manually (`export DISPLAY=:0`). The `cortex_renderer.service` file handles this automatically.

- **"Packet size" warnings in hub log:**
  - This can indicate a BLE transmission issue or a mismatch between the Arduino firmware and the hub's parser. Ensure `PACKET_SIZE` in `cortex_hub.py` matches the struct size in `cortex_node.ino`.