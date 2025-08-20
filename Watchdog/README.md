# Watchdog

This README covers installation and quick usage of the `watchdog` utility.

## Install

Install the binary into `/usr/local/sbin` with executable permissions:

sudo install -m 0755 watchdog /usr/local/sbin/watchdog

## Permissions (I²C access)

If you encounter permission errors accessing I²C devices, add your user to the `i2c` group and create a udev rule:

sudo usermod -aG i2c $USER
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' | sudo tee /etc/udev/rules.d/10-i2c.rules
sudo udevadm control --reload

Log out and back in so the new group membership takes effect.

## Quick manual use

Disable it immediately:
sudo watchdog disable

Enable it:
sudo watchdog enable

Check current status:
watchdog status

## Add /usr/local/bin to your PATH (recommended)

Edit ~/.bashrc and add:
export PATH="$PATH:/usr/local/bin:/usr/local/sbin"

Reload your shell configuration:
source ~/.bashrc

Now anything placed in /usr/local/bin or /usr/local/sbin can be run without specifying the full path.
