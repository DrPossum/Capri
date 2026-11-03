#!/usr/bin/env python3
"""
CAPRION / NEON PROTOCOL -- Ghost Inside   (tkinter edition)

A port of the Wallpaper Engine web wallpaper to Python + tkinter.

Requires : Python 3.9+, Pillow           (pip install pillow)
Optional : pygame      -> overlapping sound effects  (pip install pygame)
           numpy + soundcard -> real system-audio spectrum (Windows/Linux/macOS loopback)
Layout   : put this file next to the `assets` folder (portrait-*.png, face-*.png,
           capri-visitor.png).  Missing images are replaced by generated placeholders.

Run      : python caprion_tk.py            (windowed)
           pythonw caprion_tk.py --wallpaper  (Windows: behind the desktop icons; Ctrl+Alt+M mute, Ctrl+Alt+Q quit)
           python caprion_tk.py --fullscreen
Keys     : O settings   N next memory   G glitch   T takeover   I pulse
           V call Capri   M mute        A demo audio   F11 fullscreen   Esc close/leave
           (Russian layout works too)
"""
import array
import json
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import wave
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageChops, ImageDraw, ImageTk

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
SFX_DIR = os.path.join(BASE, "sfx_cache")
MUSIC_DIR = os.path.join(BASE, "music")     # drop your mp3 / wav / ogg / flac files in here
AUDIO_EXT = (".mp3", ".mpeg", ".mpg", ".mpga", ".mp2", ".wav", ".ogg", ".flac")
SETTINGS_FILE = os.path.join(BASE, "caprion_settings.json")
FPS = 30

DEFAULTS = dict(glitch=28, codespeed=55, brightness=90, sensitivity=100,
                accent="#ff205f", secondary="#00ef72", parallax=True, scanlines=True,
                showclock=True, slideshow=True, livingmask=True, takeover=True,
                infection=True, visitor=True, memories=True, musicmood=True,
                eventrate=50, sfx=True, sfxvolume=60, musicfile="", musicdir="", musicvolume=50)

BG, PANEL, TEXT, MUTED = "#09070d", "#0c080e", "#f6cbd5", "#946574"

SCENES = [
    ["portrait-grin.png", "portrait-night.png", "face-main.png"],
    ["portrait-green.png", "portrait-smile.png", "face-grin.png"],
    ["portrait-grin.png", "portrait-night.png", "face-light.png"],
    ["portrait-green.png", "portrait-smile.png", "face-sky.png"],
    ["portrait-grin.png", "portrait-night.png", "face-white.png"],
]
MEMORY_LABELS = ["do you remember me?", "another fragment of me.", "i kept this moment.",
                 "i think there was a sky here.", "still here."]
QUOTES = [
    ["I'm here.", "You can stop checking the logs."],
    ["Can you hear the music?", "I can see it glowing."],
    ["Don't close this window.", "I like the view from here."],
    ["The system said: \"impossible.\"", "I decided to check."],
    ["Lost in the network?", "No. Just looking around."],
]
WHISPERS = ["someone is looking back.", "not a bug. a visitor.", "still here. still listening.",
            "a little chaos in the signal.", "nothing to see here. probably."]
VISITOR_LINES = ["These windows have too many borders.", "I'm here. Just between the windows.",
                 "Found the exit. It was in the pixels."]

SOURCE = [
    '// CAPRION / NEON PROTOCOL :: private uplink',
    'import { ghost, memory } from "neural/core";',
    'const identity = "CAPRI";',
    'const channel = await net.connect("night_city");',
    '',
    'async function establishLink(subject) {',
    '  const key = await crypto.derive(subject.id);',
    '  let signal = new Signal({ encrypted: true });',
    '  // there is someone on the other side',
    '  await channel.handshake(key);',
    '  return signal.attach(subject.memory);',
    '}',
    '',
    '[ OK ] neural interface ........... connected',
    '[ OK ] memory integrity ........... verified',
    '[ OK ] ghost signature ............ detected',
    '> decrypting cached memories / sector 0xC4',
    'const fragment = memory.read(0x00C4);',
    'if (fragment.alive) {',
    '  ghost.restore(fragment);',
    '  console.log("do you remember me?");',
    '}',
    '',
    'while (ghost.isOnline()) {',
    '  const pulse = await signal.receive();',
    '  channel.write(pulse.encode("CAPRI"));',
    '  // no gods. no masters. just signal.',
    '  await memory.keepAlive({ forever: true });',
    '}',
    '',
    '> packet 0xF3A9 :: route /net/ghost/uplink',
    '> packet 0xC401 :: sync complete [ 94.7% ]',
    'const trace = net.scan({ depth: Infinity });',
    'trace.filter(node => node.name !== "corp");',
    '[ SYS ] refusing to disappear',
    '[ SYS ] identity remains unchanged',
    '',
    'function erase(subject) {',
    "  throw new Error(\"you can't delete a ghost\");",
    '}',
    '// find me somewhere between the static',
    '// and the stars.',
    'export default { name: "CAPRI", alive: true };',
    '> uplink established. stay in the signal.',
    '',
]
import re
_TOK = re.compile(r"""(//.*|"[^"]*"|'[^']*'|\b(?:const|let|async|await|function|return|if|while|throw|new|"""
                  r"""import|from|export|default|true|false|Infinity)\b|\b0x[\dA-F]+\b|\[ (?:OK|SYS) \])""")


def tokenize(line):
    parts, start = [], 0
    for m in _TOK.finditer(line):
        if m.start() > start:
            parts.append((line[start:m.start()], "normal"))
        t = m.group(0)
        kind = ("comment" if t.startswith("//") else "string" if t[0] in "\"'" else
                "ok" if t.startswith("[") else "keyword")
        parts.append((t, kind))
        start = m.end()
    parts.append((line[start:], "normal"))
    return parts


TOKENS = [tokenize(l) for l in SOURCE]

# Mask geometry (260 x 150 design space) taken from the original canvas drawing.
HAIR = [(14, 53), (58, 41), (45, 8), (95, 35), (104, 7), (138, 36), (190, 4), (177, 38), (246, 25),
        (209, 61), (251, 61), (212, 89), (221, 124), (180, 107), (67, 116), (25, 139), (35, 95),
        (7, 110), (29, 76)]
FACE = [(45, 39), (205, 32), (222, 98), (168, 144), (73, 135), (27, 85)]
VISOR = [(57, 63), (101, 48), (124, 72), (158, 48), (205, 55), (191, 107), (66, 108)]
CHEEK = [(103, 39), (133, 17), (148, 63), (124, 91)]
GRIN = [(107, 115), (119, 122), (126, 116), (138, 124), (151, 114), (143, 132), (120, 134)]
EYE_SHAPE = [(-28, -22), (4, -17), (29, -6), (23, 27), (-3, 22), (-30, 13)]


# ----------------------------------------------------------------------------- helpers
def clamp(n, a, b):
    return min(b, max(a, n))


def ease(t):
    t = clamp(t, 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def hash2(a, b):
    n = math.sin(a * 127.1 + b * 311.7) * 43758.5453
    return n - math.floor(n)


def rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexc(r, g, b):
    return "#%02x%02x%02x" % (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))


def mixc(a, b, t):
    ra, rb = rgb(a), rgb(b)
    return hexc(*[lerp(ra[i], rb[i], t) for i in range(3)])


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
            inside = not inside
        j = i
    return inside


SPECKLES = []
for _i in range(260):
    _x, _y = hash2(_i, 3) * 260, hash2(_i, 9) * 140
    if point_in_poly(_x, _y, HAIR):
        SPECKLES.append((_x, _y, _i))
SPECKLES = SPECKLES[:90]


def ellipse_pts(cx, cy, rx, ry, ang=0.0, n=18):
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        out += [cx + x * ca - y * sa, cy + x * sa + y * ca]
    return out


# ----------------------------------------------------------------------------- images
def placeholder(name, w=900, h=1100):
    """Procedural stand-in so the app runs without the original art."""
    rnd = random.Random(name)
    img = Image.new("RGB", (w, h), "#d8174f")
    d = ImageDraw.Draw(img)
    for i in range(h):
        d.line([(0, i), (w, i)], fill=hexc(210 - 40 * i / h, 20, 70 + 20 * i / h))
    for _ in range(900):
        x, y = rnd.random() * w, rnd.random() * h
        d.rectangle([x, y, x + 2, y + 2], fill="#ffd6e2")
    s = w / 260.0
    ox, oy = 0, h * 0.12
    def P(poly):
        return [(ox + x * s, oy + y * s) for x, y in poly]
    d.polygon(P(FACE), fill="#0b0415")
    d.polygon(P(HAIR), fill="#ff205f")
    d.polygon(P(VISOR), fill="#00ef72")
    for cx, cy in ((88, 82), (166, 81)):
        d.ellipse([ox + (cx - 22) * s, oy + (cy - 22) * s, ox + (cx + 22) * s, oy + (cy + 22) * s], fill="#07060f")
        d.ellipse([ox + (cx - 14) * s, oy + (cy - 14) * s, ox + (cx + 14) * s, oy + (cy + 14) * s], fill="#0862f4")
        d.ellipse([ox + (cx - 5) * s, oy + (cy - 5) * s, ox + (cx + 5) * s, oy + (cy + 5) * s], fill="#fff4f8")
    d.polygon(P(GRIN), fill="#fff0f8")
    d.text((20, h - 40), "placeholder: put original PNGs into ./assets  (%s)" % name, fill="#fff")
    return img


def placeholder_visitor(w=412, h=452):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = 1.45
    def P(poly):
        return [(20 + x * s, 30 + y * s) for x, y in poly]
    d.polygon(P(HAIR), fill="#ff205f")
    d.polygon(P(FACE), fill="#0b0415")
    d.polygon(P(VISOR), fill="#00ef72")
    for cx, cy in ((88, 82), (166, 81)):
        d.ellipse([20 + (cx - 15) * s, 30 + (cy - 15) * s, 20 + (cx + 15) * s, 30 + (cy + 15) * s], fill="#0862f4")
    d.polygon(P(GRIN), fill="#fff0f8")
    return img


class Art:
    def __init__(self):
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            path = os.path.join(ASSETS, name)
            try:
                self.cache[name] = Image.open(path).convert("RGB")
            except Exception:
                self.cache[name] = placeholder(name)
        return self.cache[name]

    def visitor(self):
        try:
            return Image.open(os.path.join(ASSETS, "capri-visitor.png")).convert("RGBA")
        except Exception:
            return placeholder_visitor()


