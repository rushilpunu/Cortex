/*
  CORTEX Node
  ===========
  Firmware for the Arduino Nano 33 BLE Sense (or Rev2).

  - Samples all on-board sensors at 10 Hz.
  - Transmits a custom data packet over a BLE Notify characteristic at 5 Hz.
  - Follows the CORTEX BLE protocol.
  - Re-establishes advertising on disconnect.
  - Handles sensor initialization failures gracefully by sending NaN.
*/

#include "config.h"
#include <ArduinoBLE.h>
#include <Arduino_HTS221.h>    // Temperature & Humidity
#include <Arduino_LPS22HB.h>
#include <Arduino_APDS9960.h>  // Proximity, Light, Color, Gesture
#include <Arduino_LSM9DS1.h>   // 9-axis IMU (Accelerometer, Gyro, Magnetometer)
// Note: PDM library for microphone is not included by default to keep it simple.
// Sound level must be calculated from the PDM microphone if needed.

// --- CORTEX BLE Protocol Definition ---
#define CORTEX_SERVICE_UUID         "6b3a0001-b5a3-f393-e0a9-e50e24dcca9e"
#define CORTEX_CHARACTERISTIC_UUID  "6b3a0002-b5a3-f393-e0a9-e50e24dcca9e"

// Packet structure (44 bytes)
typedef struct __attribute__((packed)) {
  char    magic[4];       // "CTX1"
  uint8_t node_id;        // From config.h
  uint8_t reserved;       // 0
  uint16_t seq;           // Sequence number
  uint32_t t_ms;          // Milliseconds since boot
  float   temp_c;         // Temperature (Celsius)
  float   rh_pct;         // Relative Humidity (%)
  float   pressure_hpa;   // Pressure (hPa)
  float   lux;            // Ambient light (lux) - approximated
  float   accel_g;        // Accelerometer magnitude (g)
  float   sound_dbfs;     // Sound level (dBFS) - placeholder
} CortexPacket;

CortexPacket packet;

// --- BLE Service and Characteristic ---
BLEService cortexService(CORTEX_SERVICE_UUID);
BLECharacteristic cortexCharacteristic(CORTEX_CHARACTERISTIC_UUID, BLERead | BLENotify, sizeof(packet));

// --- Sensor State Flags ---
bool hts_ok = false;
bool baro_ok = false;
bool apds_ok = false;
bool lsm_ok = false;

// --- Timing ---
const unsigned long sampleInterval = 100; // 10 Hz
const unsigned long notifyInterval = 200; // 5 Hz
unsigned long lastSampleTime = 0;
unsigned long lastNotifyTime = 0;

// --- Function Prototypes ---
void setupSensors();
void readSensors();
void updateAndNotify();
void onBLEConnected(BLEDevice central);
void onBLEDisconnected(BLEDevice central);

void setup() {
  Serial.begin(115200);
  // while (!Serial); // Uncomment for debugging to wait for serial connection

  Serial.println("CORTEX Node Booting...");
  Serial.print("Node ID: "); Serial.println(NODE_ID);
  Serial.print("Local Name: "); Serial.println(LOCAL_NAME);

  setupSensors();

  // Initialize packet structure
  memcpy(packet.magic, "CTX1", 4);
  packet.node_id = NODE_ID;
  packet.reserved = 0;
  packet.seq = 0;

  // Setup BLE
  if (!BLE.begin()) {
    Serial.println("Starting BLE failed!");
    while (1); // Halt
  }

  BLE.setLocalName(LOCAL_NAME);
  BLE.setAdvertisedService(cortexService);
  cortexService.addCharacteristic(cortexCharacteristic);
  BLE.addService(cortexService);

  // Set initial value
  cortexCharacteristic.writeValue(&packet, sizeof(packet));

  // Assign event handlers
  BLE.setEventHandler(BLEConnected, onBLEConnected);
  BLE.setEventHandler(BLEDisconnected, onBLEDisconnected);

  // Start advertising
  BLE.advertise();
  Serial.println("BLE Advertising started.");
  
  // Turn on the built-in LED to indicate advertising
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); 
}

void loop() {
  unsigned long currentTime = millis();

  // Poll for BLE events
  BLE.poll();

  // Sample sensors at 10 Hz
  if (currentTime - lastSampleTime >= sampleInterval) {
    lastSampleTime = currentTime;
    readSensors();
  }

  // Notify central at 5 Hz if connected
  if (currentTime - lastNotifyTime >= notifyInterval) {
    lastNotifyTime = currentTime;
    if (BLE.connected()) {
      updateAndNotify();
    }
  }
}

void setupSensors() {
  Serial.println("Initializing sensors...");
  if (HTS.begin()) {
    Serial.println("HTS221 (Temp/Humidity) OK");
    hts_ok = true;
  } else {
    Serial.println("Failed to initialize HTS221!");
  }

  if (BARO.begin()) {
    Serial.println("LPS22HB (Pressure) OK");
    baro_ok = true;
  } else {
    Serial.println("Failed to initialize LPS22HB!");
  }

  if (APDS.begin()) {
    Serial.println("APDS9960 (Light/Prox) OK");
    apds_ok = true;
  } else {
    Serial.println("Failed to initialize APDS9960!");
  }

  if (IMU.begin()) {
    Serial.println("LSM9DS1 (IMU) OK");
    lsm_ok = true;
  } else {
    Serial.println("Failed to initialize LSM9DS1!");
  }
  Serial.println("Sensor initialization complete.");
}

void readSensors() {
  // Temperature and Humidity
  packet.temp_c = hts_ok ? HTS.readTemperature() : NAN;
  packet.rh_pct = hts_ok ? HTS.readHumidity() : NAN;

  // Pressure
  packet.pressure_hpa = baro_ok ? BARO.readPressure() : NAN;

  // Light
  int r, g, b, a;
  if (apds_ok && APDS.colorAvailable()) {
    APDS.readColor(r, g, b, a);
    // Simple approximation of lux from ambient value
    packet.lux = a; 
  } else {
    packet.lux = NAN;
  }

  // Accelerometer
  float ax, ay, az;
  if (lsm_ok && IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);
    packet.accel_g = sqrt(ax*ax + ay*ay + az*az);
  } else {
    packet.accel_g = NAN;
  }

  // Sound - Placeholder
  // Reading the microphone requires the PDM library and more complex handling.
  // For now, we send NaN.
  packet.sound_dbfs = NAN;
}

void updateAndNotify() {
  packet.t_ms = millis();
  packet.seq++;
  
  // Update the characteristic value
  cortexCharacteristic.writeValue(&packet, sizeof(packet));
  
  // The BLE stack will handle the notification if the central has subscribed.
}

void onBLEConnected(BLEDevice central) {
  Serial.print("Connected to central: ");
  Serial.println(central.address());
  // Turn off the advertising LED, turn on a "connected" LED if available
  digitalWrite(LED_BUILTIN, LOW); 
}

void onBLEDisconnected(BLEDevice central) {
  Serial.print("Disconnected from central: ");
  Serial.println(central.address());
  
  // Turn the advertising LED back on
  digitalWrite(LED_BUILTIN, HIGH);

  // Restart advertising
  BLE.advertise();
  Serial.println("Advertising restarted.");
}
