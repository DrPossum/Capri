import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import soundcard as sc
import random
import time
import threading
import datetime
import calendar

# --- EXACT CONFIGURATION DECODED FROM style.css & presence.js ---
COLORS = {
    'bg': '#09070d',
    'accent': '#ff205f',      # Exact pink from CSS
    'green': '#00ef72',       # Exact green from CSS
    'violet': '#8c4cff',      # Exact purple edge accent
    'text': '#f6cbd5',
    'muted': '#946574',
    'border': '#793043',      # Exact border color
    'terminal_bg': '#0c080e',
    'dark_green': '#163021'
}
FONTS = {
    'topbar': ('Consolas', 9, 'bold'),
    'header': ('Consolas', 10, 'bold'),
    'clock_big': ('Consolas', 55, 'bold'),
    'clock_sec': ('Consolas', 28, 'bold'),
    'world_clock': ('Consolas', 24, 'bold'),
    'small': ('Consolas', 8),
    'tiny': ('Consolas', 7),
    'terminal': ('Consolas', 9),
    'title_big': ('Arial', 42, 'bold'),
    'title_small': ('Consolas', 8, 'bold')
}

# --- AUDIO ENGINE ---
class AudioEngine:
    def __init__(self):
        self.levels = np.zeros(64)
        self.running = True
        self.thread = threading.Thread(target=self._capture_audio, daemon=True)
        self.thread.start()

    def _capture_audio(self):
        try:
            speaker = sc.default_speaker()
            mics = sc.all_microphones(include_loopback=True)
            loopback = next((m for m in mics if m.isloopback), None)
            if not loopback: return

            with loopback.recorder(samplerate=44100) as mic:
                while self.running:
                    data = mic.record(numframes=1024)
                    mono = np.mean(data, axis=1)
                    fft_data = np.abs(np.fft.rfft(mono))
                    bins = np.array_split(fft_data[:128], 64)
                    raw_levels = [np.mean(b) for b in bins]
                    self.levels = np.clip(raw_levels * 50, 0, 1)
        except Exception:
            pass

    def stop(self):
        self.running = False

# --- GLITCH IMAGE WIDGET (Decoded from presence.js) ---
class GlitchImagePanel(tk.Canvas):
    def __init__(self, parent, primary_image, glitch_images=None, text_overlays=None, **kwargs):
        super().__init__(parent, bg=COLORS['bg'], highlightthickness=0, **kwargs)
        self.text_overlays = text_overlays or []
        self.glitch_active = False
        self.glitch_timer = 0
        
        try:
            self.primary_img = Image.open(primary_image).convert("RGBA")
        except:
            self.primary_img = Image.new('RGBA', (400, 600), color=COLORS['bg'])

        self.glitch_imgs = []
        if glitch_images:
            for path in glitch_images:
                try:
                    img = Image.open(path).convert("RGBA")
                    self.glitch_imgs.append(img)
                except: pass

        self.bind("<Configure>", self.redraw)

    def trigger_glitch(self):
        self.glitch_active = True
        self.glitch_timer = time.time() + 0.2 

    def redraw(self, event=None):
        if self.winfo_width() < 10 or self.winfo_height() < 10: return
        img = self.primary_img.copy()
        
        if self.glitch_active:
            if time.time() > self.glitch_timer:
                self.glitch_active = False
            else:
                # Exact logic from wallpaper.js drawGlitch()
                for _ in range(random.randint(5, 12)):
                    y = random.randint(0, img.height - 20)
                    slice_h = random.randint(10, 60)
                    source_img = random.choice([self.primary_img] + self.glitch_imgs)
                    source_img = source_img.resize(img.size, Image.Resampling.LANCZOS)
                    box = (0, y, img.width, min(y + slice_h, img.height))
                    
                    if box[3] > box[1]:
                        slice_img = source_img.crop(box)
                        offset_x = random.randint(-40, 40)
                        tint_color = COLORS['accent'] if random.random() > 0.5 else COLORS['green']
                        tint = Image.new('RGBA', slice_img.size, tint_color)
                        slice_img = Image.blend(slice_img, tint, alpha=0.2) # alpha 0.2 from JS
                        img.paste(slice_img, (offset_x, y), slice_img)

        self.display_img = img.resize((self.winfo_width(), self.winfo_height()), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(self.display_img)
        
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self.tk_img)

        for txt in self.text_overlays:
            self.create_text(txt.get('x', 20), txt.get('y', 20), text=txt['text'], 
                             fill=txt.get('color', 'white'), font=txt.get('font', FONTS['small']), 
                             anchor=txt.get('anchor', 'nw'))