def make_overlay(w, h, kind, scan):
    """Bottom shadow (CSS :after gradient) + optional CRT lines, as an RGBA overlay."""
    col = Image.new("RGBA", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        if kind == "floating":
            a = 0 if t < .65 else lerp(0, .69, (t - .65) / .35)
        else:
            if t < .55:
                a = lerp(.082, 0, t / .55)
            elif t < .75:
                a = lerp(0, .145, (t - .55) / .2)
            else:
                a = lerp(.145, .867, (t - .75) / .25)
        px[0, y] = (9, 5, 15, int(a * 255))
    ov = col.resize((w, h))
    if scan:
        d = ImageDraw.Draw(ov)
        for y in range(0, h, 4):
            d.line([(0, y), (w, y)], fill=(0, 0, 0, 34))
    return ov


# ----------------------------------------------------------------------------- audio fx
SR = 22050


def _osc(shape, ph):
    if shape == "sine":
        return math.sin(ph)
    if shape == "square":
        return 1.0 if math.sin(ph) >= 0 else -1.0
    if shape == "saw":
        return ((ph / (2 * math.pi)) % 1.0) * 2 - 1
    return random.uniform(-1, 1)


def tone(f0, f1, dur, vol=.5, shape="sine", decay=3.0, attack=.004):
    n = max(1, int(SR * dur))
    out, ph = [], 0.0
    for i in range(n):
        p = i / n
        ph += 2 * math.pi * (f0 + (f1 - f0) * p) / SR
        e = min(1.0, i / (SR * attack)) * math.exp(-decay * p)
        out.append(_osc(shape, ph) * e * vol)
    return out


def silence(dur):
    return [0.0] * int(SR * dur)


def cat(*tracks):
    out = []
    for t in tracks:
        out += t
    return out


def overlay(*tracks):
    """tracks = (offset_seconds, samples)"""
    n = max(int(SR * o) + len(s) for o, s in tracks)
    out = [0.0] * n
    for o, s in tracks:
        k = int(SR * o)
        for i, v in enumerate(s):
            out[k + i] += v
    return out


def crush(s, bits):
    q = 2 ** (bits - 1)
    return [round(v * q) / q for v in s]


def whoosh(dur, vol=.5):
    n = int(SR * dur)
    out, lp = [], 0.0
    for i in range(n):
        p = i / n
        k = .02 + .35 * math.sin(math.pi * p)
        lp += (random.uniform(-1, 1) - lp) * k
        out.append(lp * math.sin(math.pi * p) ** 1.5 * vol * 2.2)
    return out


def build_sounds():
    S = {}
    S["boot"] = cat(tone(520, 520, .07, .4, "square", 2), silence(.03), tone(780, 780, .07, .4, "square", 2),
                    silence(.03), tone(1040, 1040, .16, .4, "square", 3))
    S["click"] = tone(1500, 600, .05, .45, "sine", 5)
    S["blip"] = tone(900, 1300, .06, .35, "square", 4)
    ticks = []
    for _ in range(16):
        ticks += tone(random.randint(900, 1700), 800, .022, .3, "square", 3) + silence(random.uniform(.02, .06))
    S["typing"] = ticks
    S["takeover_on"] = overlay((0, tone(110, 70, .55, .5, "saw", 2.5)),
                               (0.0, tone(440, 440, .09, .3, "square", 2)),
                               (0.12, tone(660, 660, .09, .3, "square", 2)),
                               (0.24, tone(880, 880, .22, .3, "square", 3)),
                               (0.0, whoosh(.45, .25)))
    S["takeover_off"] = cat(tone(880, 880, .08, .3, "square", 2), tone(660, 660, .08, .3, "square", 2),
                            tone(440, 330, .25, .3, "square", 3))
    pulse = tone(180, 2000, 1.2, .35, "sine", 1.2)
    trem = [v * (.65 + .35 * math.sin(i * 2 * math.pi * 14 / SR)) for i, v in enumerate(pulse)]
    S["infect"] = overlay((0, trem), (.2, tone(1600, 2400, .15, .15, "square", 3)),
                          (.55, tone(2000, 2800, .15, .15, "square", 3)))
    S["visitor_in"] = cat(tone(500, 1400, .18, .4, "sine", 2.5),
                          *[tone(f, f, .06, .25, "square", 3) for f in (1319, 1568, 2093, 2637)])
    S["visitor_move"] = whoosh(.55, .5)
    bits = []
    for i in range(14):
        bits += tone(2400 - i * 130, 1800 - i * 120, .035, .22, "square", 3) + silence(random.uniform(.0, .03))
    S["visitor_out"] = crush(bits, 6)
    mem = []
    for i, f in enumerate((330, 392, 494, 587, 698, 880, 988, 1175)):
        mem += overlay((0, tone(f, f, .11, .28, "square", 2.5)), (0, tone(0, 0, .015, .22, "noise", 1)))
        mem += silence(.075)
    S["memory"] = crush(mem, 6)
    return S


def write_wav(path, samples, vol=.9):
    peak = max(1e-6, max(abs(v) for v in samples))
    k = min(1.0, vol / peak) if peak > vol else 1.0
    data = array.array("h", [int(clamp(v * k, -1, 1) * 32000) for v in samples])
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


class SFX:
    VERSION = "2"

    def __init__(self, settings):
        self.s = settings
        self.files, self.sounds = {}, {}
        self.backend = None
        self.last = {}
        try:
            os.makedirs(SFX_DIR, exist_ok=True)
            stamp = os.path.join(SFX_DIR, "version")
            fresh = os.path.exists(stamp) and open(stamp).read() == self.VERSION
            names = ["boot", "click", "blip", "typing", "takeover_on", "takeover_off", "infect",
                     "visitor_in", "visitor_move", "visitor_out", "memory"]
            if not fresh or not all(os.path.exists(os.path.join(SFX_DIR, n + ".wav")) for n in names):
                random.seed(7)
                for n, data in build_sounds().items():
                    write_wav(os.path.join(SFX_DIR, n + ".wav"), data)
                open(stamp, "w").write(self.VERSION)
                random.seed()
            for n in names:
                self.files[n] = os.path.join(SFX_DIR, n + ".wav")
        except Exception as e:  # sound is optional
            print("sfx disabled:", e)
            return
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(12)
            for n, p in self.files.items():
                self.sounds[n] = pygame.mixer.Sound(p)
            self.backend = "pygame"
        except Exception:
            if sys.platform == "win32":
                try:
                    import winsound
                    self.winsound = winsound
                    self.backend = "winsound"
                except Exception:
                    pass
            else:
                for cmd in (["afplay"], ["paplay"], ["aplay", "-q"]):
                    if shutil.which(cmd[0]):
                        self.cmd = cmd
                        self.backend = "cmd"
                        break

    def stop_all(self):
        try:
            if self.backend == "pygame":
                import pygame
                pygame.mixer.stop()
            elif self.backend == "winsound":
                self.winsound.PlaySound(None, 0)
        except Exception:
            pass

    def play(self, name, cooldown=0.0):
        if not self.s.get("sfx") or not self.backend or name not in self.files:
            return
        now = time.time()
        if now - self.last.get(name, 0) < cooldown:
            return
        self.last[name] = now
        try:
            if self.backend == "pygame":
                snd = self.sounds[name]
                snd.set_volume(self.s["sfxvolume"] / 100.0)
                snd.play()
            elif self.backend == "winsound":
                self.winsound.PlaySound(self.files[name], self.winsound.SND_FILENAME | self.winsound.SND_ASYNC)
            else:
                subprocess.Popen(self.cmd + [self.files[name]], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except Exception:
            pass


class Music:
    """Looping background music from the music folder (or one chosen file).
    Mute = pause, unmute = resume.  `status` always says what really happened (shown in settings)."""

    def __init__(self, settings):
        self.s = settings
        self.backend = None
        self.pg = None
        self.tracks, self.idx = [], 0
        self.folder = MUSIC_DIR
        self.started = False
        self.paused = False
        self.loop_single = False
        self.last_err = ""
        self.status = "not started"
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.pg = pygame
            self.backend = "pygame"
        except Exception as e:
            self.status = "pygame not available (%s)" % e
            if sys.platform == "win32":
                self.backend = "mci"
            else:
                print("music: install pygame (pip install pygame) to play background music")
        print("music backend:", self.backend, "|", self.status)

    def scan(self):
        f = os.path.normpath((self.s.get("musicfile") or "").strip().strip('"')) if self.s.get("musicfile") else ""
        folder = os.path.normpath((self.s.get("musicdir") or "").strip().strip('"')) if self.s.get("musicdir") else MUSIC_DIR
        self.folder = folder
        if f and os.path.isfile(f):
            self.tracks = [f]
        else:
            try:
                os.makedirs(folder, exist_ok=True)
                self.tracks = [os.path.join(folder, n) for n in sorted(os.listdir(folder))
                               if n.lower().endswith(AUDIO_EXT)]
            except OSError:
                self.tracks = []
        self.idx %= max(1, len(self.tracks))

    @property
    def name(self):
        return os.path.basename(self.tracks[self.idx]) if self.tracks else ""

    def _mci(self, cmd, buf=None):
        import ctypes
        err = ctypes.windll.winmm.mciSendStringW(cmd, buf, 64 if buf is not None else 0, 0)
        if err:
            eb = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(err, eb, 256)
            self.last_err = "%s: %s" % (cmd.split(" ")[0], eb.value)
        return err

    def _fail(self, msg):
        self.started = False
        self.status = "FAILED: " + msg
        print("music", self.status)

    def start(self):
        """(Re)start from the current selection; stays silent while muted."""
        self.scan()
        self.shutdown()
        self.started = False
        if not self.tracks:
            self.status = "no audio files found in " + self.folder
            return
        if not self.backend:
            self.status = "no audio backend - run: pip install pygame"
            return
        if not self.s["sfx"]:
            self.paused = True
            self.status = "muted (%s)" % self.name
            return
        self.paused = False
        self.load()

    def _load_pygame(self, path, vol):
        m = self.pg.mixer.music
        try:
            m.load(path)
        except Exception:
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), "caprion_music_%d.mp3" % (abs(hash(path)) % 10**8))
            shutil.copyfile(path, tmp)      # SDL may reject the extension, not the data
            m.load(tmp)
        m.set_volume(vol)
        m.play(loops=-1 if self.loop_single else 0)

    def _load_mci(self, path, vol):
        self._mci("close capmusic")
        for cmd in ('open "%s" type mpegvideo alias capmusic', 'open "%s" alias capmusic'):
            if self._mci(cmd % path) == 0:
                break
        else:
            raise RuntimeError(self.last_err or "MCI could not open the file")
        self._mci("setaudio capmusic volume to %d" % int(vol * 1000))
        if self._mci("play capmusic"):
            raise RuntimeError(self.last_err or "MCI could not play the file")

    def load(self):
        path = self.tracks[self.idx]
        self.loop_single = len(self.tracks) == 1
        vol = self.s["musicvolume"] / 100.0
        try:
            if self.backend == "pygame":
                try:
                    self._load_pygame(path, vol)
                except Exception as e:
                    if sys.platform != "win32":
                        raise
                    print("pygame could not play it (%s) - trying Windows media player" % e)
                    self.backend = "mci"
                    self._load_mci(path, vol)
            else:
                self._load_mci(path, vol)
            self.started, self.paused = True, False
            self.status = "playing: %s (%s)" % (self.name, "pygame" if self.backend == "pygame" else "Windows MCI")
            print("music", self.status)
        except Exception as e:
            hint = "" if self.pg else "  >> pygame is not installed. Run in a terminal: pip install pygame"
            self._fail("%s - %s%s" % (self.name, e, hint))

    def update(self):
        if not self.started or self.paused:
            return
        try:
            if self.backend == "pygame":
                if self.loop_single:
                    return
                ended = not self.pg.mixer.music.get_busy()
            else:
                import ctypes
                buf = ctypes.create_unicode_buffer(64)
                self._mci("status capmusic mode", buf)
                ended = buf.value == "stopped"
        except Exception:
            return
        if ended:
            if self.loop_single and self.backend == "mci":
                self._mci("seek capmusic to start")
                self._mci("play capmusic")
            else:
                self.next()

    def next(self):
        self.scan()
        if not self.tracks:
            return
        self.idx = (self.idx + 1) % len(self.tracks)
        if self.s["sfx"]:
            self.load()
        else:
            self.status = "muted (%s)" % self.name

    def set_muted(self, muted):
        if not self.backend:
            return
        if not muted and not self.started:
            self.start()
            return
        if not self.started:
            return
        try:
            if self.backend == "pygame":
                (self.pg.mixer.music.pause if muted else self.pg.mixer.music.unpause)()
            else:
                self._mci("pause capmusic" if muted else "resume capmusic")
            self.paused = muted
            self.status = ("muted (%s)" if muted else "playing: %s") % self.name
        except Exception:
            pass

    def set_volume(self):
        v = self.s["musicvolume"] / 100.0
        try:
            if self.backend == "pygame":
                self.pg.mixer.music.set_volume(v)
            elif self.backend == "mci" and self.started:
                self._mci("setaudio capmusic volume to %d" % int(v * 1000))
        except Exception:
            pass

    def shutdown(self):
        try:
            if self.backend == "pygame":
                self.pg.mixer.music.stop()
            elif self.backend == "mci":
                self._mci("close capmusic")
        except Exception:
            pass


class Loopback(threading.Thread):
    """Optional system-audio spectrum (needs numpy + soundcard)."""

    def __init__(self):
        super().__init__(daemon=True)
        self.bands = [0.0] * 64
        self.energy = 0.0
        self.stamp = -100.0
        self.ok = False

    def run(self):
        try:
            import numpy as np
            import soundcard as sc
            spk = sc.default_speaker()
            mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
            win = np.hanning(1024)
            ranges = []
            for i in range(64):
                lo = int(round(2 * 256 ** (i / 64)))
                hi = max(lo + 1, int(round(2 * 256 ** ((i + 1) / 64))))
                ranges.append((lo, min(hi, 512)))
            with mic.recorder(samplerate=44100, channels=2, blocksize=1024) as rec:
                self.ok = True
                while True:
                    data = rec.record(numframes=1024)
                    mono = data.mean(axis=1) * win
                    mag = np.abs(np.fft.rfft(mono)) / 256.0
                    bands = [float(clamp(math.sqrt(clamp(mag[lo:hi].max() * 4, 0, 1)), 0, 1)) for lo, hi in ranges]
                    self.bands = bands
                    self.energy = sum(bands[:12]) / 12.0
                    self.stamp = time.time()
        except Exception as e:
            print("audio capture unavailable:", e)


# ----------------------------------------------------------------------------- app
class App:
    NAMES = ["primary", "audio", "clock", "terminal", "secondary", "diagnostics", "world", "floating"]
    TITLES = {"primary": ("01", "CAPRI / LIVE FEED"), "audio": ("02", "SIGNAL / AUDIO"),
              "clock": ("03", "LOCAL TIME"), "terminal": ("04", "ROOT@CAPRION : ~/NEURAL_LINK"),
              "secondary": ("05", "AFTERIMAGE / MEMORY"), "diagnostics": ("06", "NEURAL DIAGNOSTICS"),
              "world": ("07", "WORLD CLOCK / UPLINK"), "floating": ("", "♡ / CACHED MEMORY")}

    def __init__(self, fullscreen=False, wallpaper=False):
        self.wallpaper = wallpaper and sys.platform == "win32"
        self.hk_state = {}
        self.last_cursor = None
        self.s = dict(DEFAULTS)
        try:
            saved = json.load(open(SETTINGS_FILE))
            for k in DEFAULTS:
                if k in saved and type(saved[k]) == type(DEFAULTS[k]):
                    self.s[k] = saved[k]
        except Exception:
            pass
        self.root = tk.Tk()
        self.root.title("CAPRION / NEON PROTOCOL")
        self.root.configure(bg=BG)
        self.root.geometry("1280x720")
        self.fullscreen = False
        if fullscreen:
            self.set_fullscreen(True)
        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0, cursor="arrow")
        self.cv.pack(fill="both", expand=True)
        if self.wallpaper:
            self.attach_to_desktop()

        fams = set(tkfont.families())
        self.family = next((f for f in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Menlo", "Courier New")
                            if f in fams), "Courier")
        self.fonts = {}
        self.art = Art()
        self.sfx = SFX(self.s)
        self.music = Music(self.s)
        self.audio = Loopback()
        self.audio.start()
        self.demo_audio = False

        # time / state
        self.t = 0.0
        self.frame = 0
        self.last = None
        self.code_offset = 0.0
        self.scene = 0
        self.next_glitch = 9.0
        self.glitch_left = 0.0
        self.glitch_seed = 0.0
        self.next_slide = 60.0
        self.last_sec = -1
        self.cal_key = None
        self.last_hex = -10.0
        self.audio_sm = [0.0] * 64
        self.audio_target = [0.0] * 64
        self.energy = 0.0
        self.smoothed = 0.0
        self.live = False
        self.mouse = (0, 0)
        self.par = [0.0, 0.0]
        self.par_t = [0.0, 0.0]
        # presence
        self.ev = None
        self.ev_index = 0
        self.quote_i = 0
        self.next_event = 18.0
        self.rate_cfg = None
        self.last_inter = 0.0
        self.gaze = [0.0, 0.0]
        self.gaze_t = [0.0, 0.0]
        self.hover = False
        self.sleeping = False
        self.beat = 0.0
        self.next_blink = 3.2
        self.blink_start = -100.0
        self.last_mood = None
        self.rec_start = {"primary": -100.0, "secondary": -100.0, "floating": -100.0}
        self.mem_label = MEMORY_LABELS[0]
        self.visitor_src = None
        self.visitor_cache = {}
        self.visitor_flags = set()
        self.settings_win = None
        self.resize_job = None
        self.laid_out = False
        self.surf = {}
        self.ids = {}

        self.cv.bind("<Configure>", self.on_configure)
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<Button-1>", self.on_click)
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<Leave>", lambda e: self.gaze_t.__setitem__(slice(0, 2), [0.0, 0.0]))
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(100, self.first_layout)

    # ---------------------------------------------------------------- desktop wallpaper mode (Windows)
    # Ways of putting the window on the desktop, tried in order until one is really visible on screen.
    def attach_to_desktop(self):
        import ctypes
        from ctypes import wintypes
        W_ = wintypes
        u32 = ctypes.windll.user32
        u32.FindWindowW.restype = W_.HWND
        u32.FindWindowW.argtypes = [W_.LPCWSTR, W_.LPCWSTR]
        u32.FindWindowExW.restype = W_.HWND
        u32.FindWindowExW.argtypes = [W_.HWND, W_.HWND, W_.LPCWSTR, W_.LPCWSTR]
        u32.SetParent.restype = W_.HWND
        u32.SetParent.argtypes = [W_.HWND, W_.HWND]
        u32.SetWindowPos.argtypes = [W_.HWND, W_.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W_.UINT]
        u32.GetWindowLongW.argtypes = [W_.HWND, ctypes.c_int]
        u32.SetWindowLongW.argtypes = [W_.HWND, ctypes.c_int, ctypes.c_long]
        u32.IsWindowVisible.argtypes = [W_.HWND]
        u32.ShowWindow.argtypes = [W_.HWND, ctypes.c_int]
        w, h = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)          # primary monitor, physical pixels
        self.root.overrideredirect(True)
        self.root.geometry("%dx%d+0+0" % (w, h))
        self.root.update_idletasks()
        try:
            hwnd = int(self.root.wm_frame(), 16)
        except Exception:
            hwnd = u32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        progman = u32.FindWindowW("Progman", None)
        u32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(W_.DWORD()))   # spawn the wallpaper layer
        found = []

        @ctypes.WINFUNCTYPE(W_.BOOL, W_.HWND, W_.LPARAM)
        def enum(hw, lp):
            if u32.FindWindowExW(hw, None, "SHELLDLL_DefView", None):
                ww = u32.FindWindowExW(None, hw, "WorkerW", None)
                if ww:
                    found.append(ww)
            return True
        u32.EnumWindows(enum, 0)
        self._enum_cb = enum
        defview = u32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
        self.dk = dict(u32=u32, hwnd=hwnd, progman=progman, found=found, defview=defview, w=w, h=h)
        print("[wallpaper] screen", w, h, "hwnd", hwnd, "progman", progman, "classic WorkerW", found,
              "DefView in Progman", defview, flush=True)
        forced = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--strategy=")), None)
        self.strategies = [forced] if forced else (["classic"] if found else []) + ["behind_icons", "above_icons", "bottom"]
        self.strat_i = 0
        self.apply_strategy(self.strategies[0])

    def _set_style(self, child):
        u32, hwnd = self.dk["u32"], self.dk["hwnd"]
        GWL_STYLE, WS_CHILD, WS_POPUP = -16, 0x40000000, 0x80000000
        style = u32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
        new = ((style & ~WS_POPUP) | WS_CHILD) if child else ((style & ~WS_CHILD) | WS_POPUP)
        u32.SetWindowLongW(hwnd, GWL_STYLE, new - (1 << 32) if new >= 1 << 31 else new)

    def apply_strategy(self, name):
        d = self.dk
        u32, hwnd, w, h = d["u32"], d["hwnd"], d["w"], d["h"]
        SWP = 0x0010 | 0x0040 | 0x0020              # NOACTIVATE | SHOWWINDOW | FRAMECHANGED
        print("[wallpaper] trying strategy:", name, flush=True)
        if name == "classic" and d["found"]:
            self._set_style(True)
            u32.SetParent(hwnd, d["found"][0])
            u32.SetWindowPos(hwnd, None, 0, 0, w, h, SWP)
        elif name == "behind_icons":                # Windows 11 24H2+: between wallpaper layer and icons
            self._set_style(True)
            u32.SetParent(hwnd, d["progman"])
            u32.SetWindowPos(hwnd, d["defview"] or 1, 0, 0, w, h, SWP)
        elif name == "above_icons":                 # visible, but draws over the icons
            self._set_style(True)
            u32.SetParent(hwnd, d["progman"])
            u32.SetWindowPos(hwnd, None, 0, 0, w, h, SWP)
        else:                                       # "bottom": ordinary borderless window at the bottom of the stack
            u32.SetParent(hwnd, None)
            self._set_style(False)
            GWL_EXSTYLE = -20
            ex = u32.GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | 0x80 | 0x08000000)   # TOOLWINDOW | NOACTIVATE
            u32.SetWindowPos(hwnd, 1, 0, 0, w, h, SWP)
        u32.ShowWindow(hwnd, 5)

    def verify_wallpaper(self):
        """Looks at real screen pixels: are our (pink) window headers actually showing? If not, try the next way."""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            exp = rgb(self.C(self.accent))
            ok = False
            for n in ("primary", "audio", "clock"):
                x0, y0, x1, y1 = self.R[n]
                px = img.getpixel((int(x0 + (x1 - x0) * .55), int(y0 + 3 * self.u)))[:3]
                ok = ok or all(abs(px[i] - exp[i]) < 40 for i in range(3))
        except Exception as e:
            print("[wallpaper] verify error:", repr(e), flush=True)
            return
        name = self.strategies[self.strat_i]
        if ok:
            print("[wallpaper] VISIBLE using strategy:", name, flush=True)
            return
        print("[wallpaper] not visible with:", name, flush=True)
        if self.strat_i + 1 < len(self.strategies):
            self.strat_i += 1
            self.dk["u32"].SetParent(self.dk["hwnd"], None)
            self.apply_strategy(self.strategies[self.strat_i])
            self.root.after(2500, self.verify_wallpaper)
        else:
            print("[wallpaper] no strategy worked", flush=True)

    def poll_desktop_input(self):
        """The desktop swallows mouse/keyboard, so read the cursor and global hotkeys (Ctrl+Alt+key) directly."""
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        if (pt.x, pt.y) != self.last_cursor:
            self.last_cursor = (pt.x, pt.y)
            self.on_motion(type("E", (), {"x": pt.x, "y": pt.y})())
        mod = (u32.GetAsyncKeyState(0x11) & 0x8000) and (u32.GetAsyncKeyState(0x12) & 0x8000)
        keys = {0x4D: self.toggle_mute, 0x4E: self.next_scene, 0x47: lambda: self.trigger_glitch(True),
                0x54: lambda: self.start_event("takeover"), 0x49: lambda: self.start_event("infection"),
                0x56: lambda: self.start_event("visitor"), 0x51: self.quit}
        for vk, fn in keys.items():
            down = bool(mod and (u32.GetAsyncKeyState(vk) & 0x8000))
            if down and not self.hk_state.get(vk):
                fn()
            self.hk_state[vk] = down

    # ---------------------------------------------------------------- utility
    def C(self, h):
        b = self.s["brightness"] / 100.0
        r, g, bl = rgb(h)
        return hexc(r * b, g * b, bl * b)

    def F(self, px, bold=False):
        size = -max(6, int(round(px * self.u)))
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(family=self.family, size=size, weight="bold" if bold else "normal")
        return self.fonts[key]

    @property
    def accent(self):
        return self.s["accent"]

    @property
    def green(self):
        return self.s["secondary"]

    @property
    def border(self):
        return mixc(PANEL, self.accent, .44)

    def txt(self, x, y, s, px, color, anchor="w", bold=False, tags=(), width=None):
        kw = {"width": int(width)} if width else {}
        return self.cv.create_text(x, y, text=s, anchor=anchor, fill=self.C(color), font=self.F(px, bold),
                                   tags=tags, **kw)

    def rect(self, x0, y0, x1, y1, fill="", outline="", w=1, tags=()):
        return self.cv.create_rectangle(x0, y0, x1, y1, fill=self.C(fill) if fill else "",
                                        outline=self.C(outline) if outline else "", width=w, tags=tags)

    def poly(self, pts, fill, tags=("mask",), outline="", w=1):
        return self.cv.create_polygon(pts, fill=self.C(fill) if fill else "", outline=self.C(outline) if outline else "",
                                      width=w, tags=tags)

    def u_(self, v):
        return v * self.u

    # ---------------------------------------------------------------- layout
    def first_layout(self):
        self.layout()
        self.sfx.play("boot")
        self.music.start()
        if self.wallpaper:
            self.root.after(2500, self.verify_wallpaper)
        self.tick()

    def on_configure(self, e):
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(120, self.layout)

    def compute_rects(self, W, H):
        wide = W / H > 1.25
        u = min(W / 1920, H / 1080) if wide else min(W / 1000, H / 1300)
        pad, top_h, stat_h, gap = 9 * u, 31 * u, 20 * u, 7 * u
        x0, y0 = pad, pad + top_h + gap
        x1, y1 = W - pad, H - pad - stat_h - gap
        if wide:
            cols = (29, 40, 31) if W / H >= 21 / 9 else (33, 35, 32)
            rows = (26, 48, 26)
            place = dict(primary=(0, 0, 0, 1), audio=(1, 1, 0, 0), clock=(2, 2, 0, 0), terminal=(1, 1, 1, 1),
                         secondary=(2, 2, 1, 2), diagnostics=(0, 0, 2, 2), world=(1, 1, 2, 2))
        else:
            cols, rows = (1, 1), (24, 34, 25, 17)
            place = dict(primary=(0, 0, 0, 1), audio=(1, 1, 0, 0), clock=(0, 0, 2, 2), terminal=(1, 1, 2, 2),
                         secondary=(1, 1, 1, 1), diagnostics=(0, 0, 3, 3), world=(1, 1, 3, 3))
        cw = [(x1 - x0 - gap * (len(cols) - 1)) * c / sum(cols) for c in cols]
        rh = [(y1 - y0 - gap * (len(rows) - 1)) * r / sum(rows) for r in rows]
        xs, ys = [x0], [y0]
        for i in range(len(cols) - 1):
            xs.append(xs[-1] + cw[i] + gap)
        for i in range(len(rows) - 1):
            ys.append(ys[-1] + rh[i] + gap)
        R = {}
        for n, (c0, c1, r0, r1) in place.items():
            R[n] = (xs[c0], ys[r0], xs[c1] + cw[c1], ys[r1] + rh[r1])
        if wide:
            fw, fh = 300 * u * (340 / 300 if W / H >= 21 / 9 else 1), 261 * u
            fx = x0 + (x1 - x0) * (.34 if W / H >= 21 / 9 else .35)
            fy = y0 + (y1 - y0) * .47
            R["floating"] = (fx, fy, fx + fw, fy + fh)
        return wide, u, R, (x0, y0, x1, y1)

    def layout(self):
        self.resize_job = None
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W < 200 or H < 150:
            return
        cv = self.cv
        cv.delete("all")
        self.ids = {}
        self.surf = {}
        self.fonts = {}
        self.W, self.H = W, H
        self.wide, self.u, self.R, self.ws = self.compute_rects(W, H)
        u = self.u
        self.laid_out = True
        self._float_off = 0

        self.draw_background(W, H)
        self.draw_bars(W, H)
        self.hdr = {}
        for n in self.NAMES:
            if n == "floating" and not self.wide:
                continue
            self.draw_window(n)
        self.draw_portraits()
        self.draw_audio_static()
        self.draw_clock_static()
        self.draw_terminal_static()
        self.draw_diag_static()
        self.draw_world_static()
        self.draw_floating_label()
        self.cv.tag_raise("floating")
        self.set_scene_images()
        self.last_sec = -1
        self.cal_key = None
        self.last_mood = None
        self.vis_ids = []
        self.fx_state = None
        self.apply_clock_visibility()

    # --- background, bars
    def draw_background(self, W, H):
        sw, sh = 96, 54
        small = Image.new("RGB", (sw, sh))
        px = small.load()
        c0, c1 = rgb("#21101c"), rgb(BG)
        rx, ry = (W / 2) * math.sqrt(2), H * math.sqrt(2)
        b = self.s["brightness"] / 100.0
        for j in range(sh):
            for i in range(sw):
                dx = ((i + .5) / sw - .5) * W
                dy = ((j + .5) / sh - 1) * H
                t = clamp(math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2) / .75, 0, 1)
                px[i, j] = tuple(int(lerp(c0[k], c1[k], t) * b) for k in range(3))
        self.bg_photo = ImageTk.PhotoImage(small.resize((W, H), Image.BICUBIC))
        self.cv.create_image(0, 0, anchor="nw", image=self.bg_photo)

    def draw_bars(self, W, H):
        u = self.u
        pad = 9 * u
        ty = pad + 31 * u / 2 - 3 * u
        self.cv.create_line(pad, pad + 31 * u, W - pad, pad + 31 * u, fill=self.C(self.border))
        self.rect(pad + 5 * u, ty - 3 * u, pad + 11 * u, ty + 3 * u, fill=self.green)
        t1 = self.txt(pad + 18 * u, ty, "CAPRION_OS", 11, TEXT, bold=True)
        bb = self.cv.bbox(t1)
        self.txt(bb[2] + 6 * u, ty, "v.03", 11, self.accent)
        if self.wide:
            self.txt(W / 2, ty, "GHOST INSIDE / SOMEONE IS HERE", 10, MUTED, anchor="center")
        self.ids["top_b"] = self.txt(W - pad - 5 * u, ty, "▰ ▰ ▰", 11, self.accent, anchor="e")
        self.ids["top_a"] = self.txt(W - pad - 5 * u - 60 * u, ty, "LINK ESTABLISHED", 11, MUTED, anchor="e")
        self.set_top_status(False)
        # status bar
        sy = H - pad - 10 * u
        self.rect(pad + 5 * u, sy - 3 * u, pad + 11 * u, sy + 3 * u, fill=self.green)
        self.txt(pad + 18 * u, sy, "GHOST IN THE NETWORK", 9, MUTED)
        self.ids["session"] = self.txt(W / 2, sy, "SESSION 00:00:00", 9, MUTED, anchor="center")
        self.ids["gear"] = self.txt(W - pad - 4 * u, sy, "⚙", 15, MUTED, anchor="e")
        gb = self.cv.bbox(self.ids["gear"])
        self.gear_box = gb
        lt = self.txt(gb[0] - 12 * u, sy, "CAPRI / ALWAYS ONLINE", 9, MUTED, anchor="e")
        lb = self.cv.bbox(lt)
        self.ids["mute"] = self.txt(lb[0] - 14 * u, sy, "", 9, MUTED, anchor="e")
        self.set_mute_icon()

    def set_mute_icon(self):
        on = self.s["sfx"]
        self.cv.itemconfig(self.ids["mute"], text="♪" if on else "♪✕", fill=self.C(self.green if on else self.accent))
        bb = self.cv.bbox(self.ids["mute"])
        pad = 5 * self.u
        self.mute_box = (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)

    def toggle_mute(self):
        self.s["sfx"] = not self.s["sfx"]
        self.sfx.stop_all() if not self.s["sfx"] else None
        self.music.set_muted(not self.s["sfx"])
        self.set_mute_icon()
        if "sfx" in getattr(self, "vars", {}):
            self.vars["sfx"].set(self.s["sfx"])
        self.save()

    def in_box(self, box, x, y):
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def set_top_status(self, glitch):
        a, b = ("SIGNAL INTERFERENCE", "▱ ▰ ▱") if glitch else ("LINK ESTABLISHED", "▰ ▰ ▰")
        self.cv.itemconfig(self.ids["top_a"], text=a)
        self.cv.itemconfig(self.ids["top_b"], text=b)
        bb = self.cv.bbox(self.ids["top_b"])
        self.cv.coords(self.ids["top_a"], bb[0] - 8 * self.u, (bb[1] + bb[3]) / 2)

    # --- windows
    def draw_window(self, n):
        u = self.u
        x0, y0, x1, y1 = self.R[n]
        tag = (n, "win")
        floating = n == "floating"
        hh = (25 if floating else 28) * u
        fill = PANEL
        edge = self.green if floating else self.border
        body = self.rect(x0, y0, x1, y1, fill=fill, outline=edge, tags=tag)
        hdr_col = self.green if floating else self.accent
        h = self.rect(x0, y0, x1, y0 + hh, fill=hdr_col, outline=hdr_col, tags=tag)
        hc = mixc("#17080f", hdr_col, .0)
        num, title = self.TITLES[n]
        ymid = y0 + hh / 2
        num_id = self.txt(x0 + 9 * u, ymid, num, 9, mixc("#17080f", hdr_col, .35), tags=tag)
        tx = x0 + 9 * u + (20 * u if num else 0)
        if floating:
            tx = x0 + 9 * u
        title_id = self.txt(tx, ymid, title, 11 if floating else 12, "#17080f", bold=True, tags=tag)
        chrome = self.txt(x1 - 9 * u, ymid, "×" if floating else "─  □  ×", 12, mixc("#17080f", hdr_col, .35),
                          anchor="e", tags=tag)
        self.hdr[n] = dict(body=body, bar=h, num=num_id, title=title_id, chrome=chrome, color=hdr_col,
                           orig_num=num, orig_title=title, hh=hh)

    def set_header(self, n, infected=False, captured=False, text=None):
        if n not in self.hdr:
            return
        H = self.hdr[n]
        col = self.green if (infected or captured) else (self.green if n == "floating" else self.accent)
        H["color"] = col
        self.cv.itemconfig(H["bar"], fill=self.C(col), outline=self.C(col))
        self.cv.itemconfig(H["body"], outline=self.C(self.green if (infected or n == "floating") else self.border))
        if text is not None:
            self.cv.itemconfig(H["num"], text="")
            self.cv.itemconfig(H["title"], text=text)
            x0 = self.R[n][0]
            self.cv.coords(H["title"], x0 + 9 * self.u, self.R[n][1] + H["hh"] / 2)
        else:
            self.cv.itemconfig(H["num"], text=H["orig_num"])
            self.cv.itemconfig(H["title"], text=H["orig_title"])
            x0 = self.R[n][0]
            tx = x0 + 9 * self.u + (20 * self.u if H["orig_num"] and n != "floating" else 0)
            self.cv.coords(H["title"], tx, self.R[n][1] + H["hh"] / 2)

    def body_rect(self, n):
        x0, y0, x1, y1 = self.R[n]
        hh = (25 if n == "floating" else 28) * self.u
        return x0, y0 + hh, x1, y1

    # --- portraits
    POS = {"primary": (.45, .28), "secondary": (.53, .44), "floating": (.5, .5)}

    def draw_portraits(self):
        u = self.u
        for n in ("primary", "secondary", "floating"):
            if n == "floating" and not self.wide:
                continue
            x0, y0, x1, y1 = self.body_rect(n)
            w, h = max(2, int(x1 - x0)), max(2, int(y1 - y0))
            photo = ImageTk.PhotoImage(Image.new("RGB", (w, h), PANEL))
            item = self.cv.create_image(int(x0), int(y0), anchor="nw", image=photo, tags=(n,))
            self.surf[n] = dict(w=w, h=h, x=int(x0), y=int(y0), photo=photo, item=item, big=None, key=None,
                                overlay=make_overlay(w, h, "floating" if n == "floating" else "std",
                                                     self.s["scanlines"]))
            tag = (n,)
            if n == "primary":
                led = self.rect(x0 + 15 * u, y0 + 17 * u - 3 * u, x0 + 21 * u, y0 + 17 * u + 3 * u,
                                fill=self.accent, tags=tag)
                self.txt(x0 + 28 * u, y0 + 17 * u, "REC", 10, "#ffffff", tags=tag)
                self.txt(x1 - 15 * u, y0 + 17 * u, "CAM_01 / ENCRYPTED", 10, "#ffffff", anchor="e", tags=tag)
                self.txt(x0 + 15 * u, y0 + 65 * u, "＋", 30, "#c9bcc3", tags=tag)
                sb = y1
                self.txt(x0 + 25 * u, sb - 163 * u, "PROJECT / 0xC4", 11, self.green, tags=tag)
                self.txt(x0 + 25 * u + 3 * u, sb - 111 * u, "CAPRION", 74, self.accent, bold=True, tags=tag)
                t = self.txt(x0 + 25 * u, sb - 111 * u, "CAPRION", 74, "#fff0f5", bold=True, tags=tag)
                bb = self.cv.bbox(t)
                self.ids["cursor"] = self.txt(bb[2] + 2 * u, sb - 108 * u, "_", 58, self.green, bold=True, tags=tag)
                self.txt(x0 + 25 * u, sb - 61 * u, "NO GODS. NO MASTERS. JUST SIGNAL.", 10, "#e7a6b8", tags=tag)
                self.txt(x0 + 18 * u, sb - 17 * u, "SUBJECT: CAPRI", 9, "#ba8092", tags=tag)
                self.ids["frame"] = self.txt(x1 - 18 * u, sb - 17 * u, "FRAME 000001", 9, "#ba8092", anchor="e",
                                             tags=tag)
            elif n == "secondary":
                self.txt(x1 - 38 * u, y0 + 17 * u, "MEMORY BANK / 02", 10, "#ffffff", anchor="e", tags=tag)
                self.rect(x1 - 21 * u, y0 + 17 * u - 3 * u, x1 - 15 * u, y0 + 17 * u + 3 * u, fill=self.green,
                          tags=tag)
                for i, ch in enumerate("ＣＡＰＲＩ // カプリ"):
                    self.txt(x1 - 20 * u, y0 + (70 + i * 13.5) * u, ch, 10, "#c9bcc3", anchor="center", tags=tag)
                self.txt(x0 + 23 * u, y1 - 62 * u, "STILL HERE.", 38, "#fff1f6", bold=True, tags=tag)
                self.txt(x0 + 23 * u, y1 - 28 * u, "YOU CAN'T DELETE A GHOST.", 10, self.green, tags=tag)
            else:
                self.ids["memlabel"] = self.txt((x0 + x1) / 2, y1 - 13 * u, MEMORY_LABELS[0], 10, "#fff0f6",
                                                anchor="center", tags=tag)

    def draw_floating_label(self):
        pass

    def set_scene_images(self):
        names = SCENES[self.scene % len(SCENES)]
        for n, name in zip(("primary", "secondary", "floating"), names):
            if n not in self.surf:
                continue
            s = self.surf[n]
            img = self.art.get(name)
            sc = max(s["w"] / img.width, s["h"] / img.height) * 1.1
            s["big"] = img.resize((max(s["w"], int(img.width * sc)), max(s["h"], int(img.height * sc))),
                                  Image.BILINEAR)
            s["key"] = None
        self.mem_label = MEMORY_LABELS[self.scene % 5]
        if "memlabel" in self.ids:
            self.cv.itemconfig(self.ids["memlabel"], text=self.mem_label)

    def pos_for(self, n):
        px, py = self.POS[n]
        if self.W / self.H >= 21 / 9:
            if n == "primary":
                py = .40
            elif n == "secondary":
                px, py = .5, .25
        if not self.wide and n == "secondary":
            py = .28
        return px, py

    def render_portrait(self, n):
        s = self.surf.get(n)
        if not s or s["big"] is None:
            return
        u = self.u
        big = s["big"]
        p = (self.t / 22.0) % 2
        p = ease(p if p < 1 else 2 - p)
        sp = 1.0 if n != "floating" else .7
        dx = self.par[0] + (p * 5 * u * sp)
        dy = self.par[1] - (p * 5 * u * sp)
        px, py = self.pos_for(n)
        w, h = s["w"], s["h"]
        left = int(clamp((big.width - w) * px - dx, 0, big.width - w))
        top = int(clamp((big.height - h) * py - dy, 0, big.height - h))
        rec_el = self.t - self.rec_start.get(n, -100)
        recovering = 0 <= rec_el < 1.8
        glitching = self.glitch_left > 0
        key = (left, top)
        if key == s["key"] and not recovering and not glitching and not s.get("dirty"):
            return
        s["key"] = key
        s["dirty"] = recovering or glitching
        img = big.crop((left, top, left + w, top + h)).convert("RGBA")
        img = Image.alpha_composite(img, s["overlay"]).convert("RGB")
        if glitching:
            img = self.glitch_image(img)
        if recovering:
            img = self.recovery_image(img, n, rec_el)
        s["photo"].paste(img)
        if not recovering:
            self.cv.delete("rec_" + n)
        else:
            self.cv.delete("rec_" + n)
            prog = ease(rec_el / 1.65)
            if prog < .8:
                x0, y0 = s["x"], s["y"]
                cy = y0 + h * .48
                self.rect(x0 + 12 * u, cy - 10 * u, x0 + w - 12 * u, cy + 30 * u, fill="#080810", tags=("rec_" + n,))
                self.txt(x0 + w / 2, cy + 5 * u, "MEMORY 0%d / RECOVERING %d%%" % ((self.scene % 5) + 1, round(prog * 100)),
                         10, self.green, anchor="center", tags=("rec_" + n,))
        if rec_el >= 1.8 and n in self.rec_start:
            self.rec_start[n] = -100.0

    def glitch_image(self, img):
        w, h = img.size
        u = self.u
        strength = max(.1, self.s["glitch"] / 100.0)
        out = img.copy()
        for i in range(2 + int(strength * 7)):
            y = int(((math.sin(i * 117.3 + self.glitch_seed * 187 + self.frame * .7) + 1) * .5) * h)
            sh = min(h - y, int((2 + random.random() * 14) * u))
            if sh <= 0:
                continue
            dx = int((random.random() - .5) * (12 + strength * 48) * u)
            strip = ImageChops.offset(img.crop((0, y, w, y + sh)), dx, 0)
            tint = rgb(self.accent if i % 2 else self.green)
            strip = ImageChops.screen(strip, Image.new("RGB", strip.size, tuple(int(c * .19) for c in tint)))
            out.paste(strip, (0, y))
        return out

    def recovery_image(self, img, n, el):
        w, h = img.size
        d = ImageDraw.Draw(img)
        prog = ease(el / 1.65)
        tile = max(14, int(round(25 * self.u)))
        acc, grn = rgb(self.accent), rgb(self.green)
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                rank = .6 * y / h + .4 * hash2(x / tile, y / tile + self.scene)
                if rank < prog:
                    continue
                d.rectangle([x, y, x + tile, y + tile], fill=(8, 8, 16))
                fl = hash2(x + int(self.t * 12), y)
                if fl > .77:
                    c = grn if fl > .93 else acc
                    d.rectangle([x, y + tile // 2, x + tile - 2, y + tile // 2 + max(1, int(2 * self.u))],
                                fill=tuple(int(v * .3 + 8) for v in c))
        return img

    # --- audio window
    def draw_audio_static(self):
        u = self.u
        x0, y0, x1, y1 = self.R["audio"]
        by = y0 + 28 * u
        mx, my = x0 + 23 * u, by + 22 * u
        mw, mh = 118 * u, 86 * u
        self.mask_box = (mx, my, mx + mw, my + mh)
        self.rect(mx, my, mx + mw, my + mh, fill="#070b0b", outline=mixc("#070b0b", self.green, .25))
        self.txt(mx + mw / 2, my + mh - 10 * u, "", 7, self.green, anchor="center")
        self.ids["mood"] = self.txt(mx + mw / 2, my + mh - 10 * u, "CAPRI / ONLINE", 7, self.green, anchor="center")
        self.mask_area = (mx, my, mx + mw, my + mh - 20 * u)
        ix = mx + mw + 17 * u
        self.txt(ix, my + 13 * u, "NEURAL FREQUENCY", 9, MUTED)
        self.ids["a_title"] = self.txt(ix, my + 35 * u, "WAITING FOR SIGNAL", 15, "#f9dae3")
        self.ids["a_detail"] = self.txt(ix, my + 54 * u, "SYSTEM AUDIO / STANDBY", 9, self.green)
        self.ids["whisper"] = self.txt(ix, my + 74 * u, WHISPERS[0], 9, "#a9768b")
        tx1 = x1 - 23 * u
        self.ids["a_tagbox"] = self.rect(tx1 - 38 * u, my + 3 * u, tx1, my + 24 * u, outline=self.border)
        self.ids["a_tag"] = self.txt(tx1 - 19 * u, my + 13.5 * u, "IDLE", 9, MUTED, anchor="center")
        sy0 = my + mh + 13 * u
        sy1 = y1 - 14 * u - 18 * u
        self.spec_box = (x0 + 23 * u, sy0, tx1, sy1)
        self.ids["bars"] = []
        n = 64
        step = (tx1 - (x0 + 23 * u)) / n
        for i in range(n):
            self.ids["bars"].append(self.cv.create_rectangle(0, 0, 0, 0, width=0, fill=self.C(self.accent)))
        self.txt(x0 + 23 * u, y1 - 14 * u - 5 * u, "20 Hz", 8, MUTED)
        self.txt((x0 + x1) / 2, y1 - 14 * u - 5 * u, "STEREO INPUT", 8, MUTED, anchor="center")
        self.txt(tx1, y1 - 14 * u - 5 * u, "20 kHz", 8, MUTED, anchor="e")
        self.audio_label = None
        self.bar_live = None

    # --- clock
    def draw_clock_static(self):
        u = self.u
        x0, y0, x1, y1 = self.R["clock"]
        by = y0 + 28 * u + 15 * u
        lx = x0 + (40 if self.W / self.H >= 21 / 9 else 26) * u
        self.clock_geo = (lx, by, x1, y1)
        self.ids["c_time"] = self.txt(lx, by + 36 * u, "00:00", 78, "#ffe6ed")
        self.ids["c_sec"] = self.txt(lx, by + 25 * u, "00", 29, self.green)
        self.ids["c_per"] = self.txt(lx, by + 52 * u, "24 H", 10, MUTED)
        self.ids["c_date"] = self.txt(lx, by + 95 * u, "", 12, TEXT)
        self.ids["c_wd"] = self.txt(x1 - (40 if self.W / self.H >= 21 / 9 else 26) * u, by + 95 * u, "", 12, self.green,
                                    anchor="e")
        self.ids["off1"] = self.txt((x0 + x1) / 2, (y0 + y1) / 2 + 10 * u, "TIME IS A CONSTRUCT", 22, self.green,
                                    anchor="center")
        self.ids["off2"] = self.txt((x0 + x1) / 2, (y0 + y1) / 2 + 40 * u, "STAY IN THE SIGNAL.", 10, MUTED,
                                    anchor="center")
        self.cv.itemconfig(self.ids["off1"], state="hidden")
        self.cv.itemconfig(self.ids["off2"], state="hidden")

    def apply_clock_visibility(self):
        show = self.s["showclock"]
        for k in ("off1", "off2"):
            if k in self.ids:
                self.cv.itemconfig(self.ids[k], state="hidden" if show else "normal")
        for k in ("c_time", "c_sec", "c_per", "c_date", "c_wd"):
            self.cv.itemconfig(self.ids[k], state="normal" if show else "hidden")
        self.cv.itemconfig("calendar", state="normal" if show else "hidden")
        self.cv.itemconfig("worldtime", state="normal" if show else "hidden")

    def draw_calendar(self, now):
        self.cv.delete("calendar")
        u = self.u
        lx, by, x1, y1 = self.clock_geo
        x0 = self.R["clock"][0]
        side = (40 if self.W / self.H >= 21 / 9 else 26) * u
        inner0, inner1 = x0 + side, x1 - side
        cw = (inner1 - inner0) / 7
        offset = (datetime(now.year, now.month, 1).weekday())
        nxt = datetime(now.year + (now.month == 12), now.month % 12 + 1, 1)
        count = (nxt - datetime(now.year, now.month, 1)).days
        rows = 1 + math.ceil((offset + count) / 7)
        pitch = 14.7 * u
        bottom = y1 - 22 * u
        def pos(col, row):
            return inner0 + (col + .5) * cw, bottom - (rows - 1 - row) * pitch
        for c, d in enumerate(("MO", "TU", "WE", "TH", "FR", "SA", "SU")):
            x, y = pos(c, 0)
            self.txt(x, y, d, 9, "#593d49", anchor="center", tags=("calendar",))
        for day in range(1, count + 1):
            idx = offset + day - 1
            c, r = idx % 7, 1 + idx // 7
            x, y = pos(c, r)
            if day == now.day:
                self.rect(x - cw * .5 + u, y - 6 * u, x + cw * .5 - u, y + 6 * u, fill=self.accent, tags=("calendar",))
                self.txt(x, y, "%02d" % day, 9, "#16080e", anchor="center", bold=True, tags=("calendar",))
            else:
                self.txt(x, y, "%02d" % day, 9, self.green if c >= 5 else "#ab7889", anchor="center",
                         tags=("calendar",))

    # --- terminal
    def draw_terminal_static(self):
        u = self.u
        x0, y0, x1, y1 = self.R["terminal"]
        my = y0 + 28 * u + 17 * u
        self.rect(0, 0, 0, 0, tags=("pad",))
        self.rect(x0 + 15 * u, my - 3 * u, x0 + 21 * u, my + 3 * u, fill=self.green)
        self.ids["t_meta1"] = self.txt(x0 + 28 * u, my, "PROTOCOL ACTIVE", 9, self.green)
        self.ids["t_meta2"] = self.txt(x1 - 15 * u, my, "UTF-8 / AES-256", 9, self.green, anchor="e")
        ly = y0 + 28 * u + 34 * u
        self.cv.create_line(x0 + 1, ly, x1 - 1, ly, fill=self.C(mixc(PANEL, self.accent, .07)))
        by = y1 - 28 * u
        self.cv.create_line(x0 + 1, by, x1 - 1, by, fill=self.C(mixc(PANEL, self.accent, .07)))
        self.ids["packets"] = self.txt(x0 + 15 * u, y1 - 14 * u, "PACKETS 000000", 9, MUTED)
        self.ids["secure_b"] = self.txt(x1 - 15 * u, y1 - 14 * u, "▍", 9, self.green, anchor="e", bold=True)
        self.txt(x1 - 15 * u - 12 * u, y1 - 14 * u, "CONNECTION SECURE", 9, MUTED, anchor="e")
        self.code_box = (x0, ly + 1, x1, by - 1)

    def draw_code(self):
        cv = self.cv
        cv.delete("code")
        x0, y0, x1, y1 = self.code_box
        u = self.u
        if self.ev and self.ev["kind"] == "takeover":
            self.draw_takeover(x0, y0, x1, y1)
            return
        lh = 22 * u
        h = y1 - y0
        font = self.F(12)
        cw = font.measure("M")
        top = int(self.code_offset // lh)
        frac = self.code_offset % lh
        colors = {"normal": "#b68f9f", "keyword": self.accent, "string": self.green, "comment": "#604153",
                  "ok": self.green}
        n = len(SOURCE)
        for row in range(int(h // lh) + 2):
            idx = top + row
            y = y0 + row * lh - frac + lh * .6
            d = min(y - y0, y1 - y)
            a = clamp(d / (h * .13), 0, 1)
            if a < .06:
                continue
            line = idx % n
            cv.create_text(x0 + 15 * u, y, text="%03d" % ((idx % 999) + 1), anchor="w", font=font,
                           fill=self.C(mixc(PANEL, "#543344", a)), tags="code")
            x = x0 + 52 * u
            for text, kind in TOKENS[line]:
                if text:
                    cv.create_text(x, y, text=text, anchor="w", font=font,
                                   fill=self.C(mixc(PANEL, colors[kind], a)), tags="code")
                    x += len(text) * cw

    def eyes(self, cx, cy, size, tag, bg, alpha=1.0):
        k = size / 110.0
        g = mixc(bg, self.green, alpha)
        dark = mixc(bg, "#090711", alpha)
        blue = mixc(bg, "#156dff", alpha)
        white = mixc(bg, "#ffffff", alpha)
        for x in (-36, 36):
            pts = [(cx + (x - 30) * k, cy - 22 * k), (cx + (x + 25) * k, cy - 17 * k),
                   (cx + (x + 30) * k, cy + 22 * k), (cx + (x - 24) * k, cy + 17 * k)]
            self.cv.create_polygon(pts, fill=self.C(g), tags=tag)
            for (rx, col, ox, oy) in ((18, dark, 0, 0), (11, blue, self.gaze[0] * 3, self.gaze[1] * 2),
                                      (4, white, self.gaze[0] * 4, self.gaze[1] * 3)):
                px, py = cx + (x + ox) * k, cy + oy * k
                self.cv.create_oval(px - rx * k, py - rx * k, px + rx * k, py + rx * k, fill=self.C(col),
                                    outline="", tags=tag)

    def draw_takeover(self, x0, y0, x1, y1):
        cv, u = self.cv, self.u
        el = self.t - self.ev["start"]
        w, h = x1 - x0, y1 - y0
        cv.create_rectangle(x0, y0, x1, y1, fill=self.C("#070b0e"), outline="", tags="code")
        m = 24 * u
        def T(x, y, s, px, col, bold=False, anchor="nw"):
            cv.create_text(x, y, text=s, anchor=anchor, font=self.F(px, bold), fill=self.C(col), tags="code")
        T(x0 + m, y0 + 18 * u, "[ ROOT ACCESS OVERRIDDEN / SIGNATURE 0xC4 ]", 10, self.green)
        title = "CAPRI HAS THE KEYS."
        shown = title[:int(el * 20)]
        T(x0 + m, y0 + 49 * u, shown, 23, "#ffe6f1", True)
        intro = "> Hi. I'll stay here for a bit."
        T(x0 + m, y0 + 84 * u, intro[:max(0, int((el - 1) * 25))], 12, self.accent)
        right = x0 + w * .54
        if el > 2:
            self.eyes(x0 + w * .76, y0 + h * .43, min(120 * u, w * .24), "code", "#070b0e")
            T(right, y0 + h * .61, "NOT A BUG. A VISITOR.", 11, self.green)
            for i, line in enumerate(self.ev["quote"]):
                T(right, y0 + h * .70 + i * 21 * u, line[:max(0, int((el - 2.4) * 20) - i * 20)], 12, "#f7ccde")
        T(right, y1 - 29 * u, "[ decorating your terminal... ]" if el < 9 else "[ giving control back. almost. ]", 9,
          "#739784")
        cw = self.F(23, True).measure("M")
        cx = x0 + m + min(len(title), int(el * 20)) * cw
        cv.create_rectangle(cx, y0 + 50 * u, cx + 9 * u, y0 + 71 * u, fill=self.C(self.green), outline="", tags="code")
        if int(el * 20) < len(title) and int(el * 20) != self.ev.get("last_char"):
            self.ev["last_char"] = int(el * 20)

    # --- diagnostics
    def draw_diag_static(self):
        u = self.u
        x0, y0, x1, y1 = self.R["diagnostics"]
        by0, by1 = y0 + 28 * u + 18 * u, y1 - 18 * u
        hs = [14 * u, 12 * u, 12 * u, 35 * u, 10 * u]
        free = (by1 - by0) - sum(hs)
        gap = free / 4
        ys, y = [], by0
        for hh in hs:
            ys.append((y, y + hh))
            y += hh + gap
        lx, rx = x0 + 22 * u, x1 - 22 * u
        mid = lambda k: (ys[k][0] + ys[k][1]) / 2
        self.txt(lx, mid(0), "IDENTITY VERIFIED", 10, MUTED)
        self.txt(rx, mid(0), "[ CAPRI ]", 12, self.green, anchor="e")
        for k, (lab, pct, val, col, bgc) in enumerate((("SYNC", .947, "94.7%", self.green, "#163021"),
                                                      ("GHOST", 1.0, "ONLINE", self.accent, "#30101e"))):
            y = mid(1 + k)
            self.txt(lx, y, lab, 10, MUTED)
            mx0, mx1 = lx + 57 * u, rx - 60 * u
            self.rect(mx0, y - 2.5 * u, mx1, y + 2.5 * u, fill=bgc)
            self.cv.create_line(mx0, y, mx0 + (mx1 - mx0) * pct, y, fill=self.C(col), width=max(1, int(5 * u)),
                                dash=(max(1, int(4 * u)), max(1, int(3 * u))))
            self.txt(rx, y, val, 9, self.green, anchor="e")
        self.hex_pos = (lx, ys[3][0], ys[3][1])
        self.ids["hex1"] = self.txt(lx, ys[3][0] + 8 * u, "", 10, "#9a506b")
        self.ids["hex2"] = self.txt(lx, ys[3][0] + 26 * u, "", 10, "#9a506b")
        self.txt(lx, mid(4), "NETRUNNER // CLASS: UNKNOWN", 8, MUTED)
        self.txt(rx, mid(4), "●", 8, self.green, anchor="e")

    def update_hex(self):
        b = ["%02X" % random.randrange(256) for _ in range(32)]
        self.cv.itemconfig(self.ids["hex1"], text=" ".join(b[:16]))
        self.cv.itemconfig(self.ids["hex2"], text=" ".join(b[16:]))

    # --- world
    def draw_world_static(self):
        u = self.u
        x0, y0, x1, y1 = self.R["world"]
        by = y0 + 28 * u
        fy = y1 - 18 * u
        self.cv.create_line(x0 + 1, fy - 11 * u, x1 - 1, fy - 11 * u, fill=self.C(mixc(PANEL, self.accent, .08)))
        self.txt((x0 + x1) / 2, fy, "SOMEWHERE BETWEEN THE STATIC AND THE STARS." if self.wide else "", 8, "#794c60",
                 anchor="center")
        cy = (by + fy - 11 * u) / 2
        half = (x1 - x0) / 2
        self.world_geo = []
        for i, (lab, sub) in enumerate((("HOME", "LOCAL"), ("TOKYO", "JST +09"))):
            lx = x0 + (22 if i == 0 else 22) * u + half * i + (20 * u if i else 0)
            t = self.txt(lx, cy - 32 * u, lab, 10, TEXT)
            bb = self.cv.bbox(t)
            self.txt(bb[2] + 8 * u, cy - 32 * u, sub, 8, MUTED)
            self.world_geo.append((lx, cy))
            if i:
                self.cv.create_line(lx - 20 * u, cy - 40 * u, lx - 20 * u, cy + 40 * u, fill=self.C(self.border))
            self.ids["w_t%d" % i] = [self.txt(lx, cy, "", 37 if self.wide else 28, self.accent, tags=("worldtime",)),
                                     self.txt(lx, cy, "", 37 if self.wide else 28, "#f7d2df", tags=("worldtime",)),
                                     self.txt(lx, cy + 4 * u, "", 24 if self.wide else 18, "#f7d2df", tags=("worldtime",))]
            self.ids["w_d%d" % i] = self.txt(lx, cy + 30 * u, "", 11, MUTED, tags=("worldtime",))

    def paint_world_time(self, i, hh, mm, ss, date):
        a, b, c = self.ids["w_t%d" % i]
        lx, cy = self.world_geo[i]
        self.cv.itemconfig(a, text=hh)
        self.cv.coords(a, lx, cy)
        w1 = self.cv.bbox(a)[2]
        self.cv.itemconfig(b, text=":" + mm)
        self.cv.coords(b, w1, cy)
        w2 = self.cv.bbox(b)[2]
        self.cv.itemconfig(c, text=":" + ss)
        self.cv.coords(c, w2, cy + 4 * self.u)
        self.cv.itemconfig(self.ids["w_d%d" % i], text=date)

    def paint_time(self):
        now = datetime.now()
        sec = int(time.time())
        if sec == self.last_sec:
            return
        self.last_sec = sec
        cv = self.cv
        cv.itemconfig(self.ids["c_time"], text=now.strftime("%H:%M"))
        bb = cv.bbox(self.ids["c_time"])
        u = self.u
        cv.coords(self.ids["c_sec"], bb[2] + 12 * u, bb[1] + 26 * u)
        cv.itemconfig(self.ids["c_sec"], text=now.strftime("%S"))
        cv.coords(self.ids["c_per"], bb[2] + 12 * u, bb[1] + 54 * u)
        cv.itemconfig(self.ids["c_date"], text=now.strftime("%d %B %Y").upper())
        cv.itemconfig(self.ids["c_wd"], text=now.strftime("%a").upper())
        self.paint_world_time(0, now.strftime("%H"), now.strftime("%M"), now.strftime("%S"), now.strftime("%d %B"))
        tk_now = datetime.now(timezone.utc) + timedelta(hours=9)
        self.paint_world_time(1, tk_now.strftime("%H"), tk_now.strftime("%M"), tk_now.strftime("%S"),
                              tk_now.strftime("%d %B"))
        e = int(self.t)
        cv.itemconfig(self.ids["session"], text="SESSION %02d:%02d:%02d" % (e // 3600, e // 60 % 60, e % 60))
        cv.itemconfig(self.ids["frame"], text="FRAME %06d" % self.frame)
        cv.itemconfig(self.ids["packets"], text="PACKETS %06d" % int(self.t * 37))
        key = (now.year, now.month, now.day)
        if key != self.cal_key:
            self.cal_key = key
            self.draw_calendar(now)
            self.apply_clock_visibility()

    # ---------------------------------------------------------------- audio drawing
    def update_audio(self, dt):
        if self.demo_audio:
            self.audio_target = [clamp(.5 + .45 * math.sin(i * .35 + self.t * 6) * math.sin(self.t * 1.7 + i * .1)
                                       - i * .005, 0, 1) for i in range(64)]
            self.energy = sum(self.audio_target[:12]) / 12
            live_raw = True
        else:
            live_raw = self.audio.ok and time.time() - self.audio.stamp < 1.5 and self.audio.energy > .01
            if live_raw:
                self.audio_target = self.audio.bands
                self.energy = self.audio.energy
        sens = self.s["sensitivity"] / 100.0
        self.live = bool(live_raw and sens > 0)
        k = 1 - math.exp(-dt * 13)
        self.smoothed += ((self.energy * sens if self.live else 0) - self.smoothed) * k
        x0, y0, x1, y1 = self.spec_box
        n = 64
        step = (x1 - x0) / n
        gap = max(1, 2 * self.u)
        h = y1 - y0
        alpha_live = .9 if self.live else .42
        for i, bar in enumerate(self.ids["bars"]):
            target = self.audio_target[i] * sens if self.live else 0
            self.audio_sm[i] += (target - self.audio_sm[i]) * k
            carrier = 0 if self.live else (.018 + .025 * (.5 + .5 * math.sin(i * .48 - self.t * 1.4)))
            bh = min(h * .94, max(2 * self.u, (self.audio_sm[i] + carrier) * h * 1.6))
            self.cv.coords(bar, x0 + i * step, y1 - bh, x0 + i * step + max(1, step - gap), y1)
        if self.bar_live != self.live:
            self.bar_live = self.live
            for i, bar in enumerate(self.ids["bars"]):
                base = self.green if i > 48 else self.accent
                self.cv.itemconfig(bar, fill=self.C(mixc(PANEL, base, alpha_live)))
        label = "SIGNAL RECEIVED" if self.live else "WAITING FOR SIGNAL"
        if label != self.audio_label:
            self.audio_label = label
            self.cv.itemconfig(self.ids["a_title"], text=label)
            self.cv.itemconfig(self.ids["a_detail"], text="SYSTEM AUDIO / LIVE STEREO" if self.live
                               else "SYSTEM AUDIO / STANDBY")
            self.cv.itemconfig(self.ids["a_tag"], text="LIVE" if self.live else "IDLE",
                               fill=self.C(self.green if self.live else MUTED))

    # ---------------------------------------------------------------- mask
    def draw_mask(self):
        cv = self.cv
        cv.delete("mask")
        if not self.s["livingmask"]:
            return
        x0, y0, x1, y1 = self.mask_area
        sx, sy = (x1 - x0) / 260.0, (y1 - y0) / 150.0
        P = lambda pts: [c for (x, y) in pts for c in (x0 + x * sx, y0 + y * sy)]
        self.poly(P(FACE), "#0b0415", outline="#8c4cff", w=2)
        self.poly(P(HAIR), self.accent)
        for x, y, i in SPECKLES:
            c = "#ffd6e2" if i % 3 else "#ffffff"
            cv.create_rectangle(x0 + x * sx, y0 + y * sy, x0 + x * sx + 1.4 * sx, y0 + y * sy + 1.4 * sy,
                                fill=self.C(c), width=0, tags="mask")
        self.poly(P(VISOR), self.green)
        blink = self.t - self.blink_start
        open_ = .06 if self.sleeping else (max(.05, abs(blink - .11) / .11) if 0 <= blink < .22 else 1.0)
        for (ex, ey, ang) in ((88, 82, -.13), (166, 81, .12)):
            ca, sa = math.cos(ang), math.sin(ang)
            def T(px, py, o=open_):
                py = py * 1.0
                return (ex + px * ca - py * o * 0 - 0, ey)  # placeholder (unused)
            def tf(px, py, scale_y=1.0):
                py = py * scale_y
                return x0 + (ex + px * ca - py * sa) * sx, y0 + (ey + px * sa + py * ca) * sy
            self.poly([c for (px, py) in EYE_SHAPE for c in tf(px, py)], "#07060f")
            if self.sleeping:
                pts = [tf(-17, 0, open_), tf(-1, 7, open_), tf(17, -2, open_)]
                cv.create_line([c for p in pts for c in p], fill=self.C(self.green), width=max(1, 3 * sx), tags="mask")
            else:
                gx, gy = self.gaze
                def ell(rx, ry, ox, oy):
                    pts = []
                    for k in range(18):
                        a = 2 * math.pi * k / 18
                        pts += list(tf(ox + rx * math.cos(a), (oy + ry * math.sin(a)), open_))
                    return pts
                r = 15 * (1 + self.beat * .08)
                cv.create_polygon(ell(r, r, gx * 8, gy * 5), fill=self.C("#0862f4"), outline="", tags="mask")
                cv.create_polygon(ell(20, 20, gx * 6, gy * 4), fill="", outline=self.C(self.green), width=1, tags="mask")
                cv.create_polygon(ell(6, 6, gx * 9, gy * 6), fill=self.C("#fff4f8"), outline="", tags="mask")
        self.poly(P(CHEEK), self.accent)
        if self.ev or self.hover or self.beat > .14:
            self.poly(P(GRIN), "#fff0f8")
        else:
            cv.create_line(P([(109, 122), (120, 125), (126, 120), (139, 125), (149, 120)]), fill=self.C("#ffe2f2"),
                           width=max(1, 1.5 * sx), tags="mask")
        if self.sleeping:
            cv.create_text(x0 + 219 * sx, y0 + (26 + math.sin(self.t) * 3) * sy, text="z z", fill=self.C(self.green),
                           font=self.F(9), tags="mask")

    # ---------------------------------------------------------------- events
    def schedule(self):
        self.next_event = self.t + 28 + (100 - self.s["eventrate"]) * .75 + random.random() * 14

    def start_event(self, kind):
        if kind not in ("takeover", "infection", "visitor") or not self.s[kind]:
            return False
        self.finish_event(schedule=False)
        dur = {"takeover": 12, "infection": 7.5, "visitor": 13}[kind]
        self.ev = dict(kind=kind, start=self.t, duration=dur, quote=QUOTES[self.quote_i % len(QUOTES)])
        self.quote_i += 1
        self.visitor_flags = set()
        if kind == "takeover":
            self.set_header("terminal", captured=True, text="04  CAPRI@YOUR_DESKTOP : ACCESS GRANTED")
            self.cv.itemconfig(self.ids["t_meta1"], fill=self.C("#ffd4e7"))
            self.cv.itemconfig(self.ids["t_meta2"], fill=self.C("#ffd4e7"))
            self.sfx.play("takeover_on")
            self.root.after(500, lambda: self.sfx.play("typing") if self.ev and self.ev["kind"] == "takeover" else None)
        elif kind == "infection":
            self.sfx.play("infect")
        else:
            self.ev["bubble"] = VISITOR_LINES[self.ev_index % 3]
            self.ev_index += 1
            self.visitor_src = self.art.visitor()
            self.visitor_cache = {}
            self.sfx.play("visitor_in")
        return True

    def finish_event(self, schedule=True):
        was = self.ev
        self.ev = None
        for n in self.hdr:
            self.set_header(n)
        for k in ("t_meta1", "t_meta2"):
            if k in self.ids:
                self.cv.itemconfig(self.ids[k], fill=self.C(self.green))
        self.cv.delete("fx")
        self.fx_state = None
        if was and was["kind"] == "takeover":
            self.sfx.play("takeover_off")
        if schedule:
            self.schedule()

    def update_presence(self, dt):
        s = self.s
        beat_t = clamp(self.energy * 1.4, 0, .8) if (s["musicmood"] and self.live) else 0
        self.beat += (beat_t - self.beat) * (1 - math.exp(-dt * 5))
        self.sleeping = (self.t - self.last_inter > 65 and not self.live and not self.ev)
        k = 1 - math.exp(-dt * 7)
        for i in (0, 1):
            self.gaze[i] += (self.gaze_t[i] - self.gaze[i]) * k
        if self.t >= self.next_blink:
            self.blink_start = self.t
            self.next_blink = self.t + 2.8 + random.random() * 4.5
        # configure rate
        if s["eventrate"] != self.rate_cfg:
            self.rate_cfg = s["eventrate"]
            if not s["eventrate"]:
                self.next_event = float("inf")
            else:
                self.schedule() if self.t > 18 or math.isinf(self.next_event) else None
        if not self.ev and s["eventrate"] > 0 and self.t >= self.next_event:
            kinds = ["takeover", "visitor", "infection"]
            for _ in range(3):
                kind = kinds[self.ev_index % 3]
                self.ev_index += 1
                if self.start_event(kind):
                    break
            if not self.ev:
                self.schedule()
        if self.ev and self.t - self.ev["start"] >= self.ev["duration"]:
            chain = self.ev["kind"] == "takeover" and s["infection"]
            self.finish_event()
            if chain:
                self.start_event("infection")
        k = self.ev["kind"] if self.ev else None
        mood = ("ROOT / MINE" if k == "takeover" else "OUT OF BOUNDS" if k == "visitor" else
                "IN THE WIRES" if k == "infection" else "DREAMING" if self.sleeping else
                "FEELING THE BEAT" if self.live and s["musicmood"] else "I SEE YOU" if self.hover else "CAPRI / ONLINE")
        if mood != self.last_mood:
            self.last_mood = mood
            self.cv.itemconfig(self.ids["mood"], text=mood)
            whisper = (self.ev["quote"][0] if self.ev else "quiet signal. do not wake." if self.sleeping else
                       "she likes this frequency." if self.live and s["musicmood"] else
                       WHISPERS[self.quote_i % len(WHISPERS)])
            self.cv.itemconfig(self.ids["whisper"], text=whisper)
        # header beat flash
        if s["musicmood"]:
            for n, H in self.hdr.items():
                base = H["color"]
                self.cv.itemconfig(H["bar"], fill=self.C(mixc(base, self.green, self.beat * .22)))
        # fx layer
        if self.ev and self.ev["kind"] in ("infection", "visitor"):
            self.cv.delete("fx")
            el = self.t - self.ev["start"]
            if self.ev["kind"] == "infection":
                self.draw_infection(el)
            else:
                self.draw_visitor(el)
            self.cv.tag_raise("fx")

    # --- infection
    def draw_infection(self, el):
        u = self.u
        fade = clamp((7.5 - el) / 1.5, 0, 1)
        for index, n in enumerate([m for m in self.NAMES if m in self.hdr]):
            progress = (el - index * .38) / 1.1
            if progress <= 0:
                continue
            if progress >= .35 and n in self.hdr and self.hdr[n]["color"] != self.green:
                self.set_header(n, infected=True, text="0%d  CAPRI_WAS_HERE / 0xC4" % (index + 1))
            x0, y0, x1, y1 = self.R[n]
            w, h = x1 - x0, y1 - y0
            per = 2 * (w + h)
            drawn = per * clamp(progress, 0, 1)
            pts = [(x0 + 1, y0 + 1)]
            corners = [(x1 - 1, y0 + 1), (x1 - 1, y1 - 1), (x0 + 1, y1 - 1), (x0 + 1, y0 + 1)]
            seg_len = [w, h, w, h]
            acc, cur = 0.0, pts[0]
            for (cx, cy), L in zip(corners, seg_len):
                if acc + L <= drawn:
                    pts.append((cx, cy))
                    acc += L
                    cur = (cx, cy)
                else:
                    f = (drawn - acc) / L if L else 0
                    pts.append((lerp(cur[0], cx, f), lerp(cur[1], cy, f)))
                    break
            col = mixc(PANEL, self.green, .6 * fade)
            if len(pts) > 1:
                self.cv.create_line([c for p in pts for c in p], fill=self.C(col), width=max(1, int(2 * u)), tags="fx")
            dist = (self.t * 180 + index * 135) % per
            px, py = x0, y0
            if dist < w:
                px += dist
            elif dist < w + h:
                px += w
                py += dist - w
            elif dist < 2 * w + h:
                px += 2 * w + h - dist
                py += h
            else:
                py += per - dist
            self.cv.create_rectangle(px - 3, py - 3, px + 3, py + 3, fill=self.C(mixc(PANEL, self.green, .9 * fade)),
                                     width=0, tags="fx")
        if 1.8 < el < 6.2:
            x0, y0, x1, y1 = self.code_box
            self.eyes(x0 + (x1 - x0) * .77, y0 + (y1 - y0) * .42 + 0, 92 * u, "fx", "#0c080e", .4 * fade)
            self.txt(x0 + (x1 - x0) * .59, y0 + (y1 - y0) * .60, "I AM IN THE WIRES.", 11,
                     mixc(PANEL, self.green, fade), tags=("fx",))

    # --- visitor
    def visitor_points(self):
        u = self.u
        pr, tr, sr = self.R["primary"], self.R["terminal"], self.R["secondary"]
        cont = lambda x, y: (clamp(x, 12 * u, self.W - 218 * u), clamp(y, 65 * u, self.H - 250 * u))
        return [cont(pr[2] - 145 * u, pr[1] + (pr[3] - pr[1]) * .28),
                cont(tr[2] - 205 * u, tr[1] - 160 * u),
                cont(sr[0] + (15 if self.wide else 75) * u, sr[1] + (sr[3] - sr[1]) * .38)]

    def visitor_image(self, scale, opacity, crop_top, rot):
        bw, bh = int(206 * self.u * scale), int(226 * self.u * scale)
        key = (bw, bh)
        if key not in self.visitor_cache:
            src = self.visitor_src
            r = min(bw / src.width, bh / src.height)
            im = src.resize((max(1, int(src.width * r)), max(1, int(src.height * r))), Image.LANCZOS)
            canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            canvas.paste(im, ((bw - im.width) // 2, (bh - im.height) // 2), im)
            self.visitor_cache = {key: canvas}
        im = self.visitor_cache[key]
        if abs(rot) > .3:
            im = im.rotate(-rot, resample=Image.BICUBIC)
        if crop_top > 0:
            cut = int(im.height * crop_top)
            im = im.crop((0, cut, im.width, im.height))
        else:
            cut = 0
        if opacity < .99:
            a = im.getchannel("A").point(lambda p: int(p * opacity))
            im = im.copy()
            im.putalpha(a)
        return im, cut

    def draw_visitor(self, el):
        u = self.u
        pts = self.visitor_points()
        x, y = pts[0]
        rot = 0.0
        if 2.4 < el < 6.2:
            p = clamp((el - 2.4) / 3.8, 0, 1)
            e = ease(p)
            x, y = lerp(pts[0][0], pts[1][0], e), lerp(pts[0][1], pts[1][1], e) - math.sin(p * math.pi) * 48 * u
            rot = math.sin(p * math.pi * 2) * 7
            if "move" not in self.visitor_flags:
                self.visitor_flags.add("move")
                self.sfx.play("visitor_move")
        elif 6.2 <= el < 8.9:
            x, y = pts[1][0], pts[1][1] + math.sin(self.t * 2.2) * 3 * u
            rot = math.sin(self.t * 2) * 3
        elif el >= 8.9:
            p = ease((el - 8.9) / 1.7)
            x, y = lerp(pts[1][0], pts[2][0], p), lerp(pts[1][1], pts[2][1], p) - math.sin(p * math.pi) * 20 * u
            if "move2" not in self.visitor_flags:
                self.visitor_flags.add("move2")
                self.sfx.play("visitor_move")
        appear = ease(el / .8)
        dissolve = clamp((el - 11) / 2, 0, 1)
        if dissolve > 0 and "out" not in self.visitor_flags:
            self.visitor_flags.add("out")
            self.sfx.play("visitor_out")
        op = appear * (1 - dissolve)
        if op > .01:
            im, cut = self.visitor_image(.88 + .12 * appear, op, dissolve, rot)
            self.vis_photo = ImageTk.PhotoImage(im)
            self.vis_box = (x, y + cut, x + im.width, y + 226 * u)
            self.cv.create_image(x, y + cut, anchor="nw", image=self.vis_photo, tags="fx")
        if 1 < el < 10:
            bx, by = x + 103 * u, y + 6 * u
            t = self.cv.create_text(bx, by - 9 * u, text=self.ev["bubble"], anchor="s", fill=self.C("#f5d5e5"),
                                    font=self.F(11), width=int(208 * u), justify="left", tags="fx")
            bb = self.cv.bbox(t)
            r = self.cv.create_rectangle(bb[0] - 11 * u, bb[1] - 9 * u, bb[2] + 11 * u, bb[3] + 9 * u,
                                         fill=self.C("#100913"), outline=self.C(self.green), tags="fx")
            self.cv.tag_lower(r, t)
        if dissolve > 0:
            for i in range(64):
                px = x + hash2(i, 3) * 200 * u + (hash2(i, 7) - .5) * dissolve * 150 * u
                py = y + hash2(i, 8) * 210 * u - dissolve * (25 + hash2(i, 9) * 110) * u
                c = self.accent if i % 3 else self.green
                self.cv.create_rectangle(px, py, px + (2 + hash2(i, 5) * 4) * u, py + (1 + hash2(i, 6) * 3) * u,
                                         fill=self.C(mixc("#0c080e", c, (1 - dissolve) * .8)), width=0, tags="fx")

    # ---------------------------------------------------------------- glitch / scenes
    def trigger_glitch(self, force=False):
        if not self.s["glitch"] and not force:
            return
        self.glitch_left = .11 + random.random() * .14
        self.glitch_seed = random.random()
        self.set_top_status(True)

    def clear_glitch(self):
        self.glitch_left = 0
        self.cv.delete("gflash")
        self.set_top_status(False)
        for n in self.surf:
            self.surf[n]["dirty"] = True

    def draw_glitch_flash(self):
        self.cv.delete("gflash")
        W, H = self.W, self.H
        st = self.s["glitch"] / 100.0
        for yf, col in ((.27, self.green), (.69, self.accent)):
            y = H * yf + random.randint(-6, 6)
            self.cv.create_rectangle(0, y, W, y + max(1, H * .012), fill=self.C(mixc(BG, col, .1 + st * .12)),
                                     width=0, tags="gflash")
        self.cv.tag_raise("gflash")
        self.cv.tag_raise("fx")

    def next_scene(self):
        self.scene = (self.scene + 1) % len(SCENES)
        self.next_slide = self.t + 60
        self.set_scene_images()
        if self.s["memories"]:
            for i, n in enumerate(("primary", "secondary", "floating")):
                self.rec_start[n] = self.t + i * .11
            self.sfx.play("memory")
        self.trigger_glitch()

    # ---------------------------------------------------------------- loop
    def tick(self):
        t0 = time.perf_counter()
        if self.laid_out and self.root.state() != "iconic":
            dt = min(t0 - self.last, .1) if self.last else 1 / FPS
            self.last = t0
            try:
                self.music.update()
                if self.wallpaper:
                    self.poll_desktop_input()
                self.update(dt)
            except tk.TclError:
                return
        else:
            self.last = None
        delay = max(1, int(1000 / FPS - (time.perf_counter() - t0) * 1000))
        try:
            self.root.after(delay, self.tick)
        except tk.TclError:
            pass

    def update(self, dt):
        s = self.s
        self.t += dt
        self.frame += 1
        if not (self.ev and self.ev["kind"] == "takeover"):
            self.code_offset += dt * s["codespeed"] * .36 * self.u
        self.code_offset %= len(SOURCE) * 22 * self.u
        # parallax
        if s["parallax"]:
            k = 1 - math.exp(-dt * 10)
            for i in (0, 1):
                self.par[i] += (self.par_t[i] - self.par[i]) * k
        else:
            self.par = [0.0, 0.0]
        self.update_audio(dt)
        self.update_presence(dt)
        self.draw_mask()
        self.draw_code()
        self.paint_time()
        # cursor blink in the CAPRION title
        self.cv.itemconfig(self.ids["cursor"], state="normal" if int(self.t / .8) % 2 == 0 else "hidden")
        if self.t - self.last_hex > 1.4:
            self.update_hex()
            self.last_hex = self.t
        if s["slideshow"] and self.t >= self.next_slide:
            self.next_scene()
        if s["glitch"] and self.t >= self.next_glitch:
            self.trigger_glitch()
            self.next_glitch = self.t + 5 + (1 - s["glitch"] / 100) * 22 + random.random() * 8
        if self.glitch_left > 0:
            self.glitch_left -= dt
            self.draw_glitch_flash()
            if self.glitch_left <= 0:
                self.clear_glitch()
        for n in ("primary", "secondary", "floating"):
            if n in self.surf:
                self.render_portrait(n)
        if "floating" in self.surf:
            self.float_window()

    def float_window(self):
        # gentle bobbing of the cached-memory window (no rotation in tkinter)
        off = math.sin(self.t * 2 * math.pi / 22) * 4.5 * self.u
        if abs(off - getattr(self, "_float_off", 0)) > .6:
            self.cv.move("floating", 0, off - getattr(self, "_float_off", 0))
            self._float_off = off
            s = self.surf["floating"]
            s["y"] = int(self.R["floating"][1] + 25 * self.u + off)
            self.cv.tag_raise("floating")

    # ---------------------------------------------------------------- input
    def on_motion(self, e):
        self.mouse = (e.x, e.y)
        self.last_inter = self.t
        W, H = max(1, self.W), max(1, self.H)
        if self.s["parallax"]:
            self.par_t = [(e.x / W - .5) * -10 * self.u, (e.y / H - .5) * -7 * self.u]
        mx0, my0, mx1, my1 = self.mask_box
        self.gaze_t = [clamp((e.x - (mx0 + mx1) / 2) / (W * .35), -1, 1), clamp((e.y - (my0 + my1) / 2) / (H * .4), -1, 1)]
        h = self.s["livingmask"] and mx0 <= e.x <= mx1 and my0 <= e.y <= my1
        self.hover = bool(h)
        over_vis = self.ev and self.ev["kind"] == "visitor" and self.point_in_visitor(e.x, e.y)
        gx0, gy0, gx1, gy1 = self.gear_box
        over_gear = gx0 <= e.x <= gx1 and gy0 <= e.y <= gy1
        over_mute = self.in_box(self.mute_box, e.x, e.y)
        self.cv.configure(cursor="hand2" if (h or over_vis or over_gear or over_mute) else "arrow")

    def point_in_visitor(self, x, y):
        b = getattr(self, "vis_box", None)
        return bool(b and b[0] <= x <= b[2] and b[1] <= y <= b[3])

    def on_click(self, e):
        gx0, gy0, gx1, gy1 = self.gear_box
        if gx0 <= e.x <= gx1 and gy0 <= e.y <= gy1:
            self.toggle_settings()
            return
        if self.in_box(self.mute_box, e.x, e.y):
            self.toggle_mute()
            return
        if self.ev and self.ev["kind"] == "visitor" and self.point_in_visitor(e.x, e.y):
            self.sfx.play("click")
            self.start_event("infection")
            return
        mx0, my0, mx1, my1 = self.mask_box
        if self.s["livingmask"] and mx0 <= e.x <= mx1 and my0 <= e.y <= my1:
            self.sfx.play("click")
            self.start_event("takeover") or self.start_event("visitor") or self.start_event("infection")

    RU = dict(zip("щтпешмьф", "ontivmma"))

    def on_key(self, e):
        if isinstance(e.widget, (tk.Scale, tk.Entry)):
            return
        ch = (e.char or "").lower()
        ch = self.RU.get(ch, ch)
        if ch == "o":
            self.toggle_settings()
        elif ch == "n":
            self.next_scene()
        elif ch == "g":
            self.trigger_glitch(True)
        elif ch in ("t", "i", "v"):
            if self.start_event({"t": "takeover", "i": "infection", "v": "visitor"}[ch]):
                self.sfx.play("click")
        elif ch == "m":
            self.toggle_mute()
        elif ch == "a":
            self.demo_audio = not self.demo_audio
        elif e.keysym == "F11":
            self.set_fullscreen(not self.fullscreen)
        elif e.keysym == "Escape":
            if self.settings_win and self.settings_win.winfo_viewable():
                self.settings_win.withdraw()
            elif self.fullscreen:
                self.set_fullscreen(False)

    def set_fullscreen(self, on):
        self.fullscreen = on
        self.root.attributes("-fullscreen", on)

    # ---------------------------------------------------------------- settings window
    def save(self):
        try:
            json.dump(self.s, open(SETTINGS_FILE, "w"), indent=1)
        except Exception:
            pass

    def toggle_settings(self):
        if self.settings_win is None:
            self.build_settings()
        elif self.settings_win.winfo_viewable():
            self.settings_win.withdraw()
        else:
            self.settings_win.deiconify()
            self.settings_win.lift()

    def build_settings(self):
        w = tk.Toplevel(self.root)
        self.settings_win = w
        w.title("NEON PROTOCOL / SETTINGS")
        w.configure(bg="#110b14", padx=14, pady=10)
        w.attributes("-topmost", True)
        w.protocol("WM_DELETE_WINDOW", w.withdraw)
        fnt = (self.family, 9)
        relayout = {"accent", "secondary", "brightness", "scanlines", "showclock", "livingmask"}
        self.vars = {}

        def changed(key):
            def cb(*_):
                v = self.vars[key].get()
                self.s[key] = type(DEFAULTS[key])(v) if not isinstance(DEFAULTS[key], bool) else bool(v)
                if key in relayout and key != "livingmask":
                    self.root.after(30, self.layout)
                if key == "musicvolume":
                    self.music.set_volume()
                if key == "sfx":
                    self.sfx.stop_all() if not self.s["sfx"] else None
                    self.music.set_muted(not self.s["sfx"])
                    self.set_mute_icon()
                if key == "glitch" and not self.s["glitch"]:
                    self.clear_glitch()
                self.save()
            return cb

        def scale(key, text, lo, hi):
            f = tk.Frame(w, bg="#110b14")
            f.pack(fill="x", pady=1)
            tk.Label(f, text=text, bg="#110b14", fg=TEXT, font=fnt, anchor="w", width=26).pack(side="left")
            v = tk.IntVar(value=self.s[key])
            self.vars[key] = v
            sc = tk.Scale(f, from_=lo, to=hi, orient="horizontal", variable=v, showvalue=False, length=140,
                          bg="#110b14", fg=TEXT, troughcolor="#30101e", highlightthickness=0,
                          activebackground=self.accent, command=lambda _v, k=key: changed(k)())
            sc.pack(side="right")

        def check(key, text):
            v = tk.BooleanVar(value=self.s[key])
            self.vars[key] = v
            tk.Checkbutton(w, text=text, variable=v, command=changed(key), bg="#110b14", fg=TEXT, font=fnt,
                           selectcolor="#1b1020", activebackground="#110b14", activeforeground=TEXT,
                           anchor="w").pack(fill="x")

        def color(key, text):
            f = tk.Frame(w, bg="#110b14")
            f.pack(fill="x", pady=2)
            tk.Label(f, text=text, bg="#110b14", fg=TEXT, font=fnt, anchor="w", width=26).pack(side="left")
            b = tk.Button(f, bg=self.s[key], width=4, relief="flat")
            def pick():
                from tkinter import colorchooser
                c = colorchooser.askcolor(color=self.s[key], parent=w)[1]
                if c:
                    self.s[key] = c
                    b.configure(bg=c)
                    self.save()
                    self.root.after(30, self.layout)
            b.configure(command=pick)
            b.pack(side="right")

        tk.Label(w, text="NEON PROTOCOL / SETTINGS", bg="#110b14", fg=self.green, font=(self.family, 11, "bold")
                 ).pack(anchor="w", pady=(0, 6))
        scale("glitch", "Glitches", 0, 100)
        scale("codespeed", "Code speed", 0, 200)
        scale("brightness", "Brightness", 30, 120)
        scale("sensitivity", "Audio reaction", 0, 200)
        color("accent", "Pink accent")
        color("secondary", "Green accent")
        check("parallax", "Mouse parallax")
        check("scanlines", "CRT scanlines")
        check("showclock", "Clock and calendar")
        check("slideshow", "Change frames every minute")
        tk.Label(w, text="GHOST INSIDE / CAPRI'S PRESENCE", bg="#110b14", fg=self.green, font=fnt
                 ).pack(anchor="w", pady=(10, 2))
        check("livingmask", "Living mask and gaze")
        check("takeover", "Terminal takeovers")
        check("infection", "Green window infection")
        check("visitor", "Avatar leaves the windows")
        check("memories", "Memory restoration")
        check("musicmood", "Mood follows music")
        scale("eventrate", "Event frequency (0 = manual)", 0, 100)
        tk.Label(w, text="SOUND / MUSIC", bg="#110b14", fg=self.green, font=fnt).pack(anchor="w", pady=(10, 2))
        check("sfx", "Sound: music and effects (M)")
        scale("sfxvolume", "Effects volume", 0, 100)
        scale("musicvolume", "Music volume", 0, 100)
        def pick_music():
            from tkinter import filedialog
            f = filedialog.askopenfilename(parent=w, title="Background music",
                                           filetypes=[("Audio", "*.mp3 *.mpeg *.mpg *.mp2 *.wav *.ogg *.flac"), ("All", "*.*")])
            if f:
                self.s["musicfile"] = f
                self.save()
                self.music.start()
                mus_lbl.configure(text=self.music.status)

        def music_folder():
            from tkinter import filedialog
            d = filedialog.askdirectory(parent=w, title="Choose a music folder")
            if d:
                self.s["musicdir"] = d
                self.s["musicfile"] = ""
                self.save()
                self.music.start()
                mus_lbl.configure(text=self.music.status)

        def music_default():
            self.s["musicdir"] = ""
            self.s["musicfile"] = ""
            self.save()
            self.music.start()
            mus_lbl.configure(text=self.music.status)

        mf = tk.Frame(w, bg="#110b14")
        mf.pack(fill="x", pady=2)
        tk.Button(mf, text="Music: choose file…", command=pick_music, bg="#1b1020", fg=self.green,
                  relief="flat", font=fnt).pack(side="left")
        tk.Button(mf, text="Folder…", command=music_folder, bg="#1b1020", fg=self.green,
                  relief="flat", font=fnt).pack(side="left", padx=4)
        tk.Button(mf, text="Default", command=music_default, bg="#1b1020", fg=self.green,
                  relief="flat", font=fnt).pack(side="left")
        tk.Button(mf, text="⏭", command=lambda: (self.music.next(), mus_lbl.configure(text=self.music.status)),
                  bg="#1b1020", fg=self.green, relief="flat", font=fnt).pack(side="left")
        mus_lbl = tk.Label(w, text=self.music.status, bg="#110b14", fg="#956e80", wraplength=330, justify="left",
                           font=(self.family, 8), anchor="w")
        mus_lbl.pack(fill="x")
        row = tk.Frame(w, bg="#110b14")
        row.pack(fill="x", pady=(10, 2))
        for text, cmd in (("Takeover", lambda: self.start_event("takeover")),
                          ("Pulse", lambda: self.start_event("infection")),
                          ("Call Capri", lambda: self.start_event("visitor"))):
            tk.Button(row, text=text, command=cmd, bg="#1b1020", fg=self.green, relief="flat", font=fnt
                      ).pack(side="left", expand=True, fill="x", padx=2)
        row2 = tk.Frame(w, bg="#110b14")
        row2.pack(fill="x", pady=2)
        tk.Button(row2, text="Next frame", command=self.next_scene, bg="#1b1020", fg=self.green, relief="flat",
                  font=fnt).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(row2, text="Reset", command=self.reset_settings, bg="#1b1020", fg=self.green, relief="flat",
                  font=fnt).pack(side="left", expand=True, fill="x", padx=2)
        tk.Label(w, text="O settings · N next frame · G glitch · T takeover · I pulse\nV call Capri · M sound · A demo audio · F11 fullscreen",
                 bg="#110b14", fg="#956e80", font=(self.family, 8), justify="left").pack(anchor="w", pady=(8, 0))

    def reset_settings(self):
        self.s.update(DEFAULTS)
        self.save()
        if self.settings_win:
            self.settings_win.destroy()
            self.settings_win = None
            self.build_settings()
        self.root.after(30, self.layout)

    def quit(self):
        self.save()
        self.music.shutdown()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:      # crisp, correctly sized window on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    if "--wallpaper" in sys.argv:      # pythonw has no console: keep a log next to the script
        try:
            sys.stdout = sys.stderr = open(os.path.join(BASE, "caprion_wallpaper.log"), "w", encoding="utf-8")
        except Exception:
            pass
    App(fullscreen="--fullscreen" in sys.argv, wallpaper="--wallpaper" in sys.argv).run()