# import re, usb, uinput, time, subprocess
from driver import FutabaUsbDeviceDriver

if __name__ == '__main__':
    driver = FutabaUsbDeviceDriver()
    driver.start()