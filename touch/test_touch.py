#!/usr/bin/env python3
import argparse, csv, math, os, sys, time, statistics
import pygame
from evdev import InputDevice, categorize, ecodes
from select import select

# Utility: try to auto-pick a touchscreen device with MT ABS positions
def autodetect_device():
    candidates = []
    for node in sorted(os.listdir('/dev/input')):
        if not node.startswith('event'):
            continue
        path = f'/dev/input/{node}'
        try:
            dev = InputDevice(path)
            caps = dev.capabilities(absinfo=True)
            abs_caps = caps.get(ecodes.EV_ABS, [])
            has_x = any(code == ecodes.ABS_MT_POSITION_X for code, _ in abs_caps)
            has_y = any(code == ecodes.ABS_MT_POSITION_Y for code, _ in abs_caps)
            if has_x and has_y:
                candidates.append((dev.name or 'unknown', path))
            dev.close()
        except Exception:
            pass
    return candidates[0][1] if candidates else None

class TouchState:
    def __init__(self, max_slots=10):
        self.max_slots = max_slots
        self.slots = {i: {
            'active': False,
            'id': None,
            'x': None,
            'y': None,
            'trail': [],
            'last_ts': None,
            'intervals': []
        } for i in range(max_slots)}
        self.cur_slot = 0
        self.abs_x_range = (0, 4095)
        self.abs_y_range = (0, 4095)
        self.event_times = []
        self.down_times = {}

    def set_range(self, xinfo, yinfo):
        if xinfo: self.abs_x_range = (xinfo.min, xinfo.max)
        if yinfo: self.abs_y_range = (yinfo.min, yinfo.max)

    def update_interval(self, slot, ts):
        last = self.slots[slot]['last_ts']
        if last is not None:
            self.slots[slot]['intervals'].append(ts - last)
        self.slots[slot]['last_ts'] = ts

TARGETS = {
    'center': (0.5, 0.5),
    'top':    (0.5, 0.08),
    'bottom': (0.5, 0.92),
    'left':   (0.08, 0.5),
    'right':  (0.92, 0.5)
}

COLORS = [
    (200,60,60), (60,200,60), (60,60,200), (200,160,60), (160,60,200),
    (60,200,200), (200,60,160), (120,120,120), (240,120,40), (40,240,120)
]

