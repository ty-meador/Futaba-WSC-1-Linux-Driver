![Image of VRC-Pro RC simulator with the chosen input device being "Virtual Futaba WSC-1 on the right, and a UI on the left; The left of which is displaying a list of available Futaba USB devices, and the right of which is displaying a list of currently running devices"](screenshots/example.gif "VRC-Pro with WSC-1")


# Futaba USB RC Driver for Linux

Usermode driver for Futaba USB RC adapters. This allows most windows games to play nicely with your hardware on Linux. In theory this should "just work" for any Futaba USB RC adapter but I've only tested with the Futaba WSC-1 on VRC-Pro

## Credits
This project was inspired by the [Futaba_T16IZ_Linux](https://github.com/shaozu/Futaba_T16IZ_Linux) repo which was inspired by [dji-mini-controller-linux-driver](https://github.com/catrielmuller/dji-mini-controller-linux-driver).


## Easy install
```shell
wget spam://download-link-comhing-soon/web-installer.sh && chmod +x web-installer.sh && ./web-installer.sh
```




## Quickstart
### python3.11+ required

```shell
# Ensure python version is 3.11+
python3 -c "import sys; exit(0) if sys.version_info >= (3, 11) else exit(1)" 2>/dev/null && echo "good to go" || (echo "python version must be at least 3.11"; exit 1)

# Clone this repo
git clone https://gitlab.com/Native-Coder/futaba-usb-driver

# Change working directory to the repo you just cloned
cd futaba-usb-driver

# install dependencies
python -m pip install .
```

## You are now ready for development
```shell
# You are now ready for development
(.venv) user@linux:~/projects/Futaba_USB_Linux_Driver$ sudo ./futaba-rc-driver 
[sudo] password for user: 
Found 1 Futaba devices, autostarting Futaba WSC-1(135)
Started Futaba WSC-1(135)
CTRL + C to stop driver
```
- If you only have 1 device the driver should start automatically.
- Otherwise you will be present with a menu of detected devices
  - Type the number corresponding to the device you want to use
- **Leave the terminal running while you game**
- If your device does not show up please consider supporting the project by [creating an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)

## Building and Packaging
From the root of the repository
- Ensure all dependencies are installed: `python -m pip install .`
- run `python3 ./build_tools/build.py`

To package the build into a stand-alone (a.k.a. "portable") install
  - run `python3 ./build_tools/package.py`
  - This will create a directory called "dist" which includes:
    - The built package
    - A `tar.xyz` and `tar.gz` bundle of the built package
    - shasums of all files
    - `quick-install.sh` script
    - From here you can install, unintstall, and manually run the driver
      - install: `sudo ./install.sh`
      - uninstall: `sudo ./uninstall.sh`
      - run: `./futaba-rc-driver`

## Running the portable build
- cd into the directory where the built package is located
  - ex: `cd futaba-rc-driver-9994302-linux-X86_64`
- From here you can install, unintstall, and manually run the driver
  - install: `sudo ./install.sh`
  - uninstall: `sudo ./uninstall.sh`
  - run: `./futaba-rc-driver`

If all went well you should see somthing similar to the following
```shell
user@linux:~/projects/Futaba_USB_Linux_Driver/dist/futaba-rc-driver-99943d2-linux-x86_64$ sudo ./futaba-rc-driver 
[sudo] password for user: 
🎮 RC USB Receiver Driver
==============================
✅ Found 1 Futaba device(s)
🚀 Auto-starting Futaba WSC-1(135)
✅ Started Futaba WSC-1(135)
🎯 Driver is running. Press CTRL+C to stop.
```

## Issues and Contributing
If you encounter any issues or would like to contribute:
- [please create an issue](https://gitlab.com/Native-Coder/futaba-usb-rc-linux-driver/-/issues/new)
- I will respond as soon as I am able

## Compatability Chart
| Futaba Device                                 | Game                                                          | Supported | 
| --------------------------------------------- | ------------------------------------------------------------- | --------- |
| [WSC-1](https://futabausa.com/product/wsc-1/) | [VRC-Pro](https://store.steampowered.com/app/335070/VRC_PRO/) |  ✓  |
| [INTERLINK Plus](https://fccid.io/AZPFS0005H/User-Manual/Manual-232847) | [Real Flight Generation 2](https://forums.realflight.com/index.php?forums/realflight-g2.18/) | SAMPLES NEEDED | 
| [T16IZ](https://futabausa.com/product/transmitter-16iz/) | NEEDS TESTING | NEEDS TESTING
* goal is 100% Futaba device compatibility. The easiest way to help us with this is to test with any Futaba devices you have laying around and create an issue outlining your results.

# Driver Limitations
 - The nature of the device is that of a user space virtual joystick. This has a few inherent limitations
   - If you start (or restart) the driver while VRC-Pro is running, you MUST go into the settings and select the Futaba adapter as your input device