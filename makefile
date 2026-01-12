# Makefile for Futaba RC Driver
VENV_DIR := $(shell pwd)/.venv
VENV_ACTIVATE := . $(VENV_DIR)/bin/activate

# Check if venv exists
ifeq (,$(wildcard $(VENV_DIR)/bin/activate))
    $(error Virtual environment not found at $(VENV_DIR). Create it with: python3 -m venv .venv)
endif

PYTHON := python3
PIP := pip3

PYPROJECT := pyproject.toml
EXECUTABLE_NAME := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['tool']['build_tool']['executable_name'])")
BUILD_DIR := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['tool']['build_tool']['build_dir'])")
PACKAGE_DIR := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['tool']['build_tool']['package_dir'])")
INSTALL_DIR := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['tool']['build_tool']['install_dir'])")
BIN_DIR := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['tool']['build_tool']['bin_dir'])")
VERSION := $(shell $(VENV_ACTIVATE) && $(PYTHON) -c "import tomllib; f=open('$(PYPROJECT)','rb'); d=tomllib.load(f); print(d['project']['version'])")

# Source files and dependencies
SOURCE_MAIN := src/main.py
SOURCES := $(shell find src -name '*.py' 2>/dev/null)
BUILD_TOOLS := tools/build.py tools/package.py tools/clean.py tools/util.py tools/__config__.py


EXECUTABLE := $(BUILD_DIR)/$(EXECUTABLE_NAME)


.PHONY: help all build stubs package install uninstall test clean clean-build clean-package clean-pycache clean-logs


help:
	@echo "Futaba RC Driver - Build System"
	@echo "================================"
	@echo ""
	@echo "Available targets:"
	@echo "  make build          - Build executable with Nuitka"
	@echo "  make package        - Create distribution package"
	@echo "  make all            - Build and package (build + package)"
	@echo "  make install        - Install the built executable to system"
	@echo "  make uninstall      - Remove installed executable from system"
	@echo "  make test           - Test the built executable"
	@echo "  make clean          - Remove all build artifacts"
	@echo "  make clean-build    - Remove build artifacts only"
	@echo "  make clean-package  - Remove package artifacts only"
	@echo "  make clean-pycache  - Remove Python cache files"
	@echo "  make clean-logs     - Remove log files"
	@echo ""
	@echo "Current configuration:"
	@echo "  Executable: $(EXECUTABLE_NAME)"
	@echo "  Version: $(VERSION)"
	@echo "  Build dir: $(BUILD_DIR)"
	@echo "  Package dir: $(PACKAGE_DIR)"

all: build package

$(EXECUTABLE): $(SOURCES) $(PYPROJECT) $(BUILD_TOOLS)
	@echo "Source files changed, rebuilding..."
	$(VENV_ACTIVATE) && tools/build.py

build: $(EXECUTABLE)

stubs:
	@echo "Generating type stubs..."
	$(VENV_ACTIVATE) && tools/build.py --type-stubs

test: $(EXECUTABLE)
	@echo "Testing executable..."
	@$(EXECUTABLE) --version

package: build
	@echo "Creating distribution package..."
	$(VENV_ACTIVATE) && tools/package.py

install: build
	@echo "Installing $(EXECUTABLE_NAME)..."
	@if [ -f "$(BUILD_DIR)/install.sh" ]; then \
		cd $(BUILD_DIR) && sudo ./install.sh; \
	else \
		sudo mkdir -p $(INSTALL_DIR); \
		sudo cp -r $(BUILD_DIR)/* $(INSTALL_DIR)/; \
		sudo mkdir -p $(BIN_DIR); \
		echo '#!/bin/bash' | sudo tee $(BIN_DIR)/$(EXECUTABLE_NAME) > /dev/null; \
		echo 'exec $(INSTALL_DIR)/$(EXECUTABLE_NAME) "$$@"' | sudo tee -a $(BIN_DIR)/$(EXECUTABLE_NAME) > /dev/null; \
		sudo chmod +x $(BIN_DIR)/$(EXECUTABLE_NAME); \
	fi
	@echo "Installation complete. Run with: $(EXECUTABLE_NAME)"


uninstall:
	@echo "Uninstalling $(EXECUTABLE_NAME)..."
	@if [ -f "$(BUILD_DIR)/uninstall.sh" ]; then \
		cd $(BUILD_DIR) && sudo ./uninstall.sh; \
	else \
		sudo rm -rf $(INSTALL_DIR); \
		sudo rm -f $(BIN_DIR)/$(EXECUTABLE_NAME); \
	fi
	@echo "Uninstall complete"

clean-build:
	$(VENV_ACTIVATE) && tools/clean.py --build

clean-package:
	$(VENV_ACTIVATE) && tools/clean.py --package

clean-pycache:
	$(VENV_ACTIVATE) && tools/clean.py --pycache

clean-logs:
	$(VENV_ACTIVATE) && tools/clean.py --empty-log-dir

clean:
	$(VENV_ACTIVATE) && tools/clean.py