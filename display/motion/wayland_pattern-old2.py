#!/usr/bin/env python3
# Fullscreen moving test pattern on Wayland via GTK3 + Cairo + FPS overlay
# Examples:
#   XDG_RUNTIME_DIR=/tmp/1000-runtime-dir WAYLAND_DISPLAY=wayland-0 \
#   GDK_BACKEND=wayland ./wayland_pattern.py --pattern bars --speed 160 --fps 60

import gi, math, time, argparse, cairo
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

parser = argparse.ArgumentParser(description="Fullscreen moving test pattern with FPS.")
parser.add_argument("--pattern", choices=["bars","checker","gradient","solid-red","solid-green","solid-blue"],
                    default="bars")
parser.add_argument("--speed", type=float, default=120.0, help="pixels per second")
parser.add_argument("--fps", type=int, default=60, help="target frame rate")
parser.add_argument("--font", default="monospace", help="overlay font family")
parser.add_argument("--font-size", type=int, default=24, help="FPS text size")
args = parser.parse_args()

class PatternWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Test Pattern")
        self.fullscreen()
        self.connect("destroy", Gtk.main_quit)

        self.da = Gtk.DrawingArea()
        self.add(self.da)
        self.da.connect("draw", self.on_draw)
        self.show_all()

        # pattern state
        self.pattern = args.pattern
        self.speed = float(args.speed)

        # timing / fps state
        self.dt_target = 1.0 / max(1, int(args.fps))
        self.t_prev = time.monotonic()
        self.fps_last_t = self.t_prev
        self.fps_frames = 0
        self.fps_value = 0.0
        self.offset = 0.0

        GLib.timeout_add(int(self.dt_target * 1000), self.on_tick)

    def size(self):
        a = self.da.get_allocation()
        return max(1, a.width), max(1, a.height)

    def on_tick(self):
        now = time.monotonic()
        dt = now - self.t_prev
        self.t_prev = now

        # animation
        self.offset = (self.offset + self.speed * dt) % 10000.0

        # fps accounting (update ~2x per second)
        self.fps_frames += 1
        if (now - self.fps_last_t) >= 0.5:
            self.fps_value = self.fps_frames / (now - self.fps_last_t)
            self.fps_frames = 0
            self.fps_last_t = now

        self.da.queue_draw()
        return True

    def on_draw(self, widget, cr: cairo.Context):
        w, h = self.size()

        # background
        cr.set_source_rgb(0,0,0)
        cr.paint()

        # pattern
        if self.pattern == "bars":
            self.draw_bars(cr, w, h, self.offset)
        elif self.pattern == "checker":
            self.draw_checker(cr, w, h, self.offset)
        elif self.pattern == "gradient":
            self.draw_gradient(cr, w, h, self.offset)
        elif self.pattern == "solid-red":
            self.fill(cr, w, h, (1,0,0))
        elif self.pattern == "solid-green":
            self.fill(cr, w, h, (0,1,0))
        elif self.pattern == "solid-blue":
            self.fill(cr, w, h, (0,0,1))

        # fps overlay (top-left)
        self.draw_fps(cr, w, h)

        return False

    # -------- drawing primitives --------

    def fill(self, cr, w, h, rgb):
        cr.set_source_rgb(*rgb)
        cr.rectangle(0, 0, w, h)
        cr.fill()
    
    def draw_bars(self, cr, w, h, off):
        palette = [
            (1,1,1), (1,1,0), (0,1,1), (0,1,0),
            (1,0,1), (1,0,0), (0,0,1), (0.5,0.5,0.5)
        ]
        bars = len(palette)
        bw = max(1.0, w / bars)

        bar_shift = int(off // bw)      # full bars advanced
        shift = off % bw                # fractional pixel shift

        total = w + int(bw)             # extra width to cover edges
        for i in range(-1, int(math.ceil(total / bw)) + 1):
            color = palette[(i + bar_shift) % bars]  # cyclic palette
            x = i * bw - shift
            cr.set_source_rgb(*color)
            cr.rectangle(x, 0, bw + 1, h)
            cr.fill()

    def draw_checker(self, cr, w, h, off):
        cell = 40
        ox = off                   # smooth float motion
        oy = off * 0.6

        # Pre-shift the entire coordinate system
        for y in range(-cell, h + cell, cell):
            for x in range(-cell, w + cell, cell):
                # apply offset for drawing position
                xx = x - ox
                yy = y - oy

                # calculate the logical cell index (without modulo wrap)
                xi = int((x - ox) // cell)
                yi = int((y - oy) // cell)

                black = (xi + yi) & 1
                if black:
                    cr.set_source_rgb(0, 0, 0)
                else:
                    cr.set_source_rgb(1, 1, 1)

                cr.rectangle(xx, yy, cell, cell)
                cr.fill()
                
    def draw_gradient(self, cr, w, h, off):
        grad = cairo.LinearGradient(-(off % w), 0, w - (off % w), 0)
        grad.add_color_stop_rgb(0.00, 1, 0, 0)
        grad.add_color_stop_rgb(0.50, 0, 1, 0)
        grad.add_color_stop_rgb(1.00, 0, 0, 1)
        cr.set_source(grad)
        cr.rectangle(0, 0, w, h)
        cr.fill()

    def draw_fps(self, cr, w, h):
        text = f"{self.fps_value:5.1f} fps"
        # pick a sane font
        cr.select_font_face(args.font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(args.font_size)

        # measure text
        ext = cr.text_extents(text)
        pad = 8
        box_w = ext.width + 2*pad
        box_h = ext.height + 2*pad
        # background box with slight transparency
        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.rectangle(10, 10, box_w, box_h)
        cr.fill()
        # draw text
        cr.set_source_rgb(1, 1, 1)
        x = 10 + pad - ext.x_bearing
        y = 10 + pad - ext.y_bearing
        cr.move_to(x, y)
        cr.show_text(text)
        cr.stroke()

if __name__ == "__main__":
    # Force Wayland backend if available
    Gdk.set_allowed_backends("wayland")
    PatternWindow()
    Gtk.main()

