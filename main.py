import asyncio
from driver import FutabaUsbController

async def main():
    driver = FutabaUsbController()
    try:
        await driver.startAll()
    except KeyboardInterrupt:
        await driver.stopAll()

if __name__ == '__main__':
    asyncio.run( main() )