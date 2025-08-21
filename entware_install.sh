#!/bin/sh
# Installing Entware on Huawei E5186
# To install, you need to install a modified firmware with telnet enabled.
# 
# connect to the router:
# adb connect 192.168.8.1
# 
# Copy the script to the router
# adb push entware_install.sh /tmp/entware_install.sh
# 
# Connect to the router via telnet (address 192.168.8.1, port 23),
# give the script execution rights and run it:
# cd /tmp
# chmod 755 entware_install.sh
# ./entware_install.sh

unset LD_LIBRARY_PATH
unset LD_PRELOAD

echo "Info: Checking for prerequisites and creating folders..."

if [ -d "/data/opt" ]
  then
    echo "Warning: Folder /data/opt exists!"
  else
    mkdir /data/opt
fi

mount /data/opt /opt

echo "0"> /var/dns/ipv6

# no need to create many folders. entware-opt package creates most
for folder in bin etc lib/opkg share tmp var/lock
do
  if [ -d "/opt/$folder" ]
  then
    echo "Warning: Folder /opt/$folder exists!"
    echo "Warning: If something goes wrong please clean /opt folder and try again."
  else
    mkdir -p /opt/$folder
  fi
done

echo "Info: Opkg package manager deployment..."
DLOADER="ld-linux.so.3"
URL=/armv7sf-k2.6/installer
SITE=bin.entware.net
wget -g -l /opt/bin/opkg -r $URL/opkg $SITE 
chmod 755 /opt/bin/opkg
wget -g -l /opt/etc/opkg.conf -r $URL/opkg.conf $SITE 
wget -g -l /opt/lib/ld-2.23.so -r $URL/ld-2.23.so $SITE 
wget -g -l /opt/lib/libc-2.23.so -r $URL/libc-2.23.so $SITE 
wget -g -l /opt/lib/libgcc_s.so.1 -r $URL/libgcc_s.so.1 $SITE 
wget -g -l /opt/lib/libpthread-2.23.so -r $URL/libpthread-2.23.so $SITE 
cd /opt/lib
chmod 755 ld-2.23.so
ln -s ld-2.23.so $DLOADER
ln -s libc-2.23.so libc.so.6
ln -s libpthread-2.23.so libpthread.so.0

echo "Info: Dependency download ..."

URL=/binaries/armv7
SITE=pkg.entware.net

wget -g -l /tmp/busybox.ipk -r $URL/busybox_1.27.2-2_armv7soft.ipk $SITE
wget -g -l /tmp/libgcc.ipk -r $URL/libgcc_6.3.0-6_armv7soft.ipk $SITE
wget -g -l /tmp/libc.ipk -r $URL/libc_2.23-6_armv7soft.ipk  $SITE
wget -g -l /tmp/libssp.ipk -r $URL/libssp_6.3.0-6_armv7soft.ipk  $SITE
wget -g -l /tmp/librt.ipk -r $URL/librt_2.23-6_armv7soft.ipk  $SITE
wget -g -l /tmp/libpthread.ipk -r $URL/libpthread_2.23-6_armv7soft.ipk $SITE

export PATH="/opt/bin:/opt/sbin:$PATH"

echo "Info: Dependency installation ..."
opkg install /tmp/libgcc.ipk
opkg install /tmp/libc.ipk
opkg install /tmp/libssp.ipk
opkg install /tmp/libpthread.ipk
opkg install /tmp/librt.ipk
opkg install /tmp/busybox.ipk

echo "Info: Basic packages installation..."
opkg update
opkg install entware-opt

# Fix for multiuser environment
chmod 777 /opt/tmp

# now try create symlinks - it is a std installation
if [ -f /etc/passwd ]
then
    ln -sf /etc/passwd /opt/etc/passwd
else
    cp /opt/etc/passwd.1 /opt/etc/passwd
fi

mount -o remount,rw /app

echo '
#!/bin/sh
#

#Entware start
mount /data/opt /opt
export PATH="/opt/bin:/opt/sbin:$PATH"
/opt/etc/init.d/rc.unslung start
echo "Entware start!"

# Created by kolyanok 4PDA.ru

busybox grep -q "root::" /app/bin/passwd
if [ $? -eq 1 ]; then
    if [ ! -d /data/root-home ]; then
        mkdir /data/root-home
    fi
    if [ ! -f /data/root-home/.profile ]; then
        busybox echo "cd /" > /data/root-home/.profile
    fi
    busybox echo -en "#!/bin/sh\n\n/bin/busybox login -p" > /login.sh
    chmod 777 /login.sh
    /usr/sbin/utelnetd -d -i br0 -p 23 -l /login.sh
else
    if [ -f /opt/bin/sh ]; then
        /usr/sbin/utelnetd -d -i br0 -p 23 -l /opt/bin/sh
    else
        /usr/sbin/utelnetd -d -i br0 -p 23 -l /bin/sh
    fi
    /usr/sbin/adbd &
fi
iptables -P FORWARD DROP
busybox sleep 10
iptables -t mangle -A POSTROUTING -j TTL --ttl-set 64
iptables -P FORWARD ACCEPT

'> /app/bin/autorun.sh

mount -o remount,ro /app

echo "Info: Congratulations!"
echo "Info: If there are no errors above then Entware was successfully initialized."
echo "Info: Add /opt/bin & /opt/sbin to your PATH variable"
echo "Info: Add '/opt/etc/init.d/rc.unslung start' to startup script for Entware services to start"
echo "Info: Found a Bug? Please report at https://github.com/Entware/Entware/issues"

cd
/opt/bin/sh
