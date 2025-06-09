# main_app.py

import tkinter as tk
from tkinter import ttk as Ttk # Standard ttk for comparison/fallback if needed
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import os

# Import all the backend modules
import config_settings
import gui_utils
import measurement_handler
import live_plot_module
import history_tab_module

class Application:
    """
    The main application class that constructs and runs the GUI.
    """
    def __init__(self, root):
        self.root = root
        self.style = ttk.Style()
        self.root.title("Semiconductor Device Measurement Suite")
        self.root.geometry("1400x850")

        # --- Variables ---
        self.output_dir = tk.StringVar(value=config_settings.DEFAULT_OUTPUT_DIR)
        self.file_name_base = tk.StringVar()
        self.device_type = tk.StringVar(value="lateral")
        self.channel_width_um = tk.StringVar(value=config_settings.DEVICE_DEFAULT_CHANNEL_WIDTH_UM)
        self.area_um2 = tk.StringVar(value=config_settings.DEVICE_DEFAULT_AREA_UM2)
        self.theme_name = tk.StringVar(value=self.style.theme.name)
        
        # Dictionaries to hold tk.StringVar for each measurement tab's parameters
        self.gt_params_vars = {}
        self.oc_params_vars = {}
        self.bd_params_vars = {}
        self.diode_params_vars = {}
        self.stress_params_vars = {}

        # Backward sweep and other checkbutton variables
        self.gt_enable_backward = tk.BooleanVar(value=False)
        self.diode_enable_backward = tk.BooleanVar(value=False)

        # Post-stress characterization method
        self.post_stress_char_method = tk.StringVar(value="栅转移特性 (Gate Transfer)")

        # --- Create GUI Structure ---
        self._create_menu()
        self._create_main_layout()
        self._create_status_bar()

        # --- Instantiate Handlers ---
        # The handlers require the GUI frames to be created first.
        self.live_plot_handler = live_plot_module.LivePlotHandler(self, self.right_pane)
        self.history_tab_handler = history_tab_module.HistoryTabHandler(self, self.history_tab_frame)
        self.measurement_handler = measurement_handler.MeasurementHandler(self, self.live_plot_handler)
        
        # --- Final UI Setup ---
        self.update_device_param_state() # Initial state update
        self.refresh_recent_files() # Initial file list load

    def _create_menu(self):
        """Creates the main menu bar with a theme switcher."""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # --- Theme Menu ---
        theme_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="主题 (Theme)", menu=theme_menu)
        
        themes = ['litera', 'cosmo', 'superhero']
        for theme in themes:
            theme_menu.add_radiobutton(label=theme, variable=self.theme_name, command=self._change_theme)
            
    def _change_theme(self):
        """Applies the selected theme."""
        selected_theme = self.theme_name.get()
        self.style.theme_use(selected_theme)
        # Some elements might need an explicit update, but ttkbootstrap handles most.
        self.set_status(f"Theme changed to '{selected_theme}'")

    def _create_main_layout(self):
        """Creates the main resizable paned window."""
        main_pane = ttk.PanedWindow(self.root, orient=HORIZONTAL)
        main_pane.pack(fill=BOTH, expand=True, padx=10, pady=(5, 0))

        self.left_pane = ttk.Frame(main_pane)
        main_pane.add(self.left_pane, weight=1)

        self.right_pane = ttk.Frame(main_pane)
        main_pane.add(self.right_pane, weight=2)
        
        # Populate the panes
        self._create_left_pane_content(self.left_pane)

    def _create_left_pane_content(self, parent):
        """Creates all widgets for the left control pane."""
        parent.pack_propagate(False) # Prevent frame from shrinking
        
        # --- Common Settings Frame ---
        common_settings_frame = ttk.LabelFrame(parent, text="通用设置 (Common Settings)", padding=10)
        common_settings_frame.pack(side=TOP, fill=X, padx=5, pady=5)
        self._create_common_settings_widgets(common_settings_frame)

        # --- Recent Files Frame ---
        recent_files_frame = ttk.LabelFrame(parent, text="最近文件预览 (Recent Files Preview)", padding=10)
        recent_files_frame.pack(side=TOP, fill=X, padx=5, pady=5)
        self._create_recent_files_widgets(recent_files_frame)

        # --- Main Notebook for Measurement Tabs ---
        self.notebook = ttk.Notebook(parent, bootstyle="primary")
        self.notebook.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
        self._create_all_notebook_tabs(self.notebook)

    def _create_common_settings_widgets(self, parent):
        """Populates the Common Settings frame with widgets."""
        # Row 0: Output Path
        ttk.Label(parent, text="输出路径 (Output Path):").grid(row=0, column=0, sticky=W, pady=2)
        path_entry = ttk.Entry(parent, textvariable=self.output_dir)
        path_entry.grid(row=0, column=1, columnspan=2, sticky=EW, padx=5, pady=2)
        browse_btn = ttk.Button(parent, text="浏览...", command=self._browse_output_dir, bootstyle="secondary-outline")
        browse_btn.grid(row=0, column=3, sticky=E, padx=5, pady=2)

        # Row 1: File Name
        ttk.Label(parent, text="文件名 (File Name):").grid(row=1, column=0, sticky=W, pady=2)
        file_name_entry = ttk.Entry(parent, textvariable=self.file_name_base)
        file_name_entry.grid(row=1, column=1, columnspan=3, sticky=EW, padx=5, pady=2)

        # Row 2: Device Parameters
        device_params_frame = ttk.LabelFrame(parent, text="器件参数 (Device Parameters)", padding=5)
        device_params_frame.grid(row=2, column=0, columnspan=4, sticky=EW, pady=(10, 2))
        
        ttk.Label(device_params_frame, text="器件类型:").grid(row=0, column=0, sticky=W, padx=5)
        device_type_combo = ttk.Combobox(device_params_frame, textvariable=self.device_type, values=["lateral", "vertical"], state="readonly")
        device_type_combo.grid(row=0, column=1, sticky=EW, padx=5)
        device_type_combo.bind("<<ComboboxSelected>>", self.update_device_param_state)

        self.cw_label = ttk.Label(device_params_frame, text="沟道宽度 W (μm):")
        self.cw_label.grid(row=0, column=2, sticky=W, padx=(10, 2))
        self.cw_entry = ttk.Entry(device_params_frame, textvariable=self.channel_width_um, width=10)
        self.cw_entry.grid(row=0, column=3, sticky=W)

        self.area_label = ttk.Label(device_params_frame, text="器件面积 Area (μm²):")
        self.area_label.grid(row=0, column=4, sticky=W, padx=(10, 2))
        self.area_entry = ttk.Entry(device_params_frame, textvariable=self.area_um2, width=10)
        self.area_entry.grid(row=0, column=5, sticky=W, padx=(0, 5))
        
        parent.columnconfigure(2, weight=1)

    def _create_recent_files_widgets(self, parent):
        """Populates the recent files preview listbox."""
        self.recent_files_listbox = tk.Listbox(parent, height=5, exportselection=False)
        self.recent_files_listbox.pack(side=LEFT, fill=BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(parent, orient=VERTICAL, command=self.recent_files_listbox.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.recent_files_listbox.config(yscrollcommand=scrollbar.set)
        
        refresh_btn = ttk.Button(parent, text="刷新列表\n(Refresh List)", command=self.refresh_recent_files, bootstyle="secondary-outline")
        refresh_btn.pack(side=LEFT, padx=(10,0), fill=Y)

    def _create_all_notebook_tabs(self, notebook):
        """Creates and populates all the measurement tabs."""
        # Define structures for each tab's parameters
        self.gt_fields_structure = [
            ("基本测量参数", [
                ("漏极电流限制 (A):", "IlimitDrain", config_settings.GT_DEFAULT_ILIMIT_DRAIN),
                ("栅极电流限制 (A):", "IlimitGate", config_settings.GT_DEFAULT_ILIMIT_GATE),
                ("漏极 NPLC:", "Drain_nplc", config_settings.GT_DEFAULT_DRAIN_NPLC),
                ("栅极 NPLC:", "Gate_nplc", config_settings.GT_DEFAULT_GATE_NPLC),
                ("稳定延时 (s):", "settling_delay", config_settings.GT_DEFAULT_SETTLING_DELAY),
            ]),
            ("Vg 扫描设置", [
                ("Vg 起始 (V):", "Vg_start", config_settings.GT_DEFAULT_VG_START),
                ("Vg 终止 (V):", "Vg_stop", config_settings.GT_DEFAULT_VG_STOP),
                ("Vg 步进 (V):", "step", config_settings.GT_DEFAULT_VG_STEP),
            ]),
             ("Vd 固定偏置", [
                ("Vd 偏置 (V):", "Vd", config_settings.GT_DEFAULT_VD),
            ])
        ]
        
        self.oc_fields_structure = [
            ("基本测量参数", [
                ("漏极电流限制 (A):", "IlimitDrain", config_settings.OC_DEFAULT_ILIMIT_DRAIN),
                ("栅极电流限制 (A):", "IlimitGate", config_settings.OC_DEFAULT_ILIMIT_GATE),
                ("漏极 NPLC:", "Drain_nplc", config_settings.OC_DEFAULT_DRAIN_NPLC),
                ("栅极 NPLC:", "Gate_nplc", config_settings.OC_DEFAULT_GATE_NPLC),
                ("稳定延时 (s):", "settling_delay", config_settings.OC_DEFAULT_SETTLING_DELAY),
            ]),
            ("Vg 扫描设置", [
                ("Vg 起始 (V):", "Vg_start", config_settings.OC_DEFAULT_VG_START),
                ("Vg 终止 (V):", "Vg_stop", config_settings.OC_DEFAULT_VG_STOP),
                ("Vg 扫描段数:", "Vg_step", config_settings.OC_DEFAULT_VG_STEP),
            ]),
             ("Vd 扫描设置", [
                ("Vd 起始 (V):", "Vd_start", config_settings.OC_DEFAULT_VD_START),
                ("Vd 终止 (V):", "Vd_stop", config_settings.OC_DEFAULT_VD_STOP),
                ("Vd 步进 (V):", "Vd_step", config_settings.OC_DEFAULT_VD_STEP),
            ])
        ]

        self.bd_fields_structure = [
            ("基本测量参数", [
                ("漏极电流限制 (A):", "IlimitDrain", config_settings.BD_DEFAULT_ILIMIT_DRAIN),
                ("栅极电流限制 (A):", "IlimitGate", config_settings.BD_DEFAULT_ILIMIT_GATE),
                ("漏极 NPLC:", "Drain_nplc", config_settings.BD_DEFAULT_DRAIN_NPLC),
                ("栅极 NPLC:", "Gate_nplc", config_settings.BD_DEFAULT_GATE_NPLC),
                ("稳定延时 (s):", "settling_delay", config_settings.BD_DEFAULT_SETTLING_DELAY),
            ]),
            ("Vg 固定偏置", [
                ("Vg 偏置 (V):", "Vg", config_settings.BD_DEFAULT_VG),
            ]),
            ("Vd 扫描设置", [
                ("Vd 起始 (V):", "Vd_start", config_settings.BD_DEFAULT_VD_START),
                ("Vd 终止 (V):", "Vd_stop", config_settings.BD_DEFAULT_VD_STOP),
                ("Vd 步进 (V):", "Vd_step", config_settings.BD_DEFAULT_VD_STEP),
            ])
        ]

        self.diode_fields_structure = [
             ("基本测量参数", [
                ("阳极电流限制 (A):", "IlimitAnode", config_settings.DIODE_DEFAULT_ILIMIT_ANODE),
                ("阴极电流限制 (A):", "IlimitCathode", config_settings.DIODE_DEFAULT_ILIMIT_CATHODE),
                ("阳极 NPLC:", "Anode_nplc", config_settings.DIODE_DEFAULT_ANODE_NPLC),
                ("阴极 NPLC:", "Cathode_nplc", config_settings.DIODE_DEFAULT_CATHODE_NPLC),
                ("稳定延时 (s):", "settling_delay", config_settings.DIODE_DEFAULT_SETTLING_DELAY),
            ]),
            ("V_Anode 扫描设置", [
                ("V_Anode 起始 (V):", "Vanode_start", config_settings.DIODE_DEFAULT_VANODE_START),
                ("V_Anode 终止 (V):", "Vanode_stop", config_settings.DIODE_DEFAULT_VANODE_STOP),
                ("V_Anode 步进 (V):", "Vanode_step", config_settings.DIODE_DEFAULT_VANODE_STEP),
            ])
        ]

        self.stress_fields_structure = [
             ("应力条件", [
                ("VD stress (V):", "VD_stress_val", config_settings.STRESS_DEFAULT_VD_STRESS),
                ("VG stress (V):", "VG_stress_val", config_settings.STRESS_DEFAULT_VG_STRESS),
                ("VS stress (V):", "VS_stress_val", config_settings.STRESS_DEFAULT_VS_STRESS),
                ("应力时长 (s):", "stress_duration_val", config_settings.STRESS_DEFAULT_DURATION),
                ("测量间隔 (s):", "stress_measure_interval_val", config_settings.STRESS_DEFAULT_MEASURE_INTERVAL),
                ("初始稳定延时 (s):", "initial_settling_delay_stress", config_settings.STRESS_DEFAULT_INITIAL_SETTLING_DELAY),
            ]),
             ("应力测量参数", [
                ("Ilimit Drain (A):", "IlimitDrain_stress", config_settings.STRESS_DEFAULT_ILIMIT_DRAIN),
                ("Ilimit Gate (A):", "IlimitGate_stress", config_settings.STRESS_DEFAULT_ILIMIT_GATE),
                ("Ilimit Source (A):", "IlimitSource_stress", config_settings.STRESS_DEFAULT_ILIMIT_SOURCE),
                ("NPLC Drain:", "Drain_nplc_stress", config_settings.STRESS_DEFAULT_DRAIN_NPLC),
                ("NPLC Gate:", "Gate_nplc_stress", config_settings.STRESS_DEFAULT_GATE_NPLC),
                ("NPLC Source:", "Source_nplc_stress", config_settings.STRESS_DEFAULT_SOURCE_NPLC),
            ]),
        ]

        # Create tabs
        self._create_measurement_tab("栅转移特性 (Gate Transfer)", notebook, self.gt_fields_structure, self.gt_params_vars, has_backward_sweep=True, backward_var=self.gt_enable_backward)
        self._create_measurement_tab("输出特性 (Output Characteristics)", notebook, self.oc_fields_structure, self.oc_params_vars)
        self._create_stress_tab("应力测试 (Stress Test)", notebook)
        self._create_measurement_tab("晶体管击穿 (Transistor Breakdown)", notebook, self.bd_fields_structure, self.bd_params_vars)
        self._create_measurement_tab("二极管IV (Diode IV)", notebook, self.diode_fields_structure, self.diode_params_vars, has_backward_sweep=True, backward_var=self.diode_enable_backward)
        
        # History Tab is handled by its own class
        self.history_tab_frame = ttk.Frame(notebook)
        notebook.add(self.history_tab_frame, text="历史记录 (History)")

    def _create_measurement_tab(self, name, notebook, fields_structure, params_vars_dict, has_backward_sweep=False, backward_var=None):
        """A generic factory for creating a measurement tab."""
        tab_frame = ttk.Frame(notebook, padding=10)
        notebook.add(tab_frame, text=name)

        current_row = 0
        for section_title, fields in fields_structure:
            section_frame = ttk.LabelFrame(tab_frame, text=section_title, padding=10)
            section_frame.grid(row=current_row, column=0, columnspan=2, sticky=EW, pady=5)
            current_row += 1
            
            for i, (label_text, key, default_val) in enumerate(fields):
                var = tk.StringVar(value=str(default_val))
                params_vars_dict[key] = {"var": var, "default": str(default_val)}
                ttk.Label(section_frame, text=label_text).grid(row=i, column=0, sticky=W, padx=5, pady=3)
                entry = ttk.Entry(section_frame, textvariable=var, width=20)
                entry.grid(row=i, column=1, sticky=EW, padx=5, pady=3)
            section_frame.columnconfigure(1, weight=1)

        if has_backward_sweep:
            ttk.Checkbutton(tab_frame, text="启用反向扫描 (Enable Backward Sweep)", variable=backward_var, bootstyle="primary-round-toggle").grid(row=current_row, column=0, sticky=W, pady=10)
            current_row += 1

        reset_btn = ttk.Button(tab_frame, text="恢复默认值 (Reset to Defaults)", command=lambda d=params_vars_dict: self._reset_tab_defaults(d), bootstyle="secondary-outline")
        reset_btn.grid(row=current_row, column=1, sticky=E, pady=10)

        tab_frame.columnconfigure(1, weight=1)

    def _create_stress_tab(self, name, notebook):
        """Creates the specific tab for Stress Test with post-characterization options."""
        tab_frame = ttk.Frame(notebook, padding=10)
        notebook.add(tab_frame, text=name)
        
        # Use the generic method to create parameter entry fields
        current_row = 0
        for section_title, fields in self.stress_fields_structure:
            section_frame = ttk.LabelFrame(tab_frame, text=section_title, padding=10)
            section_frame.grid(row=current_row, column=0, columnspan=2, sticky=EW, pady=5)
            current_row += 1
            for i, (label_text, key, default_val) in enumerate(fields):
                var = tk.StringVar(value=str(default_val))
                self.stress_params_vars[key] = {"var": var, "default": str(default_val)}
                ttk.Label(section_frame, text=label_text).grid(row=i, column=0, sticky=W, padx=5, pady=3)
                entry = ttk.Entry(section_frame, textvariable=var, width=20)
                entry.grid(row=i, column=1, sticky=EW, padx=5, pady=3)
            section_frame.columnconfigure(1, weight=1)

        # Add post-characterization options
        post_char_frame = ttk.LabelFrame(tab_frame, text="应力后表征 (Post-Stress Characterization)", padding=10)
        post_char_frame.grid(row=current_row, column=0, columnspan=2, sticky=EW, pady=5)
        current_row += 1

        ttk.Label(post_char_frame, text="方法:").grid(row=0, column=0, sticky=W, padx=5)
        post_char_combo = ttk.Combobox(post_char_frame, textvariable=self.post_stress_char_method, 
                                       values=["栅转移特性 (Gate Transfer)", "输出特性 (Output Characteristics)", "无 (None)"], 
                                       state="readonly")
        post_char_combo.grid(row=0, column=1, sticky=EW, padx=5)
        post_char_frame.columnconfigure(1, weight=1)

        ttk.Label(post_char_frame, text="注意: 应力后表征将使用其他选项卡中当前的参数设置。", wraplength=400, bootstyle="secondary").grid(row=1, column=0, columnspan=2, sticky=W, padx=5, pady=(5,0))

        reset_btn = ttk.Button(tab_frame, text="恢复默认值 (Reset to Defaults)", command=lambda d=self.stress_params_vars: self._reset_tab_defaults(d), bootstyle="secondary-outline")
        reset_btn.grid(row=current_row, column=1, sticky=E, pady=10)

        tab_frame.columnconfigure(1, weight=1)

    def _reset_tab_defaults(self, params_vars_dict):
        """Resets all entries in a given tab to their default values."""
        for key in params_vars_dict:
            params_vars_dict[key]["var"].set(params_vars_dict[key]["default"])
        # Also reset checkbuttons if they are part of the reset logic (optional)
        if params_vars_dict is self.gt_params_vars:
            self.gt_enable_backward.set(False)
        elif params_vars_dict is self.diode_params_vars:
            self.diode_enable_backward.set(False)

    def _create_status_bar(self):
        """Creates the bottom status bar and control buttons."""
        status_bar_frame = ttk.Frame(self.root, padding=(5, 5))
        status_bar_frame.pack(side=BOTTOM, fill=X)

        self.status_label = ttk.Label(status_bar_frame, text="准备就绪 (Ready)", anchor=W)
        self.status_label.pack(side=LEFT, fill=X, expand=True)

        self.exit_button = ttk.Button(status_bar_frame, text="退出 (Exit)", command=self.root.quit, bootstyle="danger")
        self.exit_button.pack(side=RIGHT, padx=(5, 0))

        self.run_button = ttk.Button(status_bar_frame, text="▶ 运行 (Run)", command=self._run_measurement_wrapper, bootstyle="success")
        self.run_button.pack(side=RIGHT)

    def _run_measurement_wrapper(self):
        """Wrapper to call the measurement handler."""
        if self.measurement_handler:
            self.measurement_handler.run_measurement()
        else:
            messagebox.showerror("错误", "测量处理器未初始化。")

    def _browse_output_dir(self):
        """Opens a dialog to choose an output directory."""
        dir_name = filedialog.askdirectory(initialdir=self.output_dir.get())
        if dir_name:
            self.output_dir.set(dir_name)
            self.refresh_recent_files()

    def update_device_param_state(self, event=None):
        """Enables/disables channel width or area entries based on device type."""
        if self.device_type.get() == 'lateral':
            self.cw_entry.config(state="normal")
            self.area_entry.config(state="disabled")
            self.cw_label.config(bootstyle="default")
            self.area_label.config(bootstyle="secondary")
        else: # vertical
            self.cw_entry.config(state="disabled")
            self.area_entry.config(state="normal")
            self.cw_label.config(bootstyle="secondary")
            self.area_label.config(bootstyle="default")

    def refresh_recent_files(self):
        """Refreshes the list of recent files in the preview box."""
        self.recent_files_listbox.delete(0, tk.END)
        output_dir = self.output_dir.get()
        if not os.path.isdir(output_dir):
            self.recent_files_listbox.insert(tk.END, "输出目录无效或未设置。")
            return
        try:
            # Get CSV files and sort by modification time, newest first
            files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
            files.sort(key=lambda name: os.path.getmtime(os.path.join(output_dir, name)), reverse=True)
            if files:
                for f_name in files[:20]: # Show up to 20 recent files
                    self.recent_files_listbox.insert(tk.END, f_name)
            else:
                self.recent_files_listbox.insert(tk.END, "未找到CSV文件。")
        except Exception as e:
            self.recent_files_listbox.insert(tk.END, f"读取文件列表时出错: {e}")
            print(f"Error refreshing recent files list: {e}", file=sys.stderr)

    def set_status(self, message, error=False):
        """Updates the status bar message."""
        self.status_label.config(text=message)
        if error:
            self.status_label.config(bootstyle="danger")
        else:
            self.status_label.config(bootstyle="default")
        self.root.update_idletasks()


if __name__ == "__main__":
    # Ensure the default output directory exists
    if not os.path.exists(config_settings.DEFAULT_OUTPUT_DIR):
        os.makedirs(config_settings.DEFAULT_OUTPUT_DIR)
        
    # Start with the 'litera' theme as default
    root = ttk.Window(themename="litera")
    app = Application(root)
    root.mainloop()