# --- CALENDAR WIDGET ---
class CalendarWidget(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['terminal_bg'], **kwargs)
        self.days = ['MO','TU','WE','TH','FR','SA','SU']
        self.labels = []
        
        for i, d in enumerate(self.days):
            tk.Label(self, text=d, bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).grid(row=0, column=i, padx=2, pady=2)
            
        for r in range(1, 7):
            row_labels = []
            for c in range(7):
                lbl = tk.Label(self, text="", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['tiny'], width=2)
                lbl.grid(row=r, column=c, padx=1, pady=1)
                row_labels.append(lbl)
            self.labels.append(row_labels)
        self.update_calendar()

    def update_calendar(self):
        now = datetime.datetime.now()
        cal = calendar.Calendar(firstweekday=0) 
        month_days = cal.monthdayscalendar(now.year, now.month)
        
        for r, week in enumerate(month_days):
            if r >= len(self.labels): break
            for c, day in enumerate(week):
                lbl = self.labels[r][c]
                if day == 0:
                    lbl.config(text="", bg=COLORS['terminal_bg'])
                else:
                    lbl.config(text=str(day).zfill(2))
                    if day == now.day:
                        lbl.config(bg=COLORS['accent'], fg="#17080f")
                    elif c >= 5:
                        lbl.config(fg=COLORS['green'], bg=COLORS['terminal_bg'])
                    else:
                        lbl.config(fg=COLORS['text'], bg=COLORS['terminal_bg'])

