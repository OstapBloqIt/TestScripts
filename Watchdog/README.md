Install it:
sudo install -m 0755 watchdog /usr/local/sbin/watchdog

If you get permissions whining from the kernel like a mall cop with a whistle, add yourself to the i2c group and/or fix udev:

sudo usermod -aG i2c $USER
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' | sudo tee /etc/udev/rules.d/10-i2c.rules
sudo udevadm control --reload


Log out/in for the group change, because Linux loves ceremony.


Quick manual use

Kill it now:

sudo watchdog disable


Bring it back from the dead:

sudo watchdog enable


Sanity check:

watchdog status

Add /usr/local/bin to your $PATH (recommended)

Edit ~/.bashrc and slap this line near the top or bottom:

export PATH=$PATH:/usr/local/bin:/usr/local/sbin


Reload:

source ~/.bashrc


Now anything you drop in /usr/local/bin or /usr/local/sbin will run without needing the full path.