class Tester:
    def __init__(self, device_path, log_path, tolerance_px=20, max_slots=10):
        self.dev = InputDevice(device_path)
        self.log_path = log_path
        self.touch = TouchState(max_slots=max_slots)
        abs_caps = self.dev.capabilities(absinfo=True).get(ecodes.EV_ABS, [])
        xinfo = yinfo = None
        for code, ai in abs_caps:
            if code == ecodes.ABS_MT_POSITION_X: xinfo = ai
            if code == ecodes.ABS_MT_POSITION_Y: yinfo = ai
        self.touch.set_range(xinfo, yinfo)
        self.cur_slot = 0
        self.tolerance_px = tolerance_px
        self.writer = None
        if log_path:
            self.logf = open(log_path, 'w', newline='')
            self.writer = csv.writer(self.logf)
            self.writer.writerow(['ts','slot','tracking_id','x','y','type'])
        else:
            self.logf = None

    def close(self):
        try:
            if self.logf: self.logf.close()
            self.dev.close()
        except Exception:
            pass

    def run(self):
        pygame.init()
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
        screen = pygame.display.set_mode((0,0), flags)
        pygame.mouse.set_visible(False)
        width, height = screen.get_size()
        clock = pygame.time.Clock()

        # Precompute target pixels
        targets_px = {name: (int(x*width), int(y*height)) for name,(x,y) in TARGETS.items()}
        recent_taps = []  # list of (name, dist_px, ts)

        running = True
        while running:
            # Handle quit
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False

            # Read evdev without blocking UI
            r,_,_ = select([self.dev.fd], [], [], 0)
            if r:
                for e in self.dev.read():
                    ts = time.monotonic()
                    if e.type == ecodes.EV_ABS:
                        if e.code == ecodes.ABS_MT_SLOT:
                            self.cur_slot = int(e.value)
                            if self.cur_slot not in self.touch.slots:
                                # expand slots dict if needed
                                self.touch.slots[self.cur_slot] = {
                                    'active': False,'id':None,'x':None,'y':None,'trail':[],
                                    'last_ts': None,'intervals':[]}
                        elif e.code == ecodes.ABS_MT_TRACKING_ID:
                            sid = self.cur_slot
                            if e.value == -1:
                                # finger up
                                self.touch.slots[sid]['active'] = False
                                self.touch.slots[sid]['id'] = None
                            else:
                                # finger down
                                self.touch.slots[sid]['active'] = True
                                self.touch.slots[sid]['id'] = int(e.value)
                                self.touch.slots[sid]['trail'] = []
                                self.touch.update_interval(sid, ts)
                        elif e.code == ecodes.ABS_MT_POSITION_X:
                            sid = self.cur_slot
                            self.touch.slots[sid]['x'] = self._scale(e.value, self.touch.abs_x_range, width)
                            self.touch.update_interval(sid, ts)
                        elif e.code == ecodes.ABS_MT_POSITION_Y:
                            sid = self.cur_slot
                            self.touch.slots[sid]['y'] = self._scale(e.value, self.touch.abs_y_range, height)
                            self.touch.update_interval(sid, ts)
                    elif e.type == ecodes.EV_SYN and e.code == ecodes.SYN_REPORT:
                        # after a frame, push position to trail and log
                        active_slots = [s for s in self.touch.slots.values() if s['active'] and s['x'] is not None and s['y'] is not None]
                        for sid, s in self.touch.slots.items():
                            if s['active'] and s['x'] is not None:
                                s['trail'].append((s['x'], s['y']))
                                if len(s['trail']) > 64:
                                    s['trail'] = s['trail'][-64:]
                                if self.writer:
                                    self.writer.writerow([ts, sid, s['id'], s['x'], s['y'], 'move'])
                        # Detect taps near targets on finger up
                        # We approximate a tap when a slot just became inactive; check last position
                        pass
                    # Successful taps: track with KEY events if present
                    if e.type == ecodes.EV_KEY and e.code == ecodes.BTN_TOUCH:
                        # 1 is down, 0 is up. On up, check nearest target
                        if e.value == 0:
                            # find last active or most recent slot with a coordinate
                            best = None
                            for name, (tx,ty) in targets_px.items():
                                for s in self.touch.slots.values():
                                    if s['x'] is None or s['y'] is None: continue
                                    dist = math.hypot(s['x']-tx, s['y']-ty)
                                    if best is None or dist < best[1]:
                                        best = (name, dist)
                            if best:
                                recent_taps.append((best[0], best[1], time.monotonic()))
                                if len(recent_taps) > 20:
                                    recent_taps = recent_taps[-20:]
                        # log
                        if self.writer:
                            self.writer.writerow([time.monotonic(), self.cur_slot, self.touch.slots[self.cur_slot]['id'],
                                                  self.touch.slots[self.cur_slot]['x'], self.touch.slots[self.cur_slot]['y'],
                                                  'down' if e.value==1 else 'up'])

            # Draw
            screen.fill((12,12,12))
            # draw targets
            for name,(tx,ty) in targets_px.items():
                pygame.draw.circle(screen, (180,180,180), (tx,ty), 18, 2)
                label = pygame.font.SysFont(None, 24).render(name, True, (180,180,180))
                screen.blit(label, (tx-30, ty-36))

            # draw touches
            for idx,(sid,s) in enumerate(self.touch.slots.items()):
                if s['x'] is None or s['y'] is None: continue
                col = COLORS[sid % len(COLORS)]
                # trail
                if s['trail']:
                    pygame.draw.lines(screen, col, False, s['trail'], 2)
                # point
                pygame.draw.circle(screen, col, (int(s['x']), int(s['y'])), 12, 3)
                tag = pygame.font.SysFont(None, 24).render(f"S{sid} id {s['id']}", True, col)
                screen.blit(tag, (int(s['x'])+14, int(s['y'])+14))

            # HUD
            hud = self._make_hud(width, height, recent_taps)
            for i,line in enumerate(hud):
                color = (220,220,220)
                if line.startswith('WARN') or line.startswith('FAIL'): color = (220,80,80)
                text = pygame.font.SysFont(None, 26).render(line, True, color)
                screen.blit(text, (16, 16 + i*22))

            pygame.display.flip()
            clock.tick(120)
        self.close()

    def _scale(self, v, rng, maxpix):
        lo, hi = rng
        if hi <= lo: return 0
        return int((v - lo) * (maxpix - 1) / (hi - lo))

    def _make_hud(self, w, h, recent_taps):
        # Compute report rate and jitter per active slot
        lines = []
        lines.append(f"Device: {self.dev.name}  ({self.dev.fn})  resX {self.touch.abs_x_range} resY {self.touch.abs_y_range}")
        active = [ (sid,s) for sid,s in self.touch.slots.items() if s['active'] ]
        if not active:
            lines.append("Touch: idle. Tap targets: center, top, bottom, left, right.")
        for sid,s in active:
            hz = 0.0
            if len(s['intervals']) >= 5:
                med = statistics.median(s['intervals'][-30:])
                if med > 0: hz = 1.0/med
                jitter = statistics.pstdev(s['intervals'][-30:])
            else:
                med = 0
                jitter = 0
            warn = []
            if hz and hz < 60: warn.append('low Hz')
            if jitter and jitter > 0.003: warn.append('jitter')
            pos = (s['x'], s['y']) if s['x'] is not None else ('-','-')
            status = f"S{sid} id {s['id']} pos {pos} rate {hz:.1f}Hz jitter {jitter*1000:.2f}ms"
            if warn:
                status = "WARN " + ", ".join(warn) + " | " + status
            lines.append(status)
        # Tap accuracy summary
        if recent_taps:
            last_name, last_dist, last_ts = recent_taps[-1]
            verdict = "PASS" if last_dist <= self.tolerance_px else "FAIL edge/center accuracy"
            if verdict.startswith('FAIL'):
                lines.append(f"FAIL tap {last_name} dist {last_dist:.1f}px (tol {self.tolerance_px}px)")
            else:
                lines.append(f"PASS tap {last_name} dist {last_dist:.1f}px")
        # Multi-touch count
        active_count = sum(1 for _,s in active)
        if active_count >= 3:
            lines.append("PASS multi-touch >=3 active")
        elif active_count == 2:
            lines.append("OK two-finger active; add third to pass full MT goal")
        return lines

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Touchscreen test UI + logger')
    ap.add_argument('--device', help='evdev node (e.g., /dev/input/event2). If omitted, autodetect.')
    ap.add_argument('--log', default='', help='CSV log path (optional)')
    ap.add_argument('--tolerance', type=int, default=20, help='tap accuracy tolerance in pixels')
    args = ap.parse_args()

    dev = args.device or autodetect_device()
    if not dev:
        print('No multitouch device found. Specify --device.')
        sys.exit(1)

    tester = Tester(dev, args.log, tolerance_px=args.tolerance)
    try:
        tester.run()
    finally:
        tester.close()
