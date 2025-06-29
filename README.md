![Image of VRC-Pro RC simulator with the chosen input device being "Virtual Futaba WSC-1 on the right, and a UI on the left; The left of which is displaying a list of available Futaba USB devices, and the right of which is displaying a list of currently running devices"](screenshots/banner.png "VRC-Pro with WSC-1")


# Futaba USB RC Linux Driver 

Python script that will remap the native hardware inputs to a virtual joystick device. This allows most windows games to play nicely with your hardware on Linux. In theory this should "just work" if any Futaba USB RC adapter but I've only tested with the Futaba WSC-1 on VRC-Pro

## Credits
This project was inspired by the [Futaba_T16IZ_Linux](https://github.com/shaozu/Futaba_T16IZ_Linux) repo which was inspired by [dji-mini-controller-linux-driver](https://github.com/catrielmuller/dji-mini-controller-linux-driver).



## Quickstart
```shell
# NOTE: The driver requires root level access which means you must be a sudoer!

# Clone this repo
git clone https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver.git 
# Change working directory to the repo you just cloned
cd futaba-usb-rc-linux-driver
# install dependencies
sudo pip3 install -r requirements.txt
sudo ./run.sh --text-ui
```
# Use
## Single Device
```shell
# Make sure you are in the projects folder
# cd /path/to/futaba-usb-rc-linux-driver
sudo ./run.sh
```
- You will be shown a list of connected Futaba USB devices
```shell
Which device would you like to start?
[ 0 ] : Futaba WSC-1(135)
0
Started Futaba WSC-1(135)
CTRL + C to stop driver
```
- Type the number corresponding to the device you want to use
- **Leave the terminal running while you game**

## Multiple Devices
```shell
# Make sure you are in the projects folder
# cd /path/to/futaba-usb-rc-linux-driver
# Start the UI
sudo ./run.sh --text-ui
```
- The UI will show a list of available Futaba USB devices
  - Click the button for the device you want to start
- Each device that you start will run in a **separate process**
  - This ensures that each device gets the maximum bandwidth possible
  - This prevents the entire driver from crashing if a single device crashes
- **Leave the terminal running while you game**
```shell               
                        ┌─ Running Drivers ───────────────────────────────────────────────┐                   
  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔ │[{'name': 'Futaba WSC-1(1,1)', 'state': 'RUNNING', 'key': 0}]    │                   
  Futaba WSC-1(1,1) ⏹   └─────────────────────────────────────────────────────────────────┘                   
  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
```
- If your device does not show up please consider supporting the project by [creating an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)


## Issues and Contributing
If you encounter any issues or would like to contribute:
- [please create an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)
- I will respond as soon as I am able

## Compatability Chart
| Futaba Device                                 | Game                                                          | Supported | 
| --------------------------------------------- | ------------------------------------------------------------- | --------- |
| [WSC-1](https://futabausa.com/product/wsc-1/) | [VRC-Pro](https://store.steampowered.com/app/335070/VRC_PRO/) |  ✓  |
| [INTERLINK Plus](https://fccid.io/AZPFS0005H/User-Manual/Manual-232847) | [Real Flight Generation 2](https://forums.realflight.com/index.php?forums/realflight-g2.18/) | SAMPLES NEEDED | 


# Driver Limitations
 - The nature of the device is that of a user space virtual joystick. This has a vew inherent limitations
   - If you start (or restart) the driver while VRC-Pro is running, you MUST go into the settings and select the Futaba adapter as your input device