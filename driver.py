import asyncio
import               \
    os,              \
    re,              \
    json,            \
    usb,             \
    uinput,          \
    time,            \
    subprocess,      \
    logging,         \
    logging.handlers \
    
def generateLogger(
        name,
        maxSize = 5 * 1024 * 1024, # 5 megabytes
        backupCount = 5,
        level = logging.WARNING
    ):
        """Generates a logger

        Args:
            name (str): _description_
            maxSize (int, optional): Max file size of log files. Defaults to 5*1024*1024.
            backupCount (int, optional): Number of backup logs to keep in rotation. Defaults to 5
            level (loglevel, optional): The level the logger should output. Defaults to logging.WARNING.

        Returns:
            logger: The generated logger
        """
        handler = logging.handlers.RotatingFileHandler (
            f"{name}.log",
            maxBytes=maxSize,
            backupCount=backupCount
        )
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger
    

class FutabaUsbDeviceDriver():

    def __init__(self):

        self.config             = self._loadConfig()
        self.coroutines         = []
        self.devices            = []
        self.logger             = generateLogger( name="driver" )
        self.runningDevices     = None
        self.stoppingDevices    = None
        
        try:
            self._loadConfig()
            lsusb               = "/usr/bin/lsusb"
            subproc             = subprocess.run( lsusb, capture_output = True, text = True )
            lsusb_output        = subproc.stdout.strip()
            futaba_device_regex = r"Bus ([0-9]{3}).*Device ([0-9]{3}):.*ID ([0-9a-fA-F]{4}):([0-9a-fA-F]{4}) ((?i)futaba.*)"
            matches             = re.findall( futaba_device_regex, lsusb_output )

            if len( matches ) == 0:
                raise Exception( "No Futaba USB device detected!" )         
        except Exception as e:
            self.logger.critical( e )
            exit( 1 )


        for device in matches:
            [ # Destructure our regex groups into what they actually are
                bus,
                device,
                vendorId,
                productId,
                name
            ] = device

            # Map local variables to a dictionary to be returned later
            deviceInfo = {
                "bus"       : bus.strip(),
                "device"    : device.strip(),
                "name"      : name.strip(),
                "productId" : productId.strip(),
                "vendorId"  : vendorId.strip()
            }

            self.devices.append( FutabaUsbDevice( deviceInfo, self.config ) )

    def __str__(self):
        return f"Devices: {self.devices}"

    def __repr__(self):
        return f"Devices: {self.devices}"
    
    def _loadConfig(self):
        """Loads the settings from config.json

        Returns:
            dict: A dictionary containing the driver settings
        """
        config = None

        # Try to load, regenerate default config if that fails and try again
        for retry in range( 0, 2 ):
            try:
                with open( "config.json", 'r' ) as cfgFile:
                    config = json.load( cfgFile )
            except:
                self._generateDefaultConfigFile( forceRegenerate=True )

        if config is None:
            self.logger.critical( "Unable to load the config file" )
            exit( 1 )

        return config

    def _generateDefaultConfigFile(self, forceRegenerate=False):
        """Regenerates the default config file

        Args:
            forceRegenerate (bool, optional): If true the existing configuration file will be deleted and a new one will be created using default values. Defaults to False.
        """
        FILE_NAME = "config.json"
        BACKUP_FILE_NAME = f"{FILE_NAME}.{time.time()}.BACKUP"

        if os.path.exists( FILE_NAME ):
            # Force regenerate will delete the existing file and generate a
            # new one from scratch
            if forceRegenerate is True:
                
                os.rename( FILE_NAME, BACKUP_FILE_NAME )
                self.logger.info( f"Force regnerating default config file: your config file was backed up to {BACKUP_FILE_NAME}" )
            else: # file exists, not force regenerating - do nothing
                return
        
        # A dict with a 1:1 representation of the JSON file that will be generated...
        DEFAULT_CONFIG = {
            "frame_size": 16,
            "event_max_value": 32768,
            "futaba-wsc-1": {
                "channels": 2
            }
        }

        # ...told ya
        with open(FILE_NAME, "w") as cfgFile:
            cfgFile.write( json.dumps( DEFAULT_CONFIG, indent=4 ) )

    async def start(self):
        for device in self.devices:
            self.coroutines.append( await device.start() )
        self.runningDevices = asyncio.gather( self.coroutines )
    
    async def stop(self):
        self.runningDevices.cancel()

        for device in self.devices:
            self.coroutines.append( device.stop() )
        self.stoppingDevices = asyncio.gather( self.coroutines )






