# cortex_renderer.py
#
# Renders the CORTEX UI on the Raspberry Pi's 3.5" TFT display.
# - Connects to the hub's IPC server to get live data.
# - Manages different UI states (boot, dashboard, sleep, detail views).
# - Renders all visual elements using Pygame.
# - Handles touch input for an interactive experience.

import asyncio
import json
import logging
import os
import time
from collections import deque
from typing import Dict, Any, List, Callable, Optional

import pygame
from dotenv import load_dotenv

# --- Configuration Loading ---
load_dotenv()
IPC_HOST = os.getenv("IPC_HOST", "127.0.0.1")
IPC_PORT = int(os.getenv("IPC_PORT", 6789))
RENDERER_ENABLED = os.getenv("RENDERER_ENABLED", "true").lower() == "true"

# --- Constants ---
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 480
FPS = 30
HISTORY_LENGTH = 100 # Number of data points to keep for graphs

# --- Colors (will be replaced by theme loader) ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
ACCENT = (0, 150, 255)
ACCENT_DARK = (0, 80, 150)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CortexRenderer")

# --- Globals ---
last_values_cache: Dict[str, Dict[str, Any]] = {}
history_cache: Dict[str, deque] = {} # For sparklines
screen: pygame.Surface
ui_elements: List['Button'] = []

class RendererState:
    """A simple state machine for the renderer."""
    BOOT_ANIMATION = 0
    DASHBOARD = 1
    DETAIL_TEMP = 2
    DETAIL_HUMIDITY = 3
    SLEEP_SCREEN = 4

class Button:
    """A simple class for touchable UI elements."""
    def __init__(self, rect: pygame.Rect, callback: Callable, text: str = "", data_key: Optional[str] = None):
        self.rect = rect
        self.callback = callback
        self.text = text
        self.data_key = data_key # To fetch live data for display

    def handle_click(self, pos: tuple):
        if self.rect.collidepoint(pos):
            self.callback()
            return True
        return False

    def draw(self, font: pygame.font.Font, data: Optional[Dict] = None):
        # This is a simplified draw method. We'll do custom drawing in the main loop.
        pass

# --- IPC Client & Data Handling ---
async def ipc_client():
    """Connects to the hub's IPC server and updates local data caches."""
    while True:
        try:
            reader, writer = await asyncio.open_connection(IPC_HOST, IPC_PORT)
            logger.info(f"Connected to IPC server at {IPC_HOST}:{IPC_PORT}")
            
            while not reader.at_eof():
                data = await reader.readline()
                if not data: continue
                
                try:
                    packet = json.loads(data.decode('utf-8'))
                    mac = packet.get('mac')
                    if mac:
                        last_values_cache[mac] = packet
                        # Update history
                        if mac not in history_cache:
                            history_cache[mac] = deque(maxlen=HISTORY_LENGTH)
                        history_cache[mac].append(packet)
                        logger.debug(f"Received packet from {mac}, updating caches.")
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode JSON from IPC stream: {data}")

        except (ConnectionRefusedError, ConnectionResetError):
            logger.warning("IPC connection failed. Retrying in 5 seconds...")
            last_values_cache.clear()
            history_cache.clear()
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred in IPC client: {e}")
            await asyncio.sleep(5)

# --- Drawing Functions ---
def draw_text(text, font, color, x, y, center=False):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if center:
        text_rect.center = (x, y)
    else:
        text_rect.topleft = (x, y)
    screen.blit(text_surface, text_rect)

def run_boot_animation(font_large, font_small):
    # (This function remains the same as before)
    logger.info("Starting boot animation...")
    # ... [omitted for brevity, it's unchanged]
    time.sleep(2) # Simulate boot time
    logger.info("Boot animation finished.")

def draw_dashboard(font_large, font_medium, font_small):
    screen.fill(BLACK)
    
    # Top Bar
    current_time = time.strftime("%H:%M")
    draw_text(current_time, font_medium, WHITE, 10, 10)
    draw_text("CHILL", font_small, (20, 150, 100), SCREEN_WIDTH - 120, 15)

    if not last_values_cache:
        draw_text("Scanning for nodes...", font_medium, GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, center=True)
    else:
        first_node_data = next(iter(last_values_cache.values()))
        
        # Draw Metric Cards
        for btn in ui_elements:
            if btn.data_key:
                pygame.draw.rect(screen, ACCENT_DARK, btn.rect, border_radius=10)
                
                value = first_node_data.get(btn.data_key)
                unit = "°C" if "temp" in btn.data_key else "%"
                value_str = f"{value:.1f}{unit}" if value is not None else "N/A"

                draw_text(btn.text, font_medium, GRAY, btn.rect.x + 15, btn.rect.y + 15)
                draw_text(value_str, font_large, WHITE, btn.rect.x + 15, btn.rect.y + 45)
            else: # Simple button like "Sleep"
                pygame.draw.rect(screen, GRAY, btn.rect, border_radius=8)
                draw_text(btn.text, font_medium, BLACK, btn.rect.centerx, btn.rect.centery, center=True)

