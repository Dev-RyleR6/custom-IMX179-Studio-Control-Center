import cv2
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import datetime
import os
import threading
import time

class CandlingDataCollector:
    def __init__(self, root):
        self.root = root
        self.root.title("🥚 Duck Egg Candling Dataset Collector")
        self.root.geometry("1450x950")
        self.root.configure(bg="#1e272e")

        # Dataset storage configuration
        self.output_dir = "candling_dataset"
        os.makedirs(self.output_dir, exist_ok=True)

        # Dataset Variables
        self.class_label = tk.StringVar(value="fertile")
        self.batch_id = tk.StringVar(value="batch_01")
        self.counter = 0

        # Resolution Tracker
        self.res_var = tk.StringVar(value="1920x1080")

        # Hardware Auto/Manual Toggle States
        self.auto_focus_var = tk.BooleanVar(value=False)
        self.auto_exp_var = tk.BooleanVar(value=False)
        self.auto_wb_var = tk.BooleanVar(value=False)
        self.all_auto_var = tk.BooleanVar(value=False)

        self.slider_vars = {}
        self.cap = None
        
        # Thread control flags and locks
        self.running = True
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.props_lock = threading.Lock()
        self.pending_props = {}
        
        # Initialize camera stream
        self.init_camera()
        self.setup_ui()

        # Background framing loop
        self.video_thread = threading.Thread(target=self.bg_video_loop, daemon=True)
        self.video_thread.start()

        self.update_preview()

    def init_camera(self):
        if self.cap is not None:
            self.cap.release()
            time.sleep(0.1)

        self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        
        try:
            w_str, h_str = self.res_var.get().split('x')
            width, height = int(w_str), int(h_str)
        except ValueError:
            width, height = 1920, 1080

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        if not self.cap.isOpened():
            messagebox.showerror("Hardware Error", f"Could not connect to camera index 1 at {width}x{height}.")
            return False

        self.apply_all_manual_states()
        return True

    def on_resolution_change(self, event=None):
        with self.frame_lock:
            self.latest_frame = None
        success = self.init_camera()
        if success:
            for prop_id, (var_obj, _) in self.slider_vars.items():
                self.queue_property(prop_id, var_obj.get())

    def setup_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        main_container = tk.Frame(self.root, bg="#1e272e")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        # --- VIDEO PREVIEW WINDOW ---
        self.preview_frame = tk.Frame(main_container, bg="black", bd=2, relief=tk.RIDGE)
        self.preview_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        
        self.video_label = tk.Label(self.preview_frame, bg="black")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        self.flash_banner = tk.Label(self.preview_frame, text="✔ IMAGE SAVED TO DATASET", font=("Arial", 14, "bold"), 
                                     bg="#2ed573", fg="white", pady=12)

        # --- SCROLLABLE CONTROL SIDEBAR CONTAINER ---
        sidebar_outer = tk.Frame(main_container, width=440, bg="#f5f6fa")
        sidebar_outer.grid(row=0, column=1, sticky="ns")
        sidebar_outer.pack_propagate(False)

        canvas = tk.Canvas(sidebar_outer, bg="#f5f6fa", highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_outer, orient="vertical", command=canvas.yview)
        
        self.sidebar = tk.Frame(canvas, bg="#f5f6fa", padx=15, pady=15)
        self.sidebar.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas_window = canvas.create_window((0, 0), window=self.sidebar, anchor="nw")
        
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
            
        canvas.bind('<Configure>', _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        sidebar_outer.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # --- MODULE 1: HARDWARE MANAGEMENT ---
        hw_frame = tk.LabelFrame(self.sidebar, text=" 1. Hardware Initialization ", font=("Arial", 10, "bold"), bg="#f5f6fa", fg="#2f3640", padx=10, pady=10)
        hw_frame.pack(fill=tk.X, pady=(0, 10))

        self.reset_btn = tk.Button(
            hw_frame, text="🔄 Reset to Manual Defaults", font=("Arial", 9, "bold"),
            bg="#718093", fg="white", activebackground="#a4b0be", activeforeground="white",
            command=self.reset_to_defaults, cursor="hand2", relief=tk.FLAT, height=1, pady=4
        )
        self.reset_btn.pack(fill=tk.X, pady=(0, 8))

        tk.Label(hw_frame, text="Active Video Sensor Resolution:", bg="#f5f6fa", font=("Arial", 9)).pack(anchor="w")
        res_options = ["1920x1080", "1280x720", "640x480"]
        self.res_dropdown = ttk.Combobox(hw_frame, textvariable=self.res_var, values=res_options, state="readonly")
        self.res_dropdown.pack(fill=tk.X, pady=(2, 8))
        self.res_dropdown.bind("<<ComboboxSelected>>", self.on_resolution_change)

        self.settings_btn = tk.Button(
            hw_frame, text="⚙️ Open Driver Dialog Panel", font=("Arial", 9),
            bg="#e67e22", fg="white", command=self.open_camera_settings, cursor="hand2", relief=tk.FLAT, pady=2
        )
        self.settings_btn.pack(fill=tk.X)

        # --- MODULE 2: AUTOMATION MODES ---
        auto_frame = tk.LabelFrame(self.sidebar, text=" 2. Automation Loops ", font=("Arial", 10, "bold"), bg="#f5f6fa", fg="#2f3640", padx=10, pady=10)
        auto_frame.pack(fill=tk.X, pady=(0, 10))

        self.all_auto_check = tk.Checkbutton(auto_frame, text="🤖 AUTOMATE EVERYTHING (ALL AUTO)", variable=self.all_auto_var, 
                                             bg="#dcdde1", font=("Arial", 9, "bold"), fg="#2c3e50", selectcolor="white",
                                             command=self.toggle_all_auto_modes, anchor="w")
        self.all_auto_check.pack(fill=tk.X, pady=(0, 8), ipady=3)

        for text, var in [("Auto Focus Loop", self.auto_focus_var), ("Auto Exposure Control", self.auto_exp_var), ("Auto White Balance Loop", self.auto_wb_var)]:
            tk.Checkbutton(auto_frame, text=text, variable=var, bg="#f5f6fa", font=("Arial", 9), command=self.on_individual_auto_toggle, anchor="w").pack(fill=tk.X, pady=2)

        # --- MODULE 3: MANUAL TUNING SLIDERS ---
        sliders_parent = tk.LabelFrame(self.sidebar, text=" 3. Manual Device Controls ", font=("Arial", 10, "bold"), bg="#f5f6fa", fg="#2f3640", padx=10, pady=10)
        sliders_parent.pack(fill=tk.X, pady=(0, 10))

        tk.Label(sliders_parent, text="🔬 Optics Focus (0 - 1023):", bg="#f5f6fa", font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.focus_var = tk.IntVar(value=120)
        self.slider_vars[cv2.CAP_PROP_FOCUS] = (self.focus_var, 120)
        
        focus_box = tk.Frame(sliders_parent, bg="#f5f6fa")
        focus_box.pack(fill=tk.X, pady=(0, 6))
        tk.Button(focus_box, text="◀", width=3, font=("Arial", 8), command=lambda: self.step_value(self.focus_var, -5, cv2.CAP_PROP_FOCUS)).pack(side=tk.LEFT)
        self.focus_scale = ttk.Scale(focus_box, from_=0, to=1023, variable=self.focus_var, orient=tk.HORIZONTAL, command=self.on_focus_slider)
        self.focus_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Button(focus_box, text="▶", width=3, font=("Arial", 8), command=lambda: self.step_value(self.focus_var, 5, cv2.CAP_PROP_FOCUS)).pack(side=tk.LEFT)
        tk.Label(sliders_parent, textvariable=self.focus_var, bg="#f5f6fa", font=("Arial", 8, "italic"), fg="#718093").pack(anchor="e")

        self.create_hardware_slider(sliders_parent, "Color Temperature (WB)", cv2.CAP_PROP_WB_TEMPERATURE, 2800, 6500, 4600, is_wb=True)
        self.create_hardware_slider(sliders_parent, "Shutter Speed (Exposure)", cv2.CAP_PROP_EXPOSURE, -13, 0, -6, is_exp=True)
        self.create_hardware_slider(sliders_parent, "Digital Brightness Offset", cv2.CAP_PROP_BRIGHTNESS, 0, 255, 128)
        self.create_hardware_slider(sliders_parent, "Contrast Enhancement", cv2.CAP_PROP_CONTRAST, 0, 255, 32)
        self.create_hardware_slider(sliders_parent, "Sensor Gain Boost", cv2.CAP_PROP_GAIN, 0, 255, 0)
        self.create_hardware_slider(sliders_parent, "Edge Sharpness Filter", cv2.CAP_PROP_SHARPNESS, 0, 255, 128)

        # --- MODULE 4: METADATA & DATASETS ---
        meta_frame = tk.LabelFrame(self.sidebar, text=" 4. Annotation & Metadata ", font=("Arial", 10, "bold"), bg="#f5f6fa", fg="#2f3640", padx=10, pady=10)
        meta_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(meta_frame, text="Active Batch ID:", bg="#f5f6fa", font=("Arial", 9)).pack(anchor="w")
        tk.Entry(meta_frame, textvariable=self.batch_id, font=("Arial", 10), bd=1, relief=tk.SOLID).pack(fill=tk.X, pady=(2, 8), ipady=3)

        classes = [
            ("🟢 Fertile Embryo (Developing)", "fertile"), 
            ("⚪ Infertile Structure (Clear)", "infertile"), 
            ("🔴 Abnormal Specimen (Blood Ring)", "abnormal")
        ]
        for text, val in classes:
            tk.Radiobutton(meta_frame, text=text, variable=self.class_label, value=val, bg="#f5f6fa", font=("Arial", 9)).pack(anchor="w", pady=2)

        # --- MODULE 5: PRODUCTION RUN CAPTURE BUTTON ---
        self.snap_btn = tk.Button(
            self.sidebar, text="📸 CAPTURE SAMPLE TO DATASET\n[ Spacebar Key ]", font=("Arial", 11, "bold"),
            bg="#2cf43b", fg="#1e272e", activebackground="#219653", activeforeground="white",
            command=self.save_image, height=2, cursor="hand2", relief=tk.FLAT
        )
        self.snap_btn.pack(fill=tk.X, pady=(5, 2))
        self.root.bind("<space>", lambda event: self.save_image()) 

        self.stats_lbl = tk.Label(self.sidebar, text="Current Session Frame Count: 0", font=("Arial", 9, "italic"), bg="#f5f6fa", fg="#7f8c8d")
        self.stats_lbl.pack(pady=2)

    def toggle_all_auto_modes(self):
        state = self.all_auto_var.get()
        self.auto_focus_var.set(state)
        self.auto_exp_var.set(state)
        self.auto_wb_var.set(state)
        val = 1 if state else 0
        self.queue_property(cv2.CAP_PROP_AUTOFOCUS, val)
        self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, val)
        self.queue_property(cv2.CAP_PROP_AUTO_WB, val)

    def on_individual_auto_toggle(self):
        self.queue_property(cv2.CAP_PROP_AUTOFOCUS, 1 if self.auto_focus_var.get() else 0)
        self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if self.auto_exp_var.get() else 0)
        self.queue_property(cv2.CAP_PROP_AUTO_WB, 1 if self.auto_wb_var.get() else 0)
        self.all_auto_var.set(self.auto_focus_var.get() and self.auto_exp_var.get() and self.auto_wb_var.get())

    def reset_to_defaults(self):
        self.all_auto_var.set(False)
        self.auto_focus_var.set(False)
        self.auto_exp_var.set(False)
        self.auto_wb_var.set(False)
        self.apply_all_manual_states()
        for prop_id, (var_obj, default_val) in self.slider_vars.items():
            var_obj.set(default_val)

    def apply_all_manual_states(self):
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            self.cap.set(cv2.CAP_PROP_FOCUS, 120)
            self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, 4600)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
            self.cap.set(cv2.CAP_PROP_CONTRAST, 32)
            self.cap.set(cv2.CAP_PROP_GAIN, 0)
            self.cap.set(cv2.CAP_PROP_SHARPNESS, 128)

    def on_focus_slider(self, val):
        self.break_focus_loop()
        self.queue_property(cv2.CAP_PROP_FOCUS, int(float(val)))

    def on_exp_slider(self, val):
        self.break_general_loops(break_exp=True)
        self.queue_property(cv2.CAP_PROP_EXPOSURE, int(float(val)))

    def on_wb_slider(self, val):
        self.break_general_loops(break_wb=True)
        self.queue_property(cv2.CAP_PROP_WB_TEMPERATURE, int(float(val)))

    def break_focus_loop(self):
        """Only shuts down auto-focus loops; preserves active auto exposure & auto white balance."""
        if self.auto_focus_var.get():
            self.auto_focus_var.set(False)
            self.all_auto_var.set(False)
            self.queue_property(cv2.CAP_PROP_AUTOFOCUS, 0)

    def break_general_loops(self, break_exp=False, break_wb=False):
        """Standard slider interaction safety drops for Exposure/WB loops."""
        self.all_auto_var.set(False)
        if break_exp and self.auto_exp_var.get():
            self.auto_exp_var.set(False)
            self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
        if break_wb and self.auto_wb_var.get():
            self.auto_wb_var.set(False)
            self.queue_property(cv2.CAP_PROP_AUTO_WB, 0)

    def create_hardware_slider(self, parent, label_text, prop_id, from_val, to_val, default_val, is_exp=False, is_wb=False):
        tk.Label(parent, text=f"{label_text}:", bg="#f5f6fa", font=("Arial", 9)).pack(anchor="w", pady=(3, 0))
        var = tk.IntVar(value=default_val)
        self.slider_vars[prop_id] = (var, default_val)
        
        if is_exp:
            cmd = lambda v: self.on_exp_slider(v)
        elif is_wb:
            cmd = lambda v: self.on_wb_slider(v)
        else:
            # Brightness, Contrast, Gain, and Sharpness fall under basic image registers
            cmd = lambda v, p=prop_id: [self.break_general_loops(break_exp=True, break_wb=True), self.queue_property(p, int(float(v)))]
            
        scale = ttk.Scale(parent, from_=from_val, to=to_val, variable=var, orient=tk.HORIZONTAL, command=cmd)
        scale.pack(fill=tk.X, pady=(0, 2))

    def step_value(self, var_obj, amount, prop_id):
        if prop_id == cv2.CAP_PROP_FOCUS:
            self.break_focus_loop()
        elif prop_id == cv2.CAP_PROP_EXPOSURE:
            self.break_general_loops(break_exp=True)
        elif prop_id == cv2.CAP_PROP_WB_TEMPERATURE:
            self.break_general_loops(break_wb=True)
        else:
            self.break_general_loops(break_exp=True, break_wb=True)

        new_val = max(0, min(1023, var_obj.get() + amount))
        var_obj.set(new_val)
        self.queue_property(prop_id, new_val)

    def open_camera_settings(self):
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_SETTINGS, 1)

    def queue_property(self, prop_id, value):
        with self.props_lock:
            self.pending_props[prop_id] = value

    def bg_video_loop(self):
        while self.running:
            with self.props_lock:
                if self.pending_props and self.cap and self.cap.isOpened():
                    for prop_id, val in list(self.pending_props.items()):
                        self.cap.set(prop_id, val)
                    self.pending_props.clear()

            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.latest_frame = frame
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.05)

    def update_preview(self):
        with self.frame_lock:
            frame = self.latest_frame.copy() if self.latest_frame is not None else None

        if frame is not None:
            win_w = max(self.preview_frame.winfo_width(), 10)
            win_h = max(self.preview_frame.winfo_height(), 10)
            
            h, w = frame.shape[:2]
            scale = min(win_w / w, win_h / h)
            
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            if new_w > 10 and new_h > 10:
                frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

        if self.running:
            self.root.after(16, self.update_preview)

    def save_image(self):
        with self.frame_lock:
            frame_to_save = self.latest_frame.copy() if self.latest_frame is not None else None

        if frame_to_save is not None:
            target_class = self.class_label.get()
            class_folder = os.path.join(self.output_dir, target_class)
            os.makedirs(class_folder, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            batch = self.batch_id.get().strip().replace(" ", "_")
            filename = f"Egg_{batch}_{timestamp}_{self.counter:04d}.jpg"
            full_path = os.path.join(class_folder, filename)

            threading.Thread(target=self._async_write_disk, args=(full_path, frame_to_save), daemon=True).start()
            
            self.counter += 1
            self.stats_lbl.config(text=f"Current Session Frame Count: {self.counter}")

            self.flash_banner.grid(row=0, column=0, sticky="s", padx=10, pady=25)
            self.snap_btn.config(bg="#2ed573", fg="white", text="✔ SAMPLE RECORDED SUCCESSFULLY")
            
            self.root.after(300, self._clear_visual_flash)

    def _async_write_disk(self, path, frame):
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

    def _clear_visual_flash(self):
        self.flash_banner.grid_forget()
        self.snap_btn.config(bg="#2cf43b", fg="#1e272e", text="📸 CAPTURE SAMPLE TO DATASET\n[ Spacebar Key ]")

    def close(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CandlingDataCollector(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()