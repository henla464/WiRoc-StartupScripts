#!/bin/sh

echo "Beginning Startup.sh" >> /home/chip/startup.log
#hciconfig hci0 up
echo $(hostname -s) >> /home/chip/startup.log
if hostname -s | grep -q 'nanopiair';
then
    echo "enable battery monitoring" >> /home/chip/startup.log
    # Enable battery monitoring, percentage calculation; (Battery current ADC Enable)
    /usr/sbin/i2cset -y -f 0 0x34 0x82 0xC3
else
    echo "stop bluetooth" >> /home/chip/startup.log
    systemctl stop bluetooth
    systemctl disable bluetooth
    /home/chip/WiRoc-StartupScripts/setGPIOuart2
fi

systemctl disable serial-getty@ttyGS0.service
systemctl stop serial-getty@ttyGS0.service
echo "End Startup.sh" >> /home/chip/startup.log

