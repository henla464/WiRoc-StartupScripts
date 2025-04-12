#!/usr/bin/env python3

from smbus2 import SMBus
import subprocess
import os
import yaml
import logging, logging.handlers

# Constants
I2CAddressRTC: int = 0x51
CONTROL_STATUS_2_REGADDR = 0x01
VL_SECONDS_REGADDR = 0x02
DAY_ALARM_REGADDR = 0x0b

I2CAddressAXP209: int = 0x34
DATA_CACHE_0_REGADDR = 0x04
DATA_CACHE_1_REGADDR = 0x05
DATA_CACHE_2_REGADDR = 0x06
DATA_CACHE_3_REGADDR = 0x07
DATA_CACHE_4_REGADDR = 0x08
DATA_CACHE_5_REGADDR = 0x09
DATA_CACHE_6_REGADDR = 0x0A
DATA_CACHE_7_REGADDR = 0x0B
DATA_CACHE_8_REGADDR = 0x0C
DATA_CACHE_9_REGADDR = 0x0D
DATA_CACHE_10_REGADDR = 0x0E
DATA_CACHE_11_REGADDR = 0x0F

ADC_REGADDR = 0x82

BT_ADDRESS_MAGIC_CONSTANT = 0xAA

# Global variables
Logger = None
I2CBus: SMBus = None
WiRocHWVersion: str = ""
WiRocHWVersionNumber: int = 0
WiRocHWRevisionNumber: int = 0


def Init() -> None:
    logging.basicConfig(level=logging.ERROR,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        filename='Startup.log',
                        filemode='a')
    logging.raiseExceptions = False
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    rotFileHandler = logging.handlers.RotatingFileHandler('Startup.log', maxBytes=20000000, backupCount=5)
    rotFileHandler.doRollover()
    rotFileHandler.setFormatter(formatter)

    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)

    # add the handler to the myLogger
    global Logger
    Logger = logging.getLogger('Startup')
    Logger.setLevel(logging.INFO)
    Logger.propagate = False
    Logger.addHandler(rotFileHandler)
    Logger.addHandler(console)

    Logger.info("Start")

    with open("/home/chip/settings.yaml", "r") as f:
        settings = yaml.load(f, Loader=yaml.BaseLoader)
    global WiRocHWVersion
    WiRocHWVersion = settings['WiRocHWVersion']
    WiRocHWVersion = WiRocHWVersion.strip()
    global WiRocHWVersionNumber
    WiRocHWVersionNumber = int(WiRocHWVersion.split("Rev")[0][1:])
    global WiRocHWRevisionNumber
    WiRocHWRevisionNumber = int(WiRocHWVersion.split("Rev")[1])

    global I2CBus
    I2CBus = SMBus(0)  # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
    Logger.info("Init() End")
    return None


def disableGadgetSerialOnUSB() -> None:
    Logger.info("disableGadgetSerialOnUSB() Start")
    # Disable the gadget serial console on usb
    status = subprocess.check_output("systemctl disable serial-getty@ttyGS0.service", shell=True)
    Logger.info(f"systemctl disable serial-getty@ttyGS0.service | returned status {status}")
    status = subprocess.check_output("systemctl stop serial-getty@ttyGS0.service", shell=True)
    Logger.info(f"systemctl stop serial-getty@ttyGS0.service | returned status {status}")
    Logger.info("disableGadgetSerialOnUSB() End")
    return None

def enableBatteryADC() -> None:
    Logger.info("enableBatteryADC() Start")
    I2CBus.write_byte_data(I2CAddressAXP209, ADC_REGADDR, 0xC3, force=True)
    Logger.info("enableBatteryADC() End")

def clearRTCAlarm() -> None:
    Logger.info("clearRTCAlarm() Start")
    # Clear the RTC alarm
    # Disable the alarm interrupt (as well as: clear the alarm flag, timer flag, disable timer interrupt and set TI_TP (timer interrupt, timer pulse) to timer interrupt mode)
    I2CBus.write_byte_data(I2CAddressRTC, CONTROL_STATUS_2_REGADDR, 0x00, force=True)

    # We use Day_alarm register to indicate that the alarm interrupt should be enabled when WiRoc is shut down.
    # This is because if the alarm goes off when WiRoc is running then it will be shut down.
    # Let's clear this to force the user to enable the alarm again if he wants it enabled
    I2CBus.write_byte_data(I2CAddressRTC, DAY_ALARM_REGADDR, 0x00, force=True)
    Logger.info("clearRTCAlarm() End")
    return None


def initRTCModuleAndSetSystemTime() -> None:
    Logger.info("initRTCModuleAndSetSystemTime() Start")
    # Clear the VL flag
    seconds = I2CBus.read_byte_data(I2CAddressRTC, VL_SECONDS_REGADDR, force=True)
    I2CBus.write_byte_data(I2CAddressRTC, VL_SECONDS_REGADDR, 0x7F & seconds, force=True)

    if not os.path.exists("/dev/rtc1"):
        try:
            status = subprocess.check_output("echo pcf8563 0x51 > /sys/class/i2c-adapter/i2c-0/new_device", shell=True)
            Logger.info(f"echo pcf8563 0x51 > /sys/class/i2c-adapter/i2c-0/new_device | returned status {status}")
        except Exception as ex:
            Logger.error(f"echo pcf8563 0x51 > /sys/class/i2c-adapter/i2c-0/new_device | throw exception {ex}")
    # Seems hwclock uses /dev/rtc0 directly and ignoring /dev/rtc
    #status = subprocess.check_output("ln -f -s /dev/rtc1 /dev/rtc", shell=True)
    #Logger.info(f"ln -f -s /dev/rtc1 /dev/rtc | returned status {status}")

    # restore system time from hardware clock
    status = subprocess.check_output("hwclock -f /dev/rtc1 --hctosys", shell=True)
    Logger.info(f"hwclock --hctosys | returned status {status}")
    Logger.info("initRTCModuleAndSetSystemTime() End")
    return None


def getBluetoothAddressSettings() -> tuple[str, bool]:
    Logger.info("getBluetoothAddressSettings() Start")
    f = open("/home/chip/settings.yaml", "r")
    settings = yaml.load(f, Loader=yaml.BaseLoader)
    f.close()

    btAddressSettings = None
    writeBluetoothAddressToAXP209 = False
    if "BluetoothAddress" in settings:
        btAddressSettings = settings["BluetoothAddress"]
    if "WriteBluetoothAddressToAXP209" in settings:
        writeBluetoothAddressToAXP209 = settings["WriteBluetoothAddressToAXP209"] == "True"

    Logger.info(f"getBluetoothAddressSettings() End: ({btAddressSettings}, {writeBluetoothAddressToAXP209})")
    return btAddressSettings, writeBluetoothAddressToAXP209


def setBluetoothAddressInSettings(btAddress: str) -> None:
    Logger.info("setBluetoothAddressSettings() Start")
    with open("/home/chip/settings.yaml", "r") as f1:
        settings = yaml.load(f1, Loader=yaml.BaseLoader)

    settings["BluetoothAddress"] = btAddress
    with open('/home/chip/settings.yaml', 'w') as f2:
        yaml.dump(settings, f2)  # Write a YAML representation of data to 'settings.yaml'.
    Logger.info("setBluetoothAddressSettings() End")
    return None


def clearWriteBluetoothAddressToAXP209() -> None:
    Logger.info("clearWriteBluetoothAddressToAXP209() Start")
    with open("/home/chip/settings.yaml", "r") as f1:
        settings = yaml.load(f1, Loader=yaml.BaseLoader)

    settings["WriteBluetoothAddressToAXP209"] = "False"
    with open('/home/chip/settings.yaml', 'w') as f2:
        yaml.dump(settings, f2)  # Write a YAML representation of data to 'settings.yaml'.
    Logger.info("clearWriteBluetoothAddressToAXP209() End")
    return None


def getBluetoothAddressFromAXP209() -> str | None:
    Logger.info("getBluetoothAddressFromAXP209() Start")
    magic_constant = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_0_REGADDR, force=True)
    if magic_constant == BT_ADDRESS_MAGIC_CONSTANT:
        Logger.info(f"getBluetoothAddressFromAXP209() Magic constant found in APX209 => So should have a BT Address saved")
        # We should have a BT Address saved in data cache
        btAddressByte1 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_1_REGADDR, force=True)
        btAddressByte2 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_2_REGADDR, force=True)
        btAddressByte3 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_3_REGADDR, force=True)
        btAddressByte4 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_4_REGADDR, force=True)
        btAddressByte5 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_5_REGADDR, force=True)
        btAddressByte6 = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_6_REGADDR, force=True)
        parityByte = I2CBus.read_byte_data(I2CAddressAXP209, DATA_CACHE_7_REGADDR, force=True)
        calculatedParityByte = btAddressByte1 ^ btAddressByte2 ^ btAddressByte3 ^ btAddressByte4 ^ btAddressByte5 ^ btAddressByte6
        Logger.info(f"getBluetoothAddressFromAXP209() ParityByte: {parityByte} CalculatedParityByte: {calculatedParityByte}")

        if parityByte == calculatedParityByte:
            Logger.info("getBluetoothAddressFromAXP209() ParityByte OK")
            bluetoothAddressAXP209 = f"{btAddressByte1:02X}:{btAddressByte2:02X}:{btAddressByte3:02X}:{btAddressByte4:02X}:{btAddressByte5:02X}:{btAddressByte6:02X}"
            Logger.info(f"getBluetoothAddressFromAXP209() End: {bluetoothAddressAXP209}")
            return bluetoothAddressAXP209
    Logger.info("getBluetoothAddressFromAXP209() End: None")
    return None


