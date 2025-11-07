.PHONY: help install clean services-install services-start services-stop services-restart

# Default target
help:
	@echo "CORTEX Pi Makefile"
	@echo "------------------"
	@echo "Targets:"
	@echo "  install          - Create virtualenv and install dependencies"
	@echo "  run-hub          - Run the main CORTEX hub process"
	@echo "  run-renderer     - Run the UI renderer process"
	@echo "  run-web          - Run the web API process"
	@echo "  clean            - Remove virtualenv and __pycache__"
	@echo "  services-install - Install and enable systemd services"
	@echo "  services-start   - Start all CORTEX services"
	@echo "  services-stop    - Stop all CORTEX services"
	@echo "  services-restart - Restart all CORTEX services"

# Assumes python3 is available
VENV_DIR = ../venv
PYTHON = $(VENV_DIR)/bin/python

install: $(VENV_DIR)/bin/activate

$(VENV_DIR)/bin/activate: requirements.txt
	test -d $(VENV_DIR) || python3 -m venv $(VENV_DIR)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Virtualenv created and dependencies installed."

run-hub:
	@$(PYTHON) cortex_hub.py

run-renderer:
	@$(PYTHON) cortex_renderer.py

run-web:
	@$(PYTHON) cortex_web.py

clean:
	@rm -rf $(VENV_DIR)
	@find . -type d -name "__pycache__" -exec rm -r {} +
	@echo "Cleaned up virtualenv and cache files."

# --- Systemd Service Management ---
# Note: These commands require sudo privileges.
SERVICES = cortex_hub.service cortex_renderer.service cortex_web.service

services-install:
	@echo "Installing systemd services..."
	@sudo cp $(SERVICES) /etc/systemd/system/
	@sudo systemctl daemon-reload
	@sudo systemctl enable $(SERVICES)
	@echo "Services installed and enabled. Use 'sudo systemctl start \$$service_name' to start."

services-start:
	@echo "Starting all CORTEX services..."
	@sudo systemctl start $(SERVICES)

services-stop:
	@echo "Stopping all CORTEX services..."
	@sudo systemctl stop $(SERVICES)

services-restart:
	@echo "Restarting all CORTEX services..."
	@sudo systemctl restart $(SERVICES)
