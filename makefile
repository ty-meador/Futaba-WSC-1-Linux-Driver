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
EXECUTABLE_NAME := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject tool.build_tool.executable_name)
BUILD_DIR := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject tool.build_tool.build_dir)
PACKAGE_DIR := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject tool.build_tool.package_dir)
INSTALL_DIR := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject tool.build_tool.install_dir)
BIN_DIR := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject tool.build_tool.bin_dir)
VERSION := $(shell $(VENV_ACTIVATE) && tools/util.py --pyproject project.version)

GIT_VERSION := $(shell git describe --tags --always --dirty 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "$(VERSION)")
PACKAGE_NAME := $(EXECUTABLE_NAME)-$(GIT_VERSION)-linux-x86_64
PACKAGE_BUILD_DIR := $(PACKAGE_DIR)/$(PACKAGE_NAME)
PACKAGE_TARBALL := $(PACKAGE_BUILD_DIR)/$(PACKAGE_NAME).tar.gz

# Documentation
DOCS_DIR := docs
DOCS_SOURCE_DIR := $(DOCS_DIR)/source
DOCS_BUILD_DIR := $(DOCS_DIR)/build
SPHINX_BUILD := $(VENV_DIR)/bin/python -m sphinx
SPHINX_OPTS :=

# Source files and dependencies
SOURCE_MAIN := src/main.py
SOURCES := $(shell find src -name '*.py' 2>/dev/null)
BUILD_TOOLS := tools/build.py tools/package.py tools/clean.py tools/util.py tools/__config__.py
TEMPLATE_FILES := $(shell find tools/artifact-templates -type f 2>/dev/null)


EXECUTABLE := $(BUILD_DIR)/$(EXECUTABLE_NAME)

# Package depends on executable, build tools, and template changes
$(PACKAGE_TARBALL): $(EXECUTABLE) $(BUILD_TOOLS) $(DOCS_DIR) $(TEMPLATE_FILES)
	@echo "Dependencies changed, repackaging..."
	$(VENV_ACTIVATE) && tools/package.py

# The executable depends on source and build tool changes
$(EXECUTABLE): $(SOURCES) $(PYPROJECT)
	@echo "Source files changed, rebuilding..."
	$(VENV_ACTIVATE) && tools/build.py

.DEFAULT_GOAL := help
.PHONY: help all build release stubs docs package install uninstall test clean clean-build clean-package clean-pycache clean-logs version

help:
	@echo "Futaba RC Driver - Build System"
	@echo "================================"
	@echo ""
	@echo "Available targets:"
	@echo "  make build          - Build executable with Nuitka"
	@echo "  make release        - Build a release"
	@echo "  make stubs          - Regenerate type stubs"
	@echo "  make docs           - Generate Sphinx documentation"
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

build: $(EXECUTABLE)

release:
	@echo "Prepping new release"
	$(VENV_ACTIVATE) && tools/prep-release.sh
	$(MAKE) all
	@echo ""
	@echo "Release complete! To publish:"
	@echo "  git push && git push --tags"

stubs:
	@echo "Generating type stubs..."
	$(VENV_ACTIVATE) && tools/build.py --type-stubs

docs: $(SOURCES) $(PYPROJECT)
	@echo "Building Sphinx documentation..."
	@$(VENV_ACTIVATE) && tools/clean.py --docs
	@$(VENV_ACTIVATE) && sphinx-apidoc -f -o $(DOCS_SOURCE_DIR) src/Futaba/ --tocfile index
	@$(VENV_ACTIVATE) && $(SPHINX_BUILD) -M html "$(DOCS_SOURCE_DIR)" "$(DOCS_BUILD_DIR)" $(SPHINX_OPTS)
	@echo ""
	@echo "Documentation built: $(DOCS_BUILD_DIR)/html/index.html"

test: $(EXECUTABLE)
	@echo "Testing executable..."
	@$(EXECUTABLE) --version

package: $(PACKAGE_TARBALL)

install: $(PACKAGE_TARBALL)
	@$(MAKE) uninstall
	@echo "Installing $(EXECUTABLE_NAME) from $(PACKAGE_BUILD_DIR)..."
	@if [ ! -d "$(PACKAGE_BUILD_DIR)" ]; then \
		echo "Error: Package directory not found: $(PACKAGE_BUILD_DIR)"; \
		echo "Run 'make package' first"; \
		exit 1; \
	fi
	cd $(PACKAGE_BUILD_DIR) && ./install.sh

uninstall:
	@echo "Uninstalling $(EXECUTABLE_NAME)..."
	@if [ -f "$(INSTALL_DIR)/uninstall.sh" ]; then \
		cd "$(INSTALL_DIR)" && ./uninstall.sh; \
	elif [ -f "$(PACKAGE_BUILD_DIR)/uninstall.sh" ]; then \
		cd "$(PACKAGE_BUILD_DIR)" && ./uninstall.sh; \
	elif [ -f "$(BUILD_DIR)/uninstall.sh" ]; then \
		cd "$(BUILD_DIR)" && ./uninstall.sh; \
	else \
		echo "No install detected! Nothing to do!"; \
	fi

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