import asyncio
from driver import FutabaUsbController

async def main():
    driver = FutabaUsbController()
    await driver.startAll()

if __name__ == '__main__':
    asyncio.run( main() )