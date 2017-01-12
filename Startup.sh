#!/bin/sh

echo "Beginning Startup.sh" >> /home/chip/startup.log
systemctl stop bluetooth
systemctl disable bluetooth
hciconfig hci0 up
/home/chip/WiRoc-StartupScripts/setGPIOuart2
#systemctl stop getty@ttyGS0.service
#(cd /home/chip/WiRoc-Python-2 && exec python3 start.py)
#node /home/chip/WiRoc-BLE-Device/main.js &> /home/chip/WiRoc-BLE-Device.log &
echo "End Startup.sh" >> /home/chip/startup.log
