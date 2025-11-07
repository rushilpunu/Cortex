#ifndef CONFIG_H
#define CONFIG_H

// CORTEX Node Configuration
// -------------------------
// Set the unique ID for this node. This must be a value from 0 to 254.
// Each node in the CORTEX network must have a unique ID.
#define NODE_ID 1

// Set the local name that this node will advertise over BLE.
// This helps in identifying the node during discovery.
// The name will be truncated if it's too long for BLE advertising packets.
#define LOCAL_NAME "CortexNode-Vanity"

#endif // CONFIG_H
