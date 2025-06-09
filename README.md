![Image of VRC-Pro RC simulator with the chosen input device being "Virtual Futaba WSC-1 on the right, and a UI on the left; The left of which is displaying a list of available Futaba USB devices, and the right of which is displaying a list of currently running devices"](screenshots/banner.png "VRC-Pro with WSC-1")


# Futaba USB RC Linux Driver 

Python script that will remap the native hardware inputs to a virtual joystick device. This allows most windows games to play nicely with your hardware on Linux. In theory this should "just work" if any Futaba USB RC adapter but I've only tested with the Futaba WSC-1 on VRC-Pro

This repo is inspired by [dji-mini-controller-linux-driver](https://github.com/catrielmuller/dji-mini-controller-linux-driver).

## Installation

### Commands

```shell
# NOTE: The driver requires root level access which means you must be a sudoer!

# Clone this repo
git clone https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver.git 
# Change working directory to the repo you just cloned
cd futaba-usb-rc-linux-driver
# install dependencies
sudo pip3 install -r requirements.txt
```

## Use
```shell
# Make sure you are in the projects folder
cd /path/to/futaba-usb-rc-linux-driver
# Start the UI
sudo start.sh 
```

- This will start a text-based UI
- The UI will show a list of available Futaba USB devices
  - Navigate with the arrow keys
  - Spacebar to select/deselect
- To start or stop a device, simply select or de-select it respectively
- Each device that you start will run in a **seperate subprocess**
  - This ensures that each device gets the maximum bandwidth possible
  - This prevents the entire driver from crashing if a single device crashes


```shell
┌─ Driver for Futaba R/C -> USB Receivers ─────────────────────────────────┐┌─ Running Drivers ────────────────────────────────────────────────────────┐
│                                                                          ││['Futaba WSC-1 (bus-1, port-1)']                                          │
│ ▐X▌ Futaba WSC-1 (bus-1, port-1)                                         │└──────────────────────────────────────────────────────────────────────────┘
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
# Leave this terminal running and launch the RC sim of your choice
```
- If your device does not show up please consider supporting the project by [creating an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)


## Issues and Contributing
If you encounter any issues or would like to contribute:
- [please create an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)
- I will respond as soon as I am able

## Known Compatability Chart
| Futaba Device                                 | Game                                                          | Supported | 
| --------------------------------------------- | ------------------------------------------------------------- | --------- |
| [WSC-1](https://futabausa.com/product/wsc-1/) | [VRC-Pro](https://store.steampowered.com/app/335070/VRC_PRO/) |  &check;  |

## Known issues
 - If you start (or restart) the driver while VRC-Pro is running, you MUST go into the settings and select the Futaba adapter as your input device