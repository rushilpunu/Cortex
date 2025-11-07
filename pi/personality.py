# personality.py
#
# Manages the adaptive personality mode of the CORTEX hub.

import logging
from typing import Dict, Any

# --- Logging Setup ---
logger = logging.getLogger("CortexPersonality")

class Personality:
    """
    A state machine for the hub's personality.
    """
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.current_state = "Chill" # Default state
        self.state_config = {
            "Study": {"alert_sensitivity": 0.8, "theme": "Study"},
            "Chill": {"alert_sensitivity": 0.5, "theme": "Chill"},
            "Sleep": {"alert_sensitivity": 0.2, "theme": "Sleep"},
            "Social": {"alert_sensitivity": 0.9, "theme": "Social"},
        }

    async def load_state(self):
        """Loads the last known state from the database."""
        cursor = await self.db_conn.execute("SELECT current_state FROM personality_state WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            self.current_state = row[0]
        logger.info(f"Personality state loaded. Current state: {self.current_state}")

    async def set_state(self, new_state: str):
        """Sets a new state and persists it."""
        if new_state not in self.state_config:
            logger.warning(f"Attempted to set invalid personality state: {new_state}")
            return
            
        if new_state != self.current_state:
            self.current_state = new_state
            # Persist to DB
            # In a real app, you'd also record the timestamp
            await self.db_conn.execute(
                "UPDATE personality_state SET current_state = ? WHERE id = 1",
                (new_state,)
            )
            await self.db_conn.commit()
            logger.info(f"Personality state changed to: {self.current_state}")

    def get_current_properties(self) -> Dict[str, Any]:
        """Returns the properties for the current state."""
        return self.state_config.get(self.current_state, self.state_config["Chill"])

    def update(self, fused_data: Dict, occupancy_state: str):
        """
        The main update loop to decide if a state transition is needed. (Placeholder)
        
        This would contain the logic to analyze weekly patterns, time of day,
        and environmental features to automatically change the state.
        """
        # Placeholder logic
        is_night = False # Would be determined by time
        is_quiet = fused_data.get('fused_sound_dbfs', -50) < -40

        if is_night and is_quiet and self.current_state != "Sleep":
            # asyncio.create_task(self.set_state("Sleep"))
            pass # This needs to be async if called from an async context
        
        pass
