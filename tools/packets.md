# CORTEX BLE Packet Protocol

This document defines the structure of the BLE packet sent from a CORTEX node to the CORTEX hub.

- **Service UUID:** `6b3a0001-b5a3-f393-e0a9-e50e24dcca9e`
- **Characteristic UUID:** `6b3a0002-b5a3-f393-e0a9-e50e24dcca9e`
- **Properties:** Read, Notify
- **Total Length:** 44 bytes
- **Endianness:** Little-endian

## Packet Structure

The packet is a tightly packed C-style struct.

| Offset | Length (bytes) | Type         | Field Name     | Description                                      |
|--------|----------------|--------------|----------------|--------------------------------------------------|
| 0      | 4              | `char[4]`    | `magic`        | Magic bytes, must be "CTX1"                      |
| 4      | 1              | `uint8_t`    | `node_id`      | Unique ID of the node (0-254)                    |
| 5      | 1              | `uint8_t`    | `reserved`     | Reserved for future use, must be 0               |
| 6      | 2              | `uint16_t`   | `seq`          | Packet sequence number, increments on each send  |
| 8      | 4              | `uint32_t`   | `t_ms`         | Milliseconds since the node booted               |
| 12     | 4              | `float`      | `temp_c`       | Temperature in degrees Celsius                   |
| 16     | 4              | `float`      | `rh_pct`       | Relative Humidity in percent (%)                 |
| 20     | 4              | `float`      | `pressure_hpa` | Barometric pressure in hectopascals (hPa)        |
| 24     | 4              | `float`      | `lux`          | Ambient light level (approximated)               |
| 28     | 4              | `float`      | `accel_g`      | Magnitude of the accelerometer vector in g's     |
| 32     | 4              | `float`      | `sound_dbfs`   | Sound level in dBFS (placeholder)                |
| 36     | 8              | -            | `padding`      | Reserved for future expansion (e.g. CO2, VOC)    |

**Total: 44 bytes**

## Notes

- **NaN Values:** If a sensor fails to initialize or read, its value **must** be transmitted as `NaN` (Not a Number). The hub is responsible for handling `NaN` values correctly.
- **Validation:** The hub must validate every incoming packet by checking:
  1. The total length is exactly 44 bytes.
  2. The first 4 bytes match the magic string "CTX1".
- **Expansion:** The `reserved` bytes and the final padding are included to allow for future protocol expansion without breaking backward compatibility for simple parsers.
