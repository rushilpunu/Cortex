# CORTEX Detailed Setup Guide

This guide provides a detailed, step-by-step walkthrough for setting up the entire CORTEX system, from flashing the sensor nodes to configuring the Raspberry Pi hub.

---

## Table of Contents

1.  [Hardware Requirements](#part-1-hardware-requirements)
2.  [Setting Up the Sensor Node (Arduino)](#part-2-setting-up-the-sensor-node-arduino)
3.  [Setting Up the Hub (Raspberry Pi)](#part-3-setting-up-the-hub-raspberry-pi)
4.  [Bringing the System Online](#part-4-bringing-the-system-online)
5.  [Verification and Calibration](#part-5-verification-and-calibration)

---

## Part 1: Hardware Requirements

Before you begin, ensure you have the following hardware:

#### Hub Components:
- **Raspberry Pi:** A Pi 4 Model B (2GB or more is recommended).
- **Display:** A 3.5" 320x480 TFT display with an **XPT2046 touch controller**. These are widely available and often connect directly to the GPIO pins.
- **Storage:** A high-quality 16GB or larger microSD card.
- **Power:** A reliable 5V, 3A USB-C power supply for the Pi.

#### Sensor Node Components:
- **Arduino:** One or more Arduino Nano 33 BLE Sense (or Rev2) boards.
- **Power:** A USB cable and a power source (e.g., computer, power bank, wall adapter) for each Arduino.

---

## Part 2: Setting Up the Sensor Node (Arduino)

You must repeat these steps for **each** Arduino board you want to use as a sensor node.

### Step 2.1: Install Arduino IDE and Libraries

1.  **Download the IDE:** Go to the [official Arduino Software page](https://www.arduino.cc/en/software) and download the Arduino IDE for your operating system.
2.  **Install Board Support:**
    - Open the Arduino IDE.
    - Navigate to `Tools > Board > Boards Manager...`.
    - In the search bar, type `Arduino Mbed OS Nano Boards`.
    - Click "Install" on the package that appears.
3.  **Install Required Libraries:**
    - Navigate to `Tools > Library Manager...`.
    - Search for and install each of the following libraries one by one:
        - `ArduinoBLE`
        - `Arduino_HTS221` (for temperature and humidity)
        - `Arduino_BARO` (for pressure)
        - `Arduino_APDS9960` (for light and proximity)
        - `Arduino_LSM9DS1` (for motion)

### Step 2.2: Configure and Upload the Firmware

1.  **Open the Sketch:**
    - In the Arduino IDE, go to `File > Open...` and navigate to the `Cortex` project folder you cloned.
    - Open the file `arduino/cortex_node/cortex_node.ino`.
2.  **Configure the Node ID:**
    - The `cortex_node.ino` sketch should open along with a tab for `config.h`. Click on the `config.h` tab.
    - **This is the most important step:** Change the `#define NODE_ID 1` line.
    - **Each node must have a unique ID.** For your first node, you can leave it as `1`. For your second, change it to `2`, and so on.
    - You can also optionally change the `LOCAL_NAME` to something more descriptive, like `"CortexNode-Window"`.
3.  **Connect and Upload:**
    - Connect your Arduino Nano 33 BLE Sense to your computer via USB.
    - In the IDE, go to `Tools > Board` and select `Arduino Nano 33 BLE`.
    - Go to `Tools > Port` and select the serial port corresponding to your Arduino.
    - Click the **Upload** button (the arrow icon in the top-left).

The IDE will compile and upload the firmware. Once complete, the small orange LED on the Arduino will light up, indicating that it is powered on and advertising its BLE service.

---

## Part 3: Setting Up the Hub (Raspberry Pi)

### Step 3.1: Prepare the Operating System

1.  **Flash Raspberry Pi OS:** Use the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash a fresh copy of **Raspberry Pi OS (64-bit)** onto your microSD card. A "Lite" version is fine if you are comfortable with the command line, but the full desktop version is also fine.
2.  **First Boot and Configuration:**
    - Insert the microSD card into your Pi and boot it up.
    - Complete the initial setup wizard (setting user, password, WiFi, etc.).
    - Open a terminal window and run `sudo raspi-config`.
    - **Enable Interfaces:**
        - Go to `3 Interface Options`.
        - Enable `I1 SPI`.
        - Enable `I2 I2C`.
    - **Set GPU Memory:**
        - Go to `1 System Options` -> `S3 Performance Options` -> `P2 GPU Memory`.
        - Enter `128` and press OK.
    - Select `Finish` and reboot when prompted.

### Step 3.2: Install System Dependencies and Code

1.  **Update System:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Install Required Packages:**
    ```bash
    sudo apt install -y python3-venv python3-pip git libopenjp2-7 libtiff5
    ```
3.  **Clone the CORTEX Repository:**
    ```bash
    cd ~
    git clone https://github.com/your-username/Cortex.git
    ```
    *(Replace `your-username` with your actual GitHub username if you forked it, otherwise use the original repo URL.)*

### Step 3.3: Install TFT Display & Touch Driver (XPT2046)

This step installs the necessary drivers for both the display and the touch controller.

1.  **Identify your screen:** While most 3.5" GPIO screens use the XPT2046 controller, it's good to confirm with the seller's documentation.
2.  **Find and run the driver installer:** Most of these screens are supported by the `LCD-show` repository.
    ```bash
    # This is an example for a common 3.5" display.
    # Your commands may vary slightly based on the manufacturer.
    git clone https://github.com/goodtft/LCD-show.git
    cd LCD-show/
    # The 'LCD35-show' script is common for 3.5" screens.
    # This script modifies boot files and installs kernel modules.
    sudo ./LCD35-show 
    ```
3.  The script will require a reboot. After rebooting, the Pi's output should appear on the TFT screen, and the touch controller should be active and emulating a mouse.

### Step 3.4: Install Python Environment and Configure CORTEX

1.  **Navigate to the `pi` directory:**
    ```bash
    cd ~/Cortex/pi
    ```
2.  **Run the automated installer:** The `Makefile` is designed to handle the Python setup for you.
    ```bash
    make install
    ```
    This command creates a virtual environment inside the `Cortex` directory (`../venv`) and installs all the necessary Python packages from `requirements.txt`.
3.  **Create Your Configuration File:**
    - Copy the sample environment file to create your own local config.
      ```bash
      cp cortex.env.sample .env
      ```
    - You can edit this file with `nano .env`. For a first run, the default settings are usually sufficient.

---

## Part 4: Bringing the System Online

### Option A: Manual Run (for Testing)

This is useful for watching the logs directly in your terminal. You'll need to open three separate terminal windows or tabs.

1.  **Terminal 1 (Hub):**
    ```bash
    cd ~/Cortex/pi
    make run-hub
    ```
    You should see logs about scanning for and connecting to your CORTEX nodes.
2.  **Terminal 2 (Web Server):**
    ```bash
    cd ~/Cortex/pi
    make run-web
    ```
    This will start the FastAPI server.
3.  **Terminal 3 (Renderer):**
    ```bash
    cd ~/Cortex/pi
    make run-renderer
    ```
    The boot animation should play on the TFT screen, followed by the main dashboard. You can now touch the screen to interact with the UI.

### Option B: Systemd Services (for Automatic Startup)

This is the recommended way to run CORTEX for daily use.

1.  **Verify Paths:** The service files assume the project is at `/home/pi/Cortex`. If you cloned it elsewhere, you **must** edit the `WorkingDirectory` and `ExecStart` paths in `cortex_hub.service`, `cortex_renderer.service`, and `cortex_web.service`.
2.  **Install and Start:**
    ```bash
    cd ~/Cortex/pi
    sudo make services-install
    sudo make services-start
    ```
3.  **Check Status:** You can verify the services are running without errors:
    ```bash
    sudo systemctl status cortex_hub.service
    sudo systemctl status cortex_web.service
    sudo systemctl status cortex_renderer.service
    ```
    Press `q` to exit the status view.

---

## Part 5: Verification and Calibration

### Step 5.1: Verify Operation

- **Check the Hub:** Look at the hub's logs (`sudo journalctl -u cortex_hub.service -f`) to see if it's discovering nodes and writing to the database.
- **Check the UI:** The TFT screen should be showing the dashboard. Tap the temperature or humidity cards to see the detail view.
- **Check the API:** From another computer on the same network, open a web browser and go to `http://<your-pi-ip>:8000/docs`. You should see the API documentation and be able to test the endpoints.

### Step 5.2: Calibrate Sensors

For best results, especially when using multiple nodes, you should calibrate them.

1.  **Co-locate Nodes:** Place all your active sensor nodes right next to each other in a stable part of the room.
2.  **Run the Tool:**
    ```bash
    cd ~/Cortex
    # Activate the virtual environment
    source venv/bin/activate
    # Run the calibration script
    python tools/calibrate.py
    ```
3.  Follow the on-screen instructions. The tool will automatically collect data for a few minutes, calculate the necessary offsets, and save them. The hub will automatically start using these new offsets for all incoming data.

**Your CORTEX system is now fully operational!**