def draw_detail_view(font_large, font_medium, font_small, title: str, key: str, unit: str):
    screen.fill(BLACK)
    
    # Draw Back Button
    back_button = ui_elements[0] # Assuming back button is always the first in detail view
    pygame.draw.rect(screen, GRAY, back_button.rect, border_radius=8)
    draw_text(back_button.text, font_medium, BLACK, back_button.rect.centerx, back_button.rect.centery, center=True)

    draw_text(title, font_large, WHITE, SCREEN_WIDTH // 2, 30, center=True)

    if not history_cache:
        draw_text("No data yet...", font_medium, GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, center=True)
        return

    first_node_mac = next(iter(history_cache.keys()))
    data_points = [p[key] for p in history_cache[first_node_mac] if p.get(key) is not None]

    if not data_points:
        draw_text("No data for this metric...", font_medium, GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, center=True)
        return

    # Draw current value
    draw_text(f"{data_points[-1]:.1f}{unit}", font_large, WHITE, SCREEN_WIDTH // 2, 100, center=True)

    # Draw Sparkline
    graph_rect = pygame.Rect(30, 160, SCREEN_WIDTH - 60, 200)
    pygame.draw.rect(screen, ACCENT_DARK, graph_rect, border_radius=10)
    
    if len(data_points) > 1:
        min_val, max_val = min(data_points), max(data_points)
        range_val = max_val - min_val if max_val > min_val else 1.0

        points = []
        for i, val in enumerate(data_points):
            x = graph_rect.x + (i / (HISTORY_LENGTH - 1)) * graph_rect.width
            y = graph_rect.y + graph_rect.height - ((val - min_val) / range_val) * graph_rect.height
            points.append((x, y))
        
        if len(points) > 1:
            pygame.draw.lines(screen, ACCENT, False, points, 2)

# --- Main Loop ---
async def main():
    global screen, ui_elements
    if not RENDERER_ENABLED:
        logger.info("Renderer is disabled in .env file. Exiting.")
        return

    # Pygame setup
    os.environ['SDL_FBDEV'] = '/dev/fb1'
    os.environ['SDL_VIDEODRIVER'] = 'fbcon'
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.mouse.set_visible(False)

    font_large = pygame.font.Font(None, 64)
    font_medium = pygame.font.Font(None, 32)
    font_small = pygame.font.Font(None, 24)

    asyncio.create_task(ipc_client())

    state = RendererState.BOOT_ANIMATION
    
    def set_state(new_state):
        nonlocal state
        state = new_state
        # Update UI elements based on state
        ui_elements.clear()
        if new_state == RendererState.DASHBOARD:
            ui_elements.append(Button(pygame.Rect(30, 80, 260, 120), lambda: set_state(RendererState.DETAIL_TEMP), "Temperature", "temp_c"))
            ui_elements.append(Button(pygame.Rect(30, 220, 260, 120), lambda: set_state(RendererState.DETAIL_HUMIDITY), "Humidity", "rh_pct"))
            ui_elements.append(Button(pygame.Rect(30, 400, 260, 60), lambda: set_state(RendererState.SLEEP_SCREEN), "Sleep"))
        elif new_state in [RendererState.DETAIL_TEMP, RendererState.DETAIL_HUMIDITY]:
            ui_elements.append(Button(pygame.Rect(30, 400, 260, 60), lambda: set_state(RendererState.DASHBOARD), "Back"))

    set_state(RendererState.BOOT_ANIMATION)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                for element in ui_elements:
                    if element.handle_click(event.pos):
                        break # Stop after first clicked element

        if state == RendererState.BOOT_ANIMATION:
            run_boot_animation(font_large, font_small)
            set_state(RendererState.DASHBOARD)

        elif state == RendererState.DASHBOARD:
            draw_dashboard(font_large, font_medium, font_small)

        elif state == RendererState.DETAIL_TEMP:
            draw_detail_view(font_large, font_medium, font_small, "Temperature", "temp_c", "°C")

        elif state == RendererState.DETAIL_HUMIDITY:
            draw_detail_view(font_large, font_medium, font_small, "Humidity", "rh_pct", "%")

        elif state == RendererState.SLEEP_SCREEN:
            screen.fill(BLACK)
            draw_text("Sleeping...", font_large, GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, center=True)
            # Add a button to wake up
            wake_button = Button(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), lambda: set_state(RendererState.DASHBOARD))
            ui_elements = [wake_button]

        pygame.display.flip()
        await asyncio.sleep(1 / FPS)

    pygame.quit()
    logger.info("Renderer shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Renderer shutting down by user.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in renderer: {e}")
        pygame.quit()