class FutabaUsbDevice():
    def __init__(self, deviceInfo = None, config = None):
        # We want to give the user a more friendly failure message
        if deviceInfo is None:
            self.logger.critical( "No Futaba USB device detected" )
            exit( 1 )

        self.logFile       = deviceInfo["name"].replace( " ", "_" )
        self.logger        = generateLogger( self.logFile )

        if config is None:
            self.logger.critical( "No config provided to device instance!" )
            exit( 1 )

        self.state         = "initializing"
        self.bus           = deviceInfo["bus"]
        self.device        = deviceInfo["device"]
        self.name          = deviceInfo["name"]
        self.productId     = int( deviceInfo['productId'], 16 )
        self.vendorId      = int( deviceInfo['vendorId'], 16 )
        self.config        = config
        self.frameSize     = config["frame_size"]
        self.eventMaxValue = config["event_max_value"]
        self.eventList     = [ # 8 channels
            uinput.ABS_X,
            uinput.ABS_Y,
            uinput.ABS_RX,
            uinput.ABS_RY,
            uinput.ABS_THROTTLE,
            uinput.ABS_RUDDER,
            uinput.ABS_TILT_X,
            uinput.ABS_TILT_Y
        ]
        
        self.eventReverseFlag = [False] * len( self.eventList ) # Default to no reversed inputs

        self.usbHandle = usb.core.find( idVendor=self.vendorId, idProduct=self.productId )
        if self.usbHandle is None:
            self.logger.critical( f"Failed to create a usb handle for device {self.vendorId}:{self.productId} ({self.name})" )
            exit(1)
        
        self.logger.info( f"Found {self.name}" )

        events = tuple( map(
            lambda event: event + ( 0, self.eventMaxValue, 0, 0 ),
            self.eventList
        ))

        self.virtualDevice = uinput.Device( events, f"Virtual {self.name}", vendor=self.vendorId )
        self.logger.info( f"Virtual {self.name} created" )
        self.state = "ready"
    
    def __str__(self):
        return f"Virtual {self.name} driver"
    
    def __repr__(self):
        return f"bus={self.bus}, device={self.device}, name={self.name}, productId={self.productId}, vendorId={self.vendorId}, config={self.config}, frameSize={self.frameSize}, eventMaxValue={self.eventMaxValue}, eventList={self.eventList}"

    def _stdout(self, msg):
        """prints a message to stdout with an identifying banner

        Args:
            msg (str): The message to output
        """
        print( f"{self.name}: {msg}" )

    async def getInterruptEndpoint(self, device):
        """Finds the interrupt endpoint of the physical device

        Example:
            DEVICE ID 1008:000a on Bus 001 Address 002 =================
                bLength                :   0x12 (18 bytes)
                bDescriptorType        :    0x1 Device
                bcdUSB                 :  0x200 USB 2.0
                bDeviceClass           :    0x0 Specified at interface
                bDeviceSubClass        :    0x0
                bDeviceProtocol        :    0x0
                bMaxPacketSize0        :   0x40 (64 bytes)
                idVendor               : 0x1008
                idProduct              : 0x000a
                bcdDevice              :  0x200 Device 2.0
                iManufacturer          :    0x1 Futaba
                iProduct               :    0x2 WSC-1
                iSerialNumber          :    0x3 000000000
                bNumConfigurations     :    0x1
                    CONFIGURATION 1: 500 mA ==================================
                    bLength              :    0x9 (9 bytes)
                    bDescriptorType      :    0x2 Configuration
                    wTotalLength         :   0x22 (34 bytes)
                    bNumInterfaces       :    0x1
                    bConfigurationValue  :    0x1
                    iConfiguration       :    0x0 
                    bmAttributes         :   0x80 Bus Powered
                    bMaxPower            :   0xfa (500 mA)
                        INTERFACE 0: Human Interface Device ====================
                        bLength            :    0x9 (9 bytes)
                        bDescriptorType    :    0x4 Interface
                        bInterfaceNumber   :    0x0
                        bAlternateSetting  :    0x0
                        bNumEndpoints      :    0x1
                        bInterfaceClass    :    0x3 Human Interface Device
                        bInterfaceSubClass :    0x0
                        bInterfaceProtocol :    0x0
                        iInterface         :    0x0 
                            ENDPOINT 0x87: Interrupt IN ==========================
                            bLength          :    0x7 (7 bytes)
                            bDescriptorType  :    0x5 Endpoint
                            bEndpointAddress :   0x87 IN
                            bmAttributes     :    0x3 Interrupt
                            wMaxPacketSize   :   0x40 (64 bytes)
                            bInterval        :    0x1

        Args:
            device (_type_): _description_

        Returns:
            _type_: _description_
        """
        for config in device:
            for interface in config:
                for endpoint in interface:
                    if usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN and endpoint.bmAttributes == 0x3:
                        self.logger.info( f"Found interrupt endpoint >{endpoint.bEndpointAddress}<" )
                        return endpoint.bEndpointAddress
        self.logger.critical( "No interrupt endpoint found!" )
        exit(1)

    async def parseDataFrame(self, data):
        """Parses the provided data frame into an ordered list of channel data frames

        Args:
            data (dataFrame): A data frame from the physical device

        Returns:
            list: Ordered list of channel data frames
        """

        parsed = []
        for i in range( 0, len( data ), 2 ):
            # remap data from (min 704, center 2048, max 3392) -> (min 0, center 16384, max 32768)
            channelData = int.from_bytes( data[i:i+2], byteorder="little" )
            channelData =  ( channelData - 704 ) * 256 // 21
            parsed.append( channelData )
        parsed.reverse()
        self.logger.info( f"Parsed data frame >{parsed}<" )
        return parsed

    async def sendDataFrame(self, data):
        """Sends the provided list of data packets to our virutal device

        Args:
            data (list): A list where each index represents a single channel. Each item will be a data
            packet from the physical device
        """
        # Queue one event for each channel
        for i in range( 0, len( self.eventList ) ):
            channelData = data[i]
            # Reverse the input if necessary
            if self.eventReverseFlag[i]:
                channelData = self.eventMaxValue - data[i]
            # queue channel event
            self.virtualDevice.emit( self.eventList[i], channelData, syn=False )
        # Synchronize (fire all queued events)
        self.virtualDevice.syn() 

    async def start(self):
        """Start the driver
        """
        try:
            self.logger.info( "Detaching kernel driver..." )
            if self.usbHandle.is_kernel_driver_active( 0 ): 
                self.usbHandle.detach_kernel_driver( 0 ) 

            self.logger.info( "Using default configuration..." )
            self.usbHandle.set_configuration() 

            self.logger.info( "Finding the interrupt endpoint..." )
            endpoint = await self.getInterruptEndpoint( self.usbHandle )

            if endpoint is None:
                self.logger.critical( f"Unable to find usb endpoint using the handle >{self.usbHandle}<" )
                await self.stop( 1 )

            self.logger.info( f"Remapped {endpoint} -> {self.name}" )

            # Main loop
            while True: 
                try:
                    # read HW frame
                    hwFrame = self.usbHandle.read( endpoint, self.frameSize, timeout=20 )

                    # Parse channel data from HW frame
                    channelData = await self.parseDataFrame( hwFrame )

                    # Send channel data to virtual device
                    await self.sendDataFrame( channelData )

                    # If we reach this point the transmitter must be detected
                    if self.state != "running":
                        self.state = "running"
                        self.logger.info( "Transmitter signal reacquired" )
                        self._stdout( "Transmitter signal reacquired" )

                except usb.core.USBError as e:
                    # kaboom?
                    if e.errno == 110:
                        # dongle doesn't detect transmitter - no big deal
                        if self.state != "timeout":
                            self.state = "timeout"
                            msg = "USB dongle detected but transmitter is not (is it on? is it paired?)"
                            self.logger.info( msg )
                            self._stdout( msg )
                        continue
                    else:
                        # Yes Rico, kaboom.
                        self.state = "critical-usb-error"
                        self.logger.critical( e )
                        await self.stop( 1 )
        except usb.core.USBError as e:
            if e.errno == 13: # Access denied - permissions issue
                self.state = "critical-insufficient-permissions"
                self.logger.critical( "Insufficient permissions to hook USB interface" )
                self._stdout( "Drivers must be run as root" )
                await self.stop( 1 )
        finally:
            await self.stop()
            self.logger.info("...Done!")

    async def stop(self, exitCode=None):
        """Stop the driver
        """
        try:
            self.logger.info("Releasing the USB interface...")
            usb.util.release_interface( self.usbHandle, 0 )
        except Exception as e: 
            self.logger.warning( "Unable to release the USB interface (Did we never acquire it in the first place? Permissions issue?)" )
            self.logger.warning( e )
            pass

        try:
            self.logger.info("Reattaching the kernel driver...")
            self.usbHandle.attach_kernel_driver( 0 )
        except Exception as e: 
            self.logger.warning( "Unable to reattach the kernel driver (Did we never acquire it in the first place? Permissions issue?)" )
            self.logger.warning( e )
            pass

        try:
            self.logger.info("Resetting device...")
            self.usbHandle.reset()
        except Exception as e: 
            self.logger.warning( "Unable to reset the USB interface (Did we never acquire it in the first place? Permissions issue?)" )
            self.logger.warning( e )
            pass
    
        if exitCode is not None:
            exit( exitCode )