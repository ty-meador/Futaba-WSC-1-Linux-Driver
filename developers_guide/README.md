# Developer Guide

### Getting Started

#### Prerequisites

- Linux x86_64 system
- Python 3.11 or higher
- GCC or Clang compiler
- Make utility
- Git

#### Initial Setup

1. **Clone or download the repository:**

    ```sh
    git clone https://gitlab.com/Native-Coder/futaba-usb-driver/
    cd futaba-usb-driver
    ```

2. **Create and activate virtual environment:**

    ```sh
    python3 -m venv .venv
    source .venv/bin/activate
    ```

    **Important:** All development scripts require the virtual environment to be active. The scripts will refuse to run if not in a venv.

3. **Install dependencies:**

    ```sh
    pip install .
    ```

4. **Install build tools:**

    ```sh
    pip install nuitka
    ```

5. **Install system dependencies:**

    ```sh
    # Ubuntu/Debian
    sudo apt install build-essential python3-dev libusb-1.0-0-dev

    # Arch/Manjaro
    sudo pacman -S base-devel python libusb
    ```

#### Project Structure

> API documentation can be found [here](https://tylermeador.com/futaba-rc-driver/docs/)

```
futaba-usb-driver/
├── LICENSE                              # Project license (distribution)
├── main.build                           # Build configuration/cache (generated)
├── makefile                             # Convenience build commands
├── NOTICE                               # Third-party attribution notices
├── pyproject.toml                       # Project metadata, dependencies, build config
├── README.md                            # Project documentation (for developers)
├── run.sh                               # Wrapper script - runs driver from source without activating venv
│
├── screenshots/                         # Marketing/documentation images
│   ├── calibration_mode.png             # Calibration UI screenshot
│   └── example.gif                      # Demo animation for README
│
├── src/                                 # Source code
│   ├── 49465.pid                        # Process ID file (runtime artifact - should be in .gitignore)
│   │
│   ├── Futaba/                         # Core driver package
│   │   ├── calibrations/               # Calibration profiles per device
│   │   │   ├── _default.json           # Fallback calibration settings
│   │   │   ├── _T16IZ.json             # Futaba T16IZ specific calibration
│   │   │   └── _WSC-1.json             # Futaba WSC-1 specific calibration
│   │   │
│   │   ├── configs/                    # Device configuration files
│   │   │   ├── _default.json           # Default device config
│   │   │   ├── _T16IZ.json             # T16IZ channel mapping & settings
│   │   │   └── _WSC-1.json             # WSC-1 channel mapping & settings
│   │   │
│   │   ├── __config__.py               # Package configuration constants
│   │   ├── DriverSubproc.py            # Main driver logic - Meant to be executed as a subprocess
│   │   ├── Driver.py                   # Programmatic device / driver interface
│   │   ├── Error.py                    # Custom exception classes
│   │   ├── __init__.py                 # Package initialization
│   │   ├── InputChannel.py             # Individual RC channel processing
│   │   ├── IPC.py                      # Inter-process communication utilities
│   │   ├── logs/                       # Runtime log directory (should be empty in repo)
│   │   ├── Manager.py                  # Device detection and lifecycle management
│   │   └── Util.py                     # Helper functions and utilities
│   │
│   ├── main.py                         # Application entry point
│   ├── SocketLock.py                   # Singleton instance enforcement (prevents multiple instances)
│   │
│   └── UI/                             # User interface components
│       ├── Calibration.py              # Interactive calibration interface
│       ├── __init__.py                 # UI package initialization
│       ├── Menu.py                     # CLI menu system
│       └── Window.py                   # Window management utilities
│
├── tools/                              # Build tools / make "phony targets"
│   ├── artifact-templates/             # Templates for generated files
│   │   ├── README.md                   # User-facing README template (with {{variables}})
│   │   │
│   │   ├── scripts/                   # Installation script templates
│   │   │   ├── install.sh             # System installer template
│   │   │   ├── uninstall.sh           # System uninstaller template
│   │   │   ├── web-installer.sh       # Quick web install script template
│   │   │   ├── wrapper-script.sh      # Development wrapper template
│   │   │   └── wrapper.sh             # Distribution wrapper template
│   │   │
│   │   ├── udev.rules                 # USB device permissions template
│   │   └── VERSION                    # Version info file template
│   │
│   ├── build.py                        # Nuitka compilation script (Python → native binary)
│   ├── clean.py                        # Cleanup script (removes build artifacts)
│   ├── __config__.py                   # Build system configuration (loads from pyproject.toml)
│   ├── package.py                      # Distribution packaging script (creates tar.gz/tar.xz)
│   └── util.py                         # Build system utilities (template rendering, command execution)
│
└── typings/                            # Type hints for external libraries
    ├── uinput/                         # Python-uinput type stubs
    │   └── __init__.pyi                # uinput interface definitions
    ├── uniput.pyi                      # Alternate typing file (typo or variant?)
    └── usb/                            # PyUSB type stubs
        ├── core.pyi                    # USB core functionality types
        ├── __init__.pyi                # USB package types
        └── util.pyi                    # USB utility types
```

## Key Directories Explained

### `/src/` - Application Source

All runtime code lives here. The `main.py` entry point coordinates the `Futaba` driver package and optional `UI` components.

### `/src/Futaba/` - Driver Core

Contains the actual USB communication, device management, and channel processing logic. Configuration files in `configs/` define device-specific channel mappings, while `calibrations/` store min/max/center values for each device.

### `/src/UI/` - User Interface

Terminal-based UI for calibration and configuration. Separated from core driver logic for optional inclusion.

### `/tools/` - Build System

Complete build pipeline for creating standalone distributions:

- **Build phase** (`build.py`): Compiles Python to native executable using Nuitka
- **Package phase** (`package.py`): Creates distribution archives with installers
- **Clean phase** (`clean.py`): Removes generated artifacts

### `/tools/artifact-templates/` - Distribution Templates

Contains templates with `{{mustache}}` variables that get rendered during packaging. The `package.py` script replaces variables like `{{executable_name}}`, `{{version}}`, etc. with actual values from `pyproject.toml`.

### `/typings/` - Type Stubs

Provides IDE autocomplete and type checking for external libraries that lack native type hints (`uinput`, `usb`).

## Generated Directories (Not in Repo)

These directories are created during build/runtime and should be in `.gitignore`:

```
├── .venv/                              # Virtual environment (development)
├── build/                              # Compiled executable and dependencies
│   └── futaba-rc-driver.dist/          # Nuitka output directory
├── dist/                               # Distribution packages
│   └── futaba-rc-driver-X.Y.Z-linux-x86_64/
│       ├── *.tar.gz                    # Compressed archive
│       ├── *.tar.xz                    # Highly compressed archive
│       ├── *.sha256                    # Checksums
│       ├── install.sh                  # Rendered installer
│       ├── uninstall.sh                # Rendered uninstaller
│       ├── web-installer.sh            # Rendered quick installer
│       └── README.md                   # Rendered user documentation
└── src/Futaba/logs/                    # Runtime log files
```

## Critical Files

| File                  | Purpose                                                     |
| --------------------- | ----------------------------------------------------------- |
| `pyproject.toml`      | Single source of truth for versions, dependencies, paths    |
| `tools/__config__.py` | Loads `pyproject.toml` and provides config to build scripts |
| `src/main.py`         | Application entry point                                     |
| `run.sh`              | Developer convenience - run without activating venv         |
| `makefile`            | Quick access to common build commands                       |

## Workflow Summary

1. **Development**: Edit code in `src/`, test with `./run.sh` or `make run`
2. **Build**: `make build` → creates `build/futaba-rc-driver.dist/`
3. **Package**: `make package` → creates `dist/futaba-rc-driver-X.Y.Z-linux-x86_64/`
4. **Distribution**: Upload archives and web installer from `dist/`
5. **Installation**: End users run `./install.sh` from extracted archive

### Development Workflow

#### Using Make (Recommended)

The project includes a `makefile` with convenient targets

```sh
# Build executable only
make build

# Build and package distribution
make package

# Clean all build artifacts
make clean

# Clean only build artifacts
make clean-build

# Clean only package artifacts
make clean-package

# Run the driver directly from source (for testing)
make run

# Complete build workflow (clean, build, package)
make all
```

#### Using the Wrapper Script

The `run.sh` wrapper script allows you to run the driver from source without activating the venv manually:

```sh
./run.sh                    # Run driver
./run.sh --calibrate        # Run calibration
./run.sh --help             # Show help
```

**How it works:** The wrapper automatically sources the venv, runs the main.py script with your arguments, then deactivates the venv when done.

**When to use:**

- Quick testing during development
- Running the driver without building
- Debugging with source-level visibility

**When NOT to use:**

- For production deployments (use the built executable)
- When testing the actual built binary
- In automated scripts (use the venv directly)

#### Manual Script Execution

If you prefer to run scripts directly:

```sh
# Activate venv first!
source .venv/bin/activate

# Then run any script
./tools/build.py
./tools/package.py
./tools/clean.py

# Deactivate when done
deactivate
```

### Build System Details

#### Build Process (`build.py`)

Creates a standalone executable using Nuitka:

```sh
# Basic build
./tools/build.py

# Clean before building
./tools/build.py --clean
```

**What it does:**

1. Validates environment (Python version, compiler, Nuitka)
2. Installs project dependencies
3. Locates native libraries (.so files) in venv
4. Compiles Python to C, then to native binary
5. Bundles all dependencies into `build/` directory
6. Creates wrapper script for execution
7. Tests the executable

**Configuration:** Settings are defined in `pyproject.toml` under `[tool.build_tool]`:

- `build_dir`: Output directory for built executable
- `executable_name`: Name of the final binary
- `install_dir`: Default installation path
- `native_dependencies`: Libraries to bundle

#### Packaging (`package.py`)

Creates distribution archives ready for release:

```sh
# Create packages
./tools/package.py

# Clean before packaging
./tools/package.py --clean
```

**What it does:**

1. Extracts version from git tags (or uses default)
2. Creates distribution directory structure
3. Copies executable, docs, and scripts
4. Renders template files (install.sh, README.md, etc.)
5. Creates tar.gz and tar.xz archives
6. Generates SHA256 checksums
7. Creates web installer script

**Output:** `dist/futaba-rc-driver-X.Y.Z-linux-x86_64/`

- Compressed archives (.tar.gz, .tar.xz)
- Checksums (.sha256 files)
- Web installer (web-installer.sh)
- Full installation package

#### Cleanup (`clean.py`)

Removes generated artifacts:

```sh
# Clean everything
./tools/clean.py

# Selective cleaning
./tools/clean.py --build          # Build artifacts only
./tools/clean.py --package        # Package artifacts only
./tools/clean.py --pycache        # Python cache files
./tools/clean.py --empty-log-dir  # Log files
```

### Template System

The build system uses Jinja2-style templates in `tools/artifact-templates/`:

**Template syntax:**

```sh
# In template file:
{{variable_name}}

# Gets replaced with actual values from __config__.py
```

**Key templates:**

- `scripts/install.sh` → Installation script
- `scripts/uninstall.sh` → Removal script
- `scripts/web-installer.sh` → Quick web installer
- `scripts/wrapper.sh` → Executable wrapper
- `README.md` → Distribution README
- `VERSION` → Version information file

### Configuration Management

All build configuration is centralized in `tools/__config__.py`, which loads settings from `pyproject.toml`.

**Key settings:**

```python
BUILD_DIR          # Where executable is built
PACKAGE_DIR        # Where distribution is packaged
EXECUTABLE_NAME    # Name of the binary
INSTALL_DIR        # Default installation path
VERSION            # Project version
```

**Adding new configuration:**

1. Add to `pyproject.toml` under `[tool.build_tool]`
2. Import in `__config__.py`
3. Use in build/package scripts

### Testing Builds

```sh
# Test the built executable
./build/futaba-rc-driver --version
./build/futaba-rc-driver --help

# Test with sudo (required for uinput)
sudo ./build/futaba-rc-driver

# Test calibration mode
sudo ./build/futaba-rc-driver --calibrate
```

### Version Management

Versions are tracked in `pyproject.toml`:

```toml
[project]
version = "1.2.3"
```

The packaging script attempts to extract the version from git tags:

```sh
git describe --tags --always --dirty
```

Format: `v1.2.3` or `v1.2.3-5-gabcdef` (with commits ahead)

### Common Development Tasks

#### Adding a new device configuration

1. Create config file: `src/Futaba/configs/_DEVICE_NAME.json`
2. Create calibration file: `src/Futaba/calibrations/_DEVICE_NAME.json`
3. Add device detection logic in `src/Futaba/Manager.py`

#### Modifying the installer

1. Edit template: `tools/artifact-templates/scripts/install.sh`
2. Add any new variables to the template rendering in `package.py`
3. Test with `make package`

#### Changing installation paths

1. Update `pyproject.toml` → `[tool.build_tool]`
2. Rebuild: `make clean build package`
3. Test installation in a clean environment

### Release Checklist

1. Update version in `pyproject.toml`
2. Update CHANGELOG (if exists)
3. Run full build: `make clean all`
4. Test executable: `./build/futaba-rc-driver --version`
5. Test installation: `./dist/*/install.sh`
6. Create git tag: `git tag v1.2.3`
7. Upload distribution files to release page

### Troubleshooting Development Issues

**Nuitka compilation fails:**

- Ensure C compiler is installed
- Check Python version (3.11+ required)
- Try `make clean` then rebuild

**Scripts refuse to run:**

- Activate venv: `source .venv/bin/activate`
- Check Python version in venv: `python --version`

**Missing dependencies:**

- Reinstall: `pip install .`
- Check for system libraries: `ldconfig -p | grep usb`

**Template rendering issues:**

- Verify template syntax (double braces)
- Check variable names in `__config__.py`
- Look for typos in template files

---

## Support

For issues, updates, and documentation visit:
https://gitlab.com/Native-Coder/futaba-usb-driver/

---

Built with ❤️ for the RC community