# --- THE LIVING MASK (Decoded exactly from presence.js drawMask) ---
class CapriMask(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['terminal_bg'], highlightthickness=0, **kwargs)
        self.gaze_x = 0
        self.gaze_y = 0
        self.blink = False
        self.bind("<Configure>", lambda e: self.draw_face())

    def update_gaze(self, mouse_x, mouse_y):
        cx = self.winfo_width() / 2
        cy = self.winfo_height() / 2
        dx = mouse_x - self.winfo_rootx() - cx
        dy = mouse_y - self.winfo_rooty() - cy
        dist = max(1, (dx**2 + dy**2)**0.5)
        self.gaze_x = max(-1, min(1, (dx / dist) * 0.15))
        self.gaze_y = max(-1, min(1, (dy / dist) * 0.15))
        self.draw_face()

    def toggle_blink(self):
        self.blink = True
        self.draw_face()
        self.after(150, self.end_blink)

    def end_blink(self):
        self.blink = False
        self.draw_face()

    def draw_face(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10: return
        scale = min(w / 260, h / 150)
        ox, oy = (w - 260 * scale) / 2, (h - 150 * scale) / 2
        def sx(val): return ox + val * scale
        def sy(val): return oy + val * scale

        # Exact hair polygons
        hair_dark = [(45,39),(205,32),(222,98),(168,144),(73,135),(27,85)]
        self.create_polygon([(sx(x), sy(y)) for x,y in hair_dark], fill="#0b0415", outline=COLORS['violet'], width=max(1, int(2*scale)))
        hair_pink = [(14,53),(58,41),(45,8),(95,35),(104,7),(138,36),(190,4),(177,38),(246,25),(209,61),(251,61),(212,89),(221,124),(180,107),(67,116),(25,139),(35,95),(7,110),(29,76)]
        self.create_polygon([(sx(x), sy(y)) for x,y in hair_pink], fill=COLORS['accent'], outline="")
        eye_mask = [(57,63),(101,48),(124,72),(158,48),(205,55),(191,107),(66,108)]
        self.create_polygon([(sx(x), sy(y)) for x,y in eye_mask], fill=COLORS['green'], outline="")

        for ex, ey in [(88,82), (166,81)]:
            socket = [(-28,-22),(4,-17),(29,-6),(23,27),(-3,22),(-30,13)]
            self.create_polygon([(sx(ex+x), sy(ey+y)) for x,y in socket], fill="#07060f", outline="")
            if self.blink:
                self.create_line(sx(ex-17), sy(ey), sx(ex-1), sy(ey+7), sx(ex+17), sy(ey-2), fill=COLORS['green'], width=max(1, int(3*scale)))
            else:
                iris_x, iris_y = sx(ex + self.gaze_x * 50), sy(ey + self.gaze_y * 50)
                self.create_oval(iris_x-15*scale, iris_y-15*scale, iris_x+15*scale, iris_y+15*scale, fill="#0862f4", outline="")
                self.create_oval(iris_x-20*scale, iris_y-20*scale, iris_x+20*scale, iris_y+20*scale, outline=COLORS['green'], width=max(1, int(1.5*scale)))
                self.create_oval(iris_x-6*scale, iris_y-6*scale, iris_x+6*scale, iris_y+6*scale, fill="#fff4f8", outline="")
        
        nose = [(103,39),(133,17),(148,63),(124,91)]
        self.create_polygon([(sx(x), sy(y)) for x,y in nose], fill=COLORS['accent'], outline="")

# --- SCROLLING TERMINAL WIDGET WITH EXACT TAKEOVER ---
class TerminalWidget(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['terminal_bg'], highlightthickness=0, **kwargs)
        self.lines = [
            "// CAPRION / NEON PROTOCOL :: private uplink",
            "import { ghost, memory } from 'neural/core';",
            "const identity = 'CAPRI';",
            "const channel = await net.connect('night_city');",
            "async function establishLink(subject) {",
            "  const key = await crypto.derive(subject.id);",
            "  let signal = new Signal({ encrypted: true });",
            "  // there is someone on the other side",
            "  await channel.handshake(key);",
            "  return signal.attach(subject.memory);",
            "}",
            "[ OK ] neural interface ........... connected",
            "[ OK ] memory integrity ........... verified",
            "[ OK ] ghost signature ............ detected",
            "> decrypting cached memories / sector 0xC4",
            "const fragment = memory.read(0x00C4);",
            "if (fragment.alive) {",
            "  ghost.restore(fragment);",
            "}",
            "while (ghost.isOnline()) {",
            "  const pulse = await signal.receive();",
            "  channel.write(pulse.encode('CAPRI'));",
            "  await memory.keepAlive({ forever: true });",
            "}",
            "[ SYS ] refusing to disappear"
        ]
        self.scroll_y = 0
        self.line_height = 16
        self.speed = 0.4
        self.takeover = False
        self.takeover_timer = 0
        self.bind("<Configure>", lambda e: self.redraw())

    def trigger_takeover(self):
        self.takeover = True
        self.takeover_timer = time.time() + 12 # From presence.js duration

    def update_scroll(self):
        if self.takeover:
            if time.time() > self.takeover_timer:
                self.takeover = False
            else:
                self.redraw()
                return

        self.scroll_y -= self.speed
        if self.scroll_y <= -self.line_height:
            self.scroll_y = 0
            self.lines.append(self.lines.pop(0))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10: return

        if self.takeover:
            # EXACT text and coordinates from presence.js drawTakeover()
            margin = 20
            self.create_text(margin, 18, anchor="nw", text="[ ROOT ACCESS OVERRIDDEN / SIGNATURE 0xC4 ]", fill=COLORS['green'], font=FONTS['terminal'])
            self.create_text(margin, 49, anchor="nw", text="CAPRI HAS THE KEYS. █", fill="#ffe6f1", font=('Consolas', 18, 'bold'))
            self.create_text(margin, 84, anchor="nw", text="> Привет. Я немного побуду здесь.", fill=COLORS['accent'], font=FONTS['terminal'])
            
            # Draw Eyes (w*.76, h*.43)
            eye_y = h * 0.43
            eye_x1 = w * 0.76 - 36
            eye_x2 = w * 0.76 + 36
            
            for ex in [eye_x1, eye_x2]:
                self.create_polygon(ex-30, eye_y-22, ex+25, eye_y-17, ex+30, eye_y+22, ex-24, eye_y+17, fill=COLORS['green'], outline="")
                self.create_oval(ex-18, eye_y-18, ex+18, eye_y+18, fill="#090711", outline="")
                self.create_oval(ex-11, eye_y-11, ex+11, eye_y+11, fill="#156dff", outline="")
                self.create_oval(ex-4, eye_y-4, ex+4, eye_y+4, fill="#fff", outline="")

            self.create_text(w*0.54, h*0.61, anchor="nw", text="NOT A BUG. A VISITOR.", fill=COLORS['green'], font=FONTS['terminal'])
            self.create_text(w*0.54, h*0.70, anchor="nw", text="Ты слышишь музыку?\nЯ вижу её.", fill="#f7ccde", font=FONTS['terminal'])
            self.create_text(w*0.54, h-29, anchor="nw", text="[ decorating your terminal... ]", fill="#739784", font=FONTS['terminal'])
            return

        num_lines = int(h / self.line_height) + 2
        for i in range(num_lines):
            idx = i % len(self.lines)
            text = self.lines[idx]
            y = i * self.line_height + self.scroll_y
            color = COLORS['muted']
            if text.startswith("["): color = COLORS['green']
            elif text.startswith("//") or text.startswith(">"): color = "#604153"
            elif "const" in text or "await" in text or "async" in text: color = COLORS['accent']
            self.create_text(10, y, anchor="nw", text=f"{idx:03d}  {text}", fill=color, font=FONTS['terminal'])

# --- DIAGNOSTICS WIDGET ---
class DiagnosticsWidget(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['terminal_bg'], **kwargs)
        top = tk.Frame(self, bg=COLORS['terminal_bg'])
        top.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(top, text="IDENTITY VERIFIED", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.LEFT)
        tk.Label(top, text="[ CAPRI ]", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['tiny']).pack(side=tk.RIGHT)
        
        self.add_bar("SYNC", 0.94, COLORS['green'])
        self.add_bar("GHOST", 1.0, COLORS['accent'])
        
        hex_frame = tk.Frame(self, bg=COLORS['terminal_bg'])
        hex_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.hex_lbl = tk.Label(hex_frame, text="77 8A 8F 53 5A 19 A0 AC 88 07 0F 3C 65 28 B5 02\nBE 3F 02 79 CF 08 3C 8C 83 51 94 89 6B 63 32 0B 0A", 
                 bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny'], justify=tk.LEFT)
        self.hex_lbl.pack(anchor="w")

    def add_bar(self, label, value, color):
        frame = tk.Frame(self, bg=COLORS['terminal_bg'])
        frame.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(frame, text=label, bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny'], width=6, anchor="w").pack(side=tk.LEFT)
        canvas = tk.Canvas(frame, bg=COLORS['dark_green'], height=6, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        canvas.bind("<Configure>", lambda e, c=canvas, v=value, col=color: self.draw_bar(c, v, col))
        tk.Label(frame, text=f"{int(value*100)}%", bg=COLORS['terminal_bg'], fg=color, font=FONTS['tiny']).pack(side=tk.RIGHT)

    def draw_bar(self, canvas, value, color):
        canvas.delete("all")
        w, h = canvas.winfo_width(), canvas.winfo_height()
        block_w = 4
        gap = 2
        num_blocks = w // (block_w + gap)
        filled_blocks = int(num_blocks * value)
        
        for i in range(num_blocks):
            x0 = i * (block_w + gap)
            fill_col = color if i < filled_blocks else COLORS['dark_green']
            canvas.create_rectangle(x0, 0, x0 + block_w, h, fill=fill_col, outline="")

# --- MAIN APP ---
class CaprionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CAPRION / NEON PROTOCOL")
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        self.root.configure(bg=COLORS['bg'])
        self.root.overrideredirect(True)
        self.root.focus_force()
        self.root.bind("<Escape>", lambda e: self.close_app())
        self.root.bind("<space>", lambda e: self.trigger_glitches()) 

        self.audio_engine = AudioEngine()
        self.setup_layout()
        self.start_loop()

    def create_header(self, parent, title, window_id="01", chrome="─ □ ×"):
        header = tk.Frame(parent, bg=COLORS['accent'], height=22)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        
        tk.Label(header, text=f"{window_id}", bg=COLORS['accent'], fg="#17080f", font=FONTS['tiny'], padx=5).pack(side=tk.LEFT)
        tk.Label(header, text=title, bg=COLORS['accent'], fg="#17080f", font=FONTS['header']).pack(side=tk.LEFT)
        tk.Label(header, text=chrome, bg=COLORS['accent'], fg="#17080f", font=FONTS['small'], padx=10).pack(side=tk.RIGHT)

    def setup_layout(self):
        # --- TOP BAR ---
        top_bar = tk.Frame(self.root, bg=COLORS['bg'], height=25)
        top_bar.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(5,0))
        tk.Label(top_bar, text="● CAPRION_OS v.03", bg=COLORS['bg'], fg=COLORS['text'], font=FONTS['topbar']).pack(side=tk.LEFT)
        tk.Label(top_bar, text="GHOST INSIDE / SOMEONE IS HERE", bg=COLORS['bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.LEFT, expand=True)
        tk.Label(top_bar, text="LINK ESTABLISHED ▰ ▰ ▰", bg=COLORS['bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.RIGHT)

        # --- BOTTOM BAR ---
        bottom_bar = tk.Frame(self.root, bg=COLORS['bg'], height=25)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0,5))
        tk.Label(bottom_bar, text="● GHOST IN THE NETWORK", bg=COLORS['bg'], fg=COLORS['green'], font=FONTS['tiny']).pack(side=tk.LEFT)
        self.session_lbl = tk.Label(bottom_bar, text="SESSION 00:00:00", bg=COLORS['bg'], fg=COLORS['muted'], font=FONTS['tiny'])
        self.session_lbl.pack(side=tk.LEFT, expand=True)
        tk.Label(bottom_bar, text="CAPRI / ALWAYS ONLINE ⚙", bg=COLORS['bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.RIGHT)

        # --- WORKSPACE GRID (Exact fr weights from CSS) ---
        self.workspace = tk.Frame(self.root, bg=COLORS['bg'])
        self.workspace.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.workspace.columnconfigure(0, weight=33)
        self.workspace.columnconfigure(1, weight=35)
        self.workspace.columnconfigure(2, weight=32)
        self.workspace.rowconfigure(0, weight=26)
        self.workspace.rowconfigure(1, weight=48)
        self.workspace.rowconfigure(2, weight=26)

        # --- PANEL 1: LIVE FEED ---
        self.panel1 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel1.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel1, "CAPRI / LIVE FEED", "01")
        
        overlays1 = [
            {'text': 'REC  CAM_01 / ENCRYPTED', 'x': 15, 'y': 15, 'color': 'white', 'font': FONTS['small']},
            {'text': 'PROJECT / 0xC4', 'x': 20, 'y': self.root.winfo_screenheight()*0.5, 'color': COLORS['muted'], 'font': FONTS['small']},
            {'text': 'CAPRION_', 'x': 20, 'y': self.root.winfo_screenheight()*0.53, 'color': 'white', 'font': FONTS['title_big']},
            {'text': 'NO GODS. NO MASTERS. JUST SIGNAL.', 'x': 20, 'y': self.root.winfo_screenheight()*0.58, 'color': COLORS['text'], 'font': FONTS['small']},
            {'text': 'SUBJECT: CAPRI', 'x': 20, 'y': self.root.winfo_screenheight()*0.62, 'color': COLORS['muted'], 'font': FONTS['tiny']},
        ]
        self.img_panel = GlitchImagePanel(
            self.panel1, 
            primary_image="assets/portrait-grin.png", 
            glitch_images=["assets/portrait-night.png", "assets/face-main.png", "assets/portrait-smile.png"],
            text_overlays=overlays1
        )
        self.img_panel.pack(fill=tk.BOTH, expand=True)

        # --- PANEL 2: AUDIO ---
        self.panel2 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel2.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel2, "SIGNAL / AUDIO", "02")
        
        self.audio_body = tk.Frame(self.panel2, bg=COLORS['terminal_bg'])
        self.audio_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.audio_top = tk.Frame(self.audio_body, bg=COLORS['terminal_bg'])
        self.audio_top.pack(fill=tk.X, padx=10, pady=10)
        
        self.mask_canvas = CapriMask(self.audio_top, width=90, height=60)
        self.mask_canvas.pack(side=tk.LEFT, padx=5)
        
        info_frame = tk.Frame(self.audio_top, bg=COLORS['terminal_bg'])
        info_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(info_frame, text="NEURAL FREQUENCY", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(anchor="w")
        tk.Label(info_frame, text="WAITING FOR SIGNAL", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['header']).pack(anchor="w")
        tk.Label(info_frame, text="SYSTEM AUDIO / STANDBY", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['tiny']).pack(anchor="w")
        
        self.audio_canvas = AudioSpectrum(self.audio_body, self.audio_engine, height=60)
        self.audio_canvas.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))

        # --- PANEL 3: CLOCK ---
        self.panel3 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel3.grid(row=0, column=2, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel3, "LOCAL TIME", "03")
        
        self.clock_body = tk.Frame(self.panel3, bg=COLORS['terminal_bg'])
        self.clock_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        time_frame = tk.Frame(self.clock_body, bg=COLORS['terminal_bg'])
        time_frame.pack(pady=(10, 0))
        self.time_lbl = tk.Label(time_frame, text="00:00", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['clock_big'])
        self.time_lbl.pack(side=tk.LEFT)
        self.sec_lbl = tk.Label(time_frame, text="00", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['clock_sec'])
        self.sec_lbl.pack(side=tk.LEFT, anchor="s", pady=(0, 10))

        date_frame = tk.Frame(self.clock_body, bg=COLORS['terminal_bg'])
        date_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.date_lbl = tk.Label(date_frame, text="", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['small'])
        self.date_lbl.pack(side=tk.LEFT)
        self.day_lbl = tk.Label(date_frame, text="", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['small'])
        self.day_lbl.pack(side=tk.RIGHT)

        self.calendar = CalendarWidget(self.clock_body)
        self.calendar.pack(pady=5)

        # --- PANEL 4: TERMINAL ---
        self.panel4 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel4.grid(row=1, column=1, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel4, "ROOT@CAPRION : ~/NEURAL_LINK", "04")
        
        term_meta_top = tk.Frame(self.panel4, bg=COLORS['terminal_bg'], height=20)
        term_meta_top.pack(fill=tk.X, padx=1)
        tk.Label(term_meta_top, text="■ PROTOCOL ACTIVE", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['tiny']).pack(side=tk.LEFT, padx=5)
        tk.Label(term_meta_top, text="UTF-8 / AES-256", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.RIGHT, padx=5)

        self.terminal = TerminalWidget(self.panel4)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=1)

        term_meta_bot = tk.Frame(self.panel4, bg=COLORS['terminal_bg'], height=20)
        term_meta_bot.pack(fill=tk.X, padx=1)
        tk.Label(term_meta_bot, text="PACKETS 013483", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(side=tk.LEFT, padx=5)
        tk.Label(term_meta_bot, text="CONNECTION SECURE ■", bg=COLORS['terminal_bg'], fg=COLORS['green'], font=FONTS['tiny']).pack(side=tk.RIGHT, padx=5)

        # --- PANEL 5: AFTERIMAGE ---
        self.panel5 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel5.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel5, "AFTERIMAGE / MEMORY", "05")
        
        overlays5 = [
            {'text': 'STILL HERE.', 'x': 20, 'y': self.root.winfo_screenheight()*0.8, 'color': 'white', 'font': FONTS['title_big']},
            {'text': "YOU CAN'T DELETE A GHOST.", 'x': 20, 'y': self.root.winfo_screenheight()*0.85, 'color': COLORS['green'], 'font': FONTS['small']},
            {'text': 'MEMORY BANK / 02', 'x': self.root.winfo_screenwidth()*0.25, 'y': 15, 'color': 'white', 'font': FONTS['small'], 'anchor': 'ne'}
        ]
        self.img_panel2 = GlitchImagePanel(
            self.panel5, 
            primary_image="assets/portrait-night.png", 
            glitch_images=["assets/portrait-grin.png", "assets/face-main.png", "assets/portrait-green.png"],
            text_overlays=overlays5
        )
        self.img_panel2.pack(fill=tk.BOTH, expand=True)

        # --- PANEL 6: DIAGNOSTICS ---
        self.panel6 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel6.grid(row=2, column=0, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel6, "NEURAL DIAGNOSTICS", "06")
        
        diag_body = tk.Frame(self.panel6, bg=COLORS['terminal_bg'])
        diag_body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.diag = DiagnosticsWidget(diag_body)
        self.diag.pack(fill=tk.BOTH, expand=True)

        # --- PANEL 7: WORLD CLOCK ---
        self.panel7 = tk.Frame(self.workspace, bg=COLORS['bg'], highlightbackground=COLORS['border'], highlightthickness=1)
        self.panel7.grid(row=2, column=1, sticky="nsew", padx=3, pady=3)
        self.create_header(self.panel7, "WORLD CLOCK / UPLINK", "07")
        
        self.world_frame = tk.Frame(self.panel7, bg=COLORS['terminal_bg'])
        self.world_frame.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)
        
        w_inner = tk.Frame(self.world_frame, bg=COLORS['terminal_bg'])
        w_inner.pack(expand=True, fill=tk.BOTH, padx=15, pady=10)
        
        tk.Label(w_inner, text="HOME LOCAL", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(anchor="w")
        self.home_time_lbl = tk.Label(w_inner, text="00:00:00", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['world_clock'])
        self.home_time_lbl.pack(anchor="w", pady=(0, 5))
        
        tk.Label(w_inner, text="TOKYO JST +09", bg=COLORS['terminal_bg'], fg=COLORS['muted'], font=FONTS['tiny']).pack(anchor="w")
        self.tokyo_time_lbl = tk.Label(w_inner, text="00:00:00", bg=COLORS['terminal_bg'], fg=COLORS['text'], font=FONTS['world_clock'])
        self.tokyo_time_lbl.pack(anchor="w")

        # --- FLOATING CACHED MEMORY WINDOW (Exact CSS Placement) ---
        # left:35%; top:47%; width:300px; height:261px;
        # Border is green.
        self.floating_win = tk.Frame(self.root, bg=COLORS['green'], highlightbackground=COLORS['green'], highlightthickness=1)
        self.floating_win.place(relx=0.35, rely=0.47, anchor="nw", width=300, height=261)
        
        f_header = tk.Frame(self.floating_win, bg=COLORS['green'], height=22)
        f_header.pack(fill=tk.X)
        f_header.pack_propagate(False)
        tk.Label(f_header, text="♡ / CACHED MEMORY", bg=COLORS['green'], fg="#17080f", font=FONTS['tiny'], padx=5).pack(side=tk.LEFT)
        tk.Label(f_header, text="×", bg=COLORS['green'], fg="#17080f", font=FONTS['tiny'], padx=5).pack(side=tk.RIGHT)
        
        self.float_img = GlitchImagePanel(
            self.floating_win, 
            primary_image="assets/face-main.png", 
            glitch_images=["assets/portrait-grin.png"], 
            text_overlays=[{'text': 'do you remember me?', 'x': 150, 'y': 235, 'color': 'white', 'anchor': 'center', 'font': FONTS['small']}]
        )
        self.float_img.pack(fill=tk.BOTH, expand=True)

    def trigger_glitches(self):
        if hasattr(self, 'img_panel'): self.img_panel.trigger_glitch()
        if hasattr(self, 'img_panel2'): self.img_panel2.trigger_glitch()
        if hasattr(self, 'float_img'): self.float_img.trigger_glitch()

    def close_app(self):
        self.audio_engine.stop()
        self.root.destroy()

    def update_clocks(self):
        now = datetime.datetime.now()
        self.time_lbl.config(text=now.strftime("%H:%M"))
        self.sec_lbl.config(text=now.strftime("%S"))
        self.date_lbl.config(text=now.strftime("%d %B %Y").upper())
        self.day_lbl.config(text=now.strftime("%a").upper())
        
        self.home_time_lbl.config(text=now.strftime("%H:%M:%S"))
        tokyo = now + datetime.timedelta(hours=9 - int(-time.timezone/3600))
        self.tokyo_time_lbl.config(text=tokyo.strftime("%H:%M:%S"))

    def start_loop(self):
        self.audio_canvas.update_spectrum()
        self.terminal.update_scroll()
        self.update_clocks()
        
        mouse_x = self.root.winfo_pointerx()
        mouse_y = self.root.winfo_pointery()
        if hasattr(self, 'mask_canvas'):
            self.mask_canvas.update_gaze(mouse_x, mouse_y)
            if random.random() < 0.005:
                self.mask_canvas.toggle_blink()

        if random.random() < 0.002:
            self.trigger_glitches()
            
        if hasattr(self, 'terminal') and not self.terminal.takeover and random.random() < 0.001:
            self.terminal.trigger_takeover()
            self.trigger_glitches()

        self.root.after(16, self.start_loop)

# --- SUPPORT CLASSES ---
class AudioSpectrum(tk.Canvas):
    def __init__(self, parent, audio_engine, **kwargs):
        super().__init__(parent, bg=COLORS['terminal_bg'], highlightthickness=0, **kwargs)
        self.audio = audio_engine
        self.bars = []
        self.bind("<Configure>", self.setup_bars)
    def setup_bars(self, event=None):
        self.delete("all")
        self.bars = []
        w, h = self.winfo_width(), self.winfo_height()
        num_bars = 64
        gap = 1
        bar_width = max(1, (w / num_bars) - gap)
        for i in range(num_bars):
            x0 = i * (bar_width + gap)
            color = COLORS['accent'] if i < 40 else COLORS['green']
            self.bars.append(self.create_rectangle(x0, h, x0 + bar_width, h, fill=color, outline=""))
    def update_spectrum(self):
        w, h = self.winfo_width(), self.winfo_height()
        for i, rect in enumerate(self.bars):
            if i >= len(self.audio.levels): break
            bar_height = max(2, self.audio.levels[i] * h * 1.5) 
            coords = self.coords(rect)
            if coords:
                self.coords(rect, coords[0], h - bar_height, coords[2], h)

if __name__ == "__main__":
    root = tk.Tk()
    app = CaprionApp(root)
    root.mainloop()