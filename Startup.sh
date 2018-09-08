#!/bin/sh

echo "Beginning Startup.sh" >> /home/chip/startup.log
systemctl stop bluetooth
systemctl disable bluetooth
hciconfig hci0 up
if [[ $(hostname -s) = nanopiair ]]; then
    # Enable battery monitoring, percentage calculation; (Battery current ADC Enable)
    sudo i2cset -y -f 0 0x34 0x82 0xC3﻿﻿
else
    /home/chip/WiRoc-StartupScripts/setGPIOuart2
fi
systemctl disable serial-getty@ttyGS0.service
systemctl stop serial-getty@ttyGS0.service
echo "End Startup.sh" >> /home/chip/startup.log
