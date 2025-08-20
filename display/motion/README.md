
---

## Troubleshooting

- **"TypeError: Couldn't find foreign struct converter for 'cairo.Context'"**
  Install both `python3-cairo` and `python3-gi-cairo` inside the runner container.

- **Black screen or nothing draws**
  Check that `-v /tmp:/tmp` is mounted and `XDG_RUNTIME_DIR` points to the correct directory that contains `wayland-0`.
  Verify `ls -l /tmp/1000-runtime-dir/wayland-0` inside the runner container.

- **Permission denied on Wayland socket**
  Run the container as the same UID as the Weston user (typically `--user 1000:1000`).

- **"No protocol specified" or GTK falls back**
  Ensure `GDK_BACKEND=wayland` is set. If the target board only offers Wayland, X11 won’t work.

- **Slow/tearing**
  Lower `--fps` or `--speed`. Confirm the device GPU/DRM node is passed via `--device /dev/dri`.

---

## Development Notes

- The script forces Wayland backend via `Gdk.set_allowed_backends("wayland")`.
- The gradient uses a repeating Cairo pattern for seamless wrap.
- The checkerboard snaps cell edges to integers to avoid blurry antialiasing.

---

