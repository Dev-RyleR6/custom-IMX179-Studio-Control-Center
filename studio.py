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
        self.root.geometry("1300x900")
        self.root.configure(bg="#2c3e50")

        # Dataset storage configuration
        self.output_dir = "candling_dataset"
        os.makedirs(self.output_dir, exist_ok=True)

        # Dataset Variables
        self.class_label = tk.StringVar(value="fertile")
        self.batch_id = tk.StringVar(value="batch_01")
        self.counter = 0

        # Hardware Auto/Manual Toggle States
        self.auto_focus_var = tk.BooleanVar(value=False)
        self.auto_exp_var = tk.BooleanVar(value=False)
        self.auto_wb_var = tk.BooleanVar(value=False)
        self.all_auto_var = tk.BooleanVar(value=False)

        # Dictionary to track slider variables for quick resets
        self.slider_vars = {}

        # Initialize Camera via DirectShow
        self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        if not self.cap.isOpened():
            messagebox.showerror("Hardware Error", "Could not connect to camera index 1.")
            self.root.destroy()
            return

        # Initialize with baseline manual states
        self.apply_all_manual_states()

        self.setup_ui()

        # Background stream thread variables
        self.running = True
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        self.pending_props = {}
        self.props_lock = threading.Lock()

        self.video_thread = threading.Thread(target=self.bg_video_loop, daemon=True)
        self.video_thread.start()

        self.update_preview()

    def setup_ui(self):
        # Configure layout weights on root for window resizing responsiveness
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        main_container = tk.Frame(self.root, bg="#2c3e50")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        # --- VIDEO PREVIEW WINDOW ---
        self.preview_frame = tk.Frame(main_container, bg="black", bd=2, relief=tk.RIDGE)
        self.preview_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        self.video_label = tk.Label(self.preview_frame, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # --- FIXED CONTROL SIDEBAR ---
        self.sidebar = tk.Frame(main_container, width=380, bg="#ecf0f1", padx=15, pady=10)
        self.sidebar.grid(row=0, column=1, sticky="ns")
        self.sidebar.pack_propagate(False) 

        # --- HARDWARE UTILITIES ---
        tk.Label(self.sidebar, text="1. HARDWARE SYSTEM CONTROL", font=("Arial", 10, "bold"), bg="#ecf0f1", fg="#2c3e50").pack(anchor="w", pady=(0, 2))
        
        self.reset_btn = tk.Button(
            self.sidebar, text="🔄 RESET TO DEFAULT SETTINGS", font=("Arial", 10, "bold"),
            bg="#7f8c8d", fg="white", activebackground="#95a5a6", activeforeground="white",
            command=self.reset_to_defaults, cursor="hand2", relief=tk.FLAT, height=2
        )
        self.reset_btn.pack(fill=tk.X, pady=(0, 8))

        self.settings_btn = tk.Button(
            self.sidebar, text="⚙️ Open Driver Dialog Panel", font=("Arial", 9),
            bg="#e67e22", fg="white", command=self.open_camera_settings, cursor="hand2", relief=tk.FLAT, height=1
        )
        self.settings_btn.pack(fill=tk.X, pady=(0, 10))

        # --- AUTOMATIC HARDWARE TOGGLES ---
        tk.Label(self.sidebar, text="HARDWARE MODE SWITCHES", font=("Arial", 9, "bold"), bg="#ecf0f1", fg="#7f8c8d").pack(anchor="w", pady=(5, 2))
        
        toggle_frame = tk.Frame(self.sidebar, bg="#ecf0f1")
        toggle_frame.pack(fill=tk.X, pady=(0, 5))

        # Master Global Automation Toggle Button
        self.all_auto_check = tk.Checkbutton(toggle_frame, text="🤖 AUTOMATE EVERYTHING (ALL AUTO)", variable=self.all_auto_var, 
                                             bg="#dcdde1", font=("Arial", 9, "bold"), fg="#2c3e50", selectcolor="white",
                                             command=self.toggle_all_auto_modes)
        self.all_auto_check.pack(anchor="w", fill=tk.X, pady=(0, 5), ipady=2)

        tk.Checkbutton(toggle_frame, text="Auto Focus", variable=self.auto_focus_var, bg="#ecf0f1", font=("Arial", 9),
                       command=self.on_individual_auto_toggle).pack(anchor="w")
        
        tk.Checkbutton(toggle_frame, text="Auto Exposure", variable=self.auto_exp_var, bg="#ecf0f1", font=("Arial", 9),
                       command=self.on_individual_auto_toggle).pack(anchor="w")

        tk.Checkbutton(toggle_frame, text="Auto White Balance", variable=self.auto_wb_var, bg="#ecf0f1", font=("Arial", 9),
                       command=self.on_individual_auto_toggle).pack(anchor="w")

        # --- MANUAL SLIDERS ---
        tk.Label(self.sidebar, text="MANUAL TUNING SLIDERS", font=("Arial", 9, "bold"), bg="#ecf0f1", fg="#7f8c8d").pack(anchor="w", pady=(5, 2))

        # Core Focus
        tk.Label(self.sidebar, text="🔬 Manual Focus Control (0 - 1023):", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(anchor="w")
        self.focus_var = tk.IntVar(value=120)
        self.slider_vars[cv2.CAP_PROP_FOCUS] = (self.focus_var, 120)
        
        focus_box = tk.Frame(self.sidebar, bg="#ecf0f1")
        focus_box.pack(fill=tk.X, pady=(0, 2))
        tk.Button(focus_box, text="◀", width=3, command=lambda: self.step_value(self.focus_var, -5, cv2.CAP_PROP_FOCUS)).pack(side=tk.LEFT)
        self.focus_scale = ttk.Scale(focus_box, from_=0, to=1023, variable=self.focus_var, orient=tk.HORIZONTAL, command=self.on_focus_slider)
        self.focus_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(focus_box, text="▶", width=3, command=lambda: self.step_value(self.focus_var, 5, cv2.CAP_PROP_FOCUS)).pack(side=tk.LEFT)
        tk.Label(self.sidebar, textvariable=self.focus_var, bg="#ecf0f1", font=("Arial", 9, "italic")).pack(anchor="e")

        # Image Registers
        self.create_hardware_slider("White Balance Color Temp", cv2.CAP_PROP_WB_TEMPERATURE, 2800, 6500, 4600, is_wb=True)
        self.create_hardware_slider("Exposure (Shutter)", cv2.CAP_PROP_EXPOSURE, -13, 0, -6, is_exp=True)
        self.create_hardware_slider("Brightness", cv2.CAP_PROP_BRIGHTNESS, 0, 255, 128)
        self.create_hardware_slider("Contrast", cv2.CAP_PROP_CONTRAST, 0, 255, 32)
        self.create_hardware_slider("Gain (Sensor Boost)", cv2.CAP_PROP_GAIN, 0, 255, 0)
        self.create_hardware_slider("Sharpness (Edges)", cv2.CAP_PROP_SHARPNESS, 0, 255, 128)

        # --- DATASET LABEL MANAGEMENT ---
        tk.Label(self.sidebar, text="2. DATASET METADATA", font=("Arial", 10, "bold"), bg="#ecf0f1", fg="#2c3e50").pack(anchor="w", pady=(10, 2))
        
        tk.Label(self.sidebar, text="Batch Identifier:", bg="#ecf0f1", font=("Arial", 9)).pack(anchor="w")
        tk.Entry(self.sidebar, textvariable=self.batch_id, font=("Arial", 10)).pack(fill=tk.X, pady=(0, 4))

        classes = [
            ("🟢 Fertile (Developing Embryo)", "fertile"), 
            ("⚪ Infertile (Clear / Unbred)", "infertile"), 
            ("🔴 Abnormal (Early Die-off / Blood Ring)", "abnormal")
        ]
        for text, val in classes:
            tk.Radiobutton(self.sidebar, text=text, variable=self.class_label, value=val, bg="#ecf0f1", font=("Arial", 10)).pack(anchor="w", pady=1)

        # --- CAPTURE HUB ---
        tk.Label(self.sidebar, text="3. COLLECT DATA", font=("Arial", 10, "bold"), bg="#ecf0f1", fg="#2c3e50").pack(anchor="w", pady=(5, 2))
        self.snap_btn = tk.Button(
            self.sidebar, text="📸 CAPTURE IMAGE\n(Spacebar)", font=("Arial", 13, "bold"),
            bg="#27ae60", fg="white", activebackground="#219653", activeforeground="white",
            command=self.save_image, height=2, cursor="hand2", relief=tk.FLAT
        )
        self.snap_btn.pack(fill=tk.X, pady=2)
        self.root.bind("<space>", lambda event: self.save_image()) 

        self.stats_lbl = tk.Label(self.sidebar, text="Captured this session: 0", font=("Arial", 10, "italic"), bg="#ecf0f1", fg="#7f8c8d")
        self.stats_lbl.pack(pady=2)

    def toggle_all_auto_modes(self):
        """Forces all auto features on or off simultaneously based on master toggle."""
        state = self.all_auto_var.get()
        self.auto_focus_var.set(state)
        self.auto_exp_var.set(state)
        self.auto_wb_var.set(state)

        val = 1 if state else 0
        self.queue_property(cv2.CAP_PROP_AUTOFOCUS, val)
        self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, val)
        self.queue_property(cv2.CAP_PROP_AUTO_WB, val)

    def on_individual_auto_toggle(self):
        """Turn off master automate check if individual toggles are broken up manually."""
        self.queue_property(cv2.CAP_PROP_AUTOFOCUS, 1 if self.auto_focus_var.get() else 0)
        self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, 1 if self.auto_exp_var.get() else 0)
        self.queue_property(cv2.CAP_PROP_AUTO_WB, 1 if self.auto_wb_var.get() else 0)
        
        # If any singular item is unchecked, master auto state isn't true anymore
        if not (self.auto_focus_var.get() and self.auto_exp_var.get() and self.auto_wb_var.get()):
            self.all_auto_var.set(False)
        else:
            self.all_auto_var.set(True)

    def reset_to_defaults(self):
        """Resets sliders to standard factory numbers and disables all auto functions."""
        self.all_auto_var.set(False)
        self.auto_focus_var.set(False)
        self.auto_exp_var.set(False)
        self.auto_wb_var.set(False)

        self.apply_all_manual_states()

        # Update GUI slider bars back to default locations
        for prop_id, (var_obj, default_val) in self.slider_vars.items():
            var_obj.set(default_val)

    def apply_all_manual_states(self):
        """Locks clean static values to prevent auto tracking drift."""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            
            # Send baseline values down to hardware channels
            self.cap.set(cv2.CAP_PROP_FOCUS, 120)
            self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, 4600)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
            self.cap.set(cv2.CAP_PROP_CONTRAST, 32)
            self.cap.set(cv2.CAP_PROP_GAIN, 0)
            self.cap.set(cv2.CAP_PROP_SHARPNESS, 128)

    def on_focus_slider(self, val):
        self.break_auto_loops()
        self.queue_property(cv2.CAP_PROP_FOCUS, int(float(val)))

    def on_exp_slider(self, val):
        self.break_auto_loops()
        self.queue_property(cv2.CAP_PROP_EXPOSURE, int(float(val)))

    def on_wb_slider(self, val):
        self.break_auto_loops()
        self.queue_property(cv2.CAP_PROP_WB_TEMPERATURE, int(float(val)))

    def break_auto_loops(self):
        """Drops auto toggles immediately if a user interacts with manual hardware sliders."""
        if self.all_auto_var.get() or self.auto_focus_var.get() or self.auto_exp_var.get() or self.auto_wb_var.get():
            self.all_auto_var.set(False)
            self.auto_focus_var.set(False)
            self.auto_exp_var.set(False)
            self.auto_wb_var.set(False)
            self.queue_property(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.queue_property(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.queue_property(cv2.CAP_PROP_AUTO_WB, 0)

    def create_hardware_slider(self, label_text, prop_id, from_val, to_val, default_val, is_exp=False, is_wb=False):
        tk.Label(self.sidebar, text=f"{label_text}:", bg="#ecf0f1", font=("Arial", 9)).pack(anchor="w", pady=(1, 0))
        var = tk.IntVar(value=default_val)
        self.slider_vars[prop_id] = (var, default_val)
        
        if is_exp:
            cmd = lambda v: self.on_exp_slider(v)
        elif is_wb:
            cmd = lambda v: self.on_wb_slider(v)
        else:
            cmd = lambda v, p=prop_id: [self.break_auto_loops(), self.queue_property(p, int(float(v)))]
            
        scale = ttk.Scale(self.sidebar, from_=from_val, to=to_val, variable=var, orient=tk.HORIZONTAL, command=cmd)
        scale.pack(fill=tk.X)
        tk.Label(self.sidebar, textvariable=var, bg="#ecf0f1", font=("Arial", 8, "italic")).pack(anchor="e")

    def step_value(self, var_obj, amount, prop_id):
        self.break_auto_loops()
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

            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame
            else:
                time.sleep(0.01)

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

            cv2.imwrite(full_path, frame_to_save, [cv2.IMWRITE_JPEG_QUALITY, 100])
            
            self.counter += 1
            self.stats_lbl.config(text=f"Captured this session: {self.counter}")

            self.snap_btn.config(bg="#3498db", text="✔ SAVED")
            self.root.after(180, lambda: self.snap_btn.config(bg="#27ae60", text="📸 CAPTURE IMAGE\n(Spacebar)"))

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

#refactored: Improved code structure and readability