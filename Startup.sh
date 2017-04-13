#!/bin/sh

echo "Beginning Startup.sh" >> /home/chip/startup.log
systemctl stop bluetooth
systemctl disable bluetooth
hciconfig hci0 up
/home/chip/WiRoc-StartupScripts/setGPIOuart2
systemctl disable serial-getty@ttyGS0.service
echo "End Startup.sh" >> /home/chip/startup.log