def getBluetoothAddressFromDevice() -> str | None:
    Logger.info("getBluetoothAddressFromDevice() Start")
    subP = os.popen("hcitool dev")
    hcitoolResp = subP.read()
    hcitoolResp = hcitoolResp.replace("Devices:", "")
    subP.close()
    hcitoolResp = hcitoolResp.strip()
    hcitoolRespWords = hcitoolResp.split()
    if len(hcitoolRespWords) > 1 and len(hcitoolRespWords[1]) == 17:
        btAddress = hcitoolRespWords[1]
        Logger.info("getBluetoothAddressFromDevice() End: {btAddress}")
        return btAddress
    Logger.info("getBluetoothAddressFromDevice() End: None")
    return None


def setBluetoothAddressInAXP209(btAddressString: str) -> None:
    Logger.info(f"setBluetoothAddressInAXP209() Start: {btAddressString}")
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_0_REGADDR, BT_ADDRESS_MAGIC_CONSTANT, force=True)
    btAddressStringArray = btAddressString.split(':')
    btAddressByte1 = int(btAddressStringArray[0], 16)
    btAddressByte2 = int(btAddressStringArray[1], 16)
    btAddressByte3 = int(btAddressStringArray[2], 16)
    btAddressByte4 = int(btAddressStringArray[3], 16)
    btAddressByte5 = int(btAddressStringArray[4], 16)
    btAddressByte6 = int(btAddressStringArray[5], 16)

    # We should have a BT Address saved in data cache
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_1_REGADDR, btAddressByte1, force=True)
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_2_REGADDR, btAddressByte2, force=True)
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_3_REGADDR, btAddressByte3, force=True)
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_4_REGADDR, btAddressByte4, force=True)
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_5_REGADDR, btAddressByte5, force=True)
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_6_REGADDR, btAddressByte6, force=True)

    calculatedParityByte = btAddressByte1 ^ btAddressByte2 ^ btAddressByte3 ^ btAddressByte4 ^ btAddressByte5 ^ btAddressByte6
    Logger.info(f"setBluetoothAddressInAXP209() calculatedParityByte: {calculatedParityByte}")
    I2CBus.write_byte_data(I2CAddressAXP209, DATA_CACHE_7_REGADDR, calculatedParityByte, force=True)

    Logger.info("setBluetoothAddressInAXP209() End")
    return None


def getBluetoothAddressToUseAndSyncronizeSettingAndAXP209():
    Logger.info("getBluetoothAddressToUseAndSyncronizeSettingAndAXP209() Start")
    btAddressSettings, writeBluetoothAddressToAXP209 = getBluetoothAddressSettings()
    if btAddressSettings is not None and writeBluetoothAddressToAXP209:
        setBluetoothAddressInAXP209(btAddressSettings)
        clearWriteBluetoothAddressToAXP209()
        Logger.info(f"getBluetoothAddressToUseAndSyncronizeSettingAndAXP209() End:  btAddressSettings: {btAddressSettings}")
        return btAddressSettings

    btAddressAXP209 = getBluetoothAddressFromAXP209()
    if btAddressAXP209 is not None:
        # write the bt address to settings
        if btAddressAXP209 != btAddressSettings:
            setBluetoothAddressInSettings(btAddressAXP209)
        Logger.info(f"getBluetoothAddressToUseAndSyncronizeSettingAndAXP209() End: btAddressAXP209: {btAddressAXP209}")
        return btAddressAXP209
    Logger.info("getBluetoothAddressToUseAndSyncronizeSettingAndAXP209() End: None")
    return None


def configureBluetoothAddress() -> None:
    Logger.info("configureBluetoothAddress() Start")
    btAddressToUse = getBluetoothAddressToUseAndSyncronizeSettingAndAXP209()
    btAddressDevice = getBluetoothAddressFromDevice()
    if btAddressToUse is None:
        # No bt address is configured, then we should try to use the default one and
        # hope it is not used by any other previous WiRoc device
        if btAddressDevice is not None:
            Logger.info(f"configureBluetoothAddress() set bt address in AXP209")
            setBluetoothAddressInAXP209(btAddressDevice)
            Logger.info(f"configureBluetoothAddress() set bt address in settings")
            setBluetoothAddressInSettings(btAddressDevice)
    elif btAddressToUse != btAddressDevice:
        # Change the bluetooth address of the WiRoc
        status = subprocess.check_output("hciconfig hci0 down", shell=True)
        Logger.info(f"configureBluetoothAddress() hciconfig hci0 down | response: {status}")
        status = subprocess.check_output(f"btmgmt public-addr {btAddressToUse}", shell=True)
        Logger.info(f"configureBluetoothAddress() btmgmt public-addr {btAddressToUse} | response: {status}")
        status = subprocess.check_output("hciconfig hci0 up", shell=True)
        Logger.info(f"configureBluetoothAddress() hciconfig hci0 up | response: {status}")
    Logger.info("configureBluetoothAddress() End")


def main():
    Init()
    enableBatteryADC()
    disableGadgetSerialOnUSB()
    if WiRocHWVersionNumber >= 7:
        clearRTCAlarm()
        initRTCModuleAndSetSystemTime()
    configureBluetoothAddress()
    Logger.info("main() End")


if __name__ == '__main__':
    main()
