import asyncio
from driver import FutabaUsbDeviceDriver

async def main():
    driver = FutabaUsbDeviceDriver()
    await driver.start()

if __name__ == '__main__':
    asyncio.run( main() )