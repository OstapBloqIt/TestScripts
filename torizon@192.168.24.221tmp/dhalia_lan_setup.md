Perfect, thanks for digging. That directory confirms the suspicion: there’s **no `20-wired.network`** in your build, so nothing explicit is forcing DHCP. Which means your static config is *supposed* to win.

But the symptom (no IPv4 after boot, only IPv6LL) is still exactly what happens when the `[Address]` section isn’t actually applied at startup. On some Yocto/Torizon systemd builds, the resolver skips your static address unless you explicitly give it `ConfigureWithoutCarrier=yes`.

Let’s try that. Edit your `/etc/systemd/network/00-ethernet0.network` to this:

```ini
[Match]
Name=ethernet0

[Network]
Gateway=192.168.24.1
DNS=8.8.8.8
DHCP=no
IPv6AcceptRA=no
LinkLocalAddressing=no
ConfigureWithoutCarrier=yes

[Address]
Address=192.168.24.22/24
```

---

### Why this matters

* At boot, `systemd-networkd` waits for the link to come up (carrier detection). If it races or sees the NIC as “down,” it ignores your `[Address]` config.
* By setting `ConfigureWithoutCarrier=yes`, it will apply the static IPv4 regardless of link state. Then, when the cable comes up, it’s already bound.

---

### Steps

1. Update the file with the above.
2. Run:

   ```bash
   systemctl daemon-reload
   systemctl restart systemd-networkd
   ```

   (to test it works live).
3. Reboot.
4. Check again:

   ```bash
   ip addr show ethernet0
   ```

---

If this finally holds after reboot, problem solved.
If not, next level is to **mask `NetworkManager`** (`systemctl disable --now NetworkManager`) because Toradex sometimes leaves it enabled by default, fighting with `systemd-networkd`.

Do you want me to show you how to check if `NetworkManager` is even running on your Torizon build?
