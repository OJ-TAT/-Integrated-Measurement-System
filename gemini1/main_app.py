# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import traceback
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

import gui_utils
import history_tab_module
import live_plot_module
import measurement_handler
import gate_transfer_module
import output_module
import breakdown_module
import diode_module
import stress_module # New import
import config_settings

class MeasurementApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("集成测量系统 (Integrated Measurement System v1.16.0_stress_delay)") # Version updated
        self.root.minsize(1000, 780)
        self.root.configure(bg='#F0F0F0')

        self.style_config = gui_utils.get_style()

        self.output_dir = tk.StringVar(value=config_settings.DEFAULT_OUTPUT_DIR)
        self.file_name_base = tk.StringVar()
        self.device_type = tk.StringVar(value="lateral")
        self.channel_width_um = tk.StringVar(value=config_settings.DEVICE_DEFAULT_CHANNEL_WIDTH_UM)
        self.area_um2 = tk.StringVar(value=config_settings.DEVICE_DEFAULT_AREA_UM2)

        self.gt_fields_structure = [
            ("漏极电流限制 (A):", "IlimitDrain", config_settings.GT_DEFAULT_ILIMIT_DRAIN),
            ("栅极电流限制 (A):", "IlimitGate", config_settings.GT_DEFAULT_ILIMIT_GATE),
            ("漏极NPLC:", "Drain_nplc", config_settings.GT_DEFAULT_DRAIN_NPLC),
            ("栅极NPLC:", "Gate_nplc", config_settings.GT_DEFAULT_GATE_NPLC),
            ("Vg 起始 (V):", "Vg_start", config_settings.GT_DEFAULT_VG_START),
            ("Vg 终止 (V):", "Vg_stop", config_settings.GT_DEFAULT_VG_STOP),
            ("Vg 步进 (V):", "step", config_settings.GT_DEFAULT_VG_STEP),
            ("Vd (V):", "Vd", config_settings.GT_DEFAULT_VD),
            ("稳定延时 (s):", "settling_delay", config_settings.GT_DEFAULT_SETTLING_DELAY)
        ]
        self.oc_fields_structure = [
            ("漏极电流限制 (A):", "IlimitDrain", config_settings.OC_DEFAULT_ILIMIT_DRAIN),
            ("栅极电流限制 (A):", "IlimitGate", config_settings.OC_DEFAULT_ILIMIT_GATE),
            ("漏极NPLC:", "Drain_nplc", config_settings.OC_DEFAULT_DRAIN_NPLC),
            ("栅极NPLC:", "Gate_nplc", config_settings.OC_DEFAULT_GATE_NPLC),
            ("Vg 起始 (V):", "Vg_start", config_settings.OC_DEFAULT_VG_START),
            ("Vg 终止 (V):", "Vg_stop", config_settings.OC_DEFAULT_VG_STOP),
            ("Vg 扫描段数:", "Vg_step", config_settings.OC_DEFAULT_VG_STEP),
            ("Vd 起始 (V):", "Vd_start", config_settings.OC_DEFAULT_VD_START),
            ("Vd 终止 (V):", "Vd_stop", config_settings.OC_DEFAULT_VD_STOP),
            ("Vd 步进 (V):", "Vd_step", config_settings.OC_DEFAULT_VD_STEP),
            ("稳定延时 (s):", "settling_delay", config_settings.OC_DEFAULT_SETTLING_DELAY)
        ]
        self.bd_fields_structure = [
            ("漏极电流限制 (A):", "IlimitDrain", config_settings.BD_DEFAULT_ILIMIT_DRAIN),
            ("栅极电流限制 (A):", "IlimitGate", config_settings.BD_DEFAULT_ILIMIT_GATE),
            ("漏极NPLC:", "Drain_nplc", config_settings.BD_DEFAULT_DRAIN_NPLC),
            ("栅极NPLC:", "Gate_nplc", config_settings.BD_DEFAULT_GATE_NPLC),
            ("栅极电压 (V):", "Vg", config_settings.BD_DEFAULT_VG),
            ("Vd 起始 (V):", "Vd_start", config_settings.BD_DEFAULT_VD_START),
            ("Vd 终止 (V):", "Vd_stop", config_settings.BD_DEFAULT_VD_STOP),
            ("Vd 步进 (V):", "Vd_step", config_settings.BD_DEFAULT_VD_STEP),
            ("稳定延时 (s):", "settling_delay", config_settings.BD_DEFAULT_SETTLING_DELAY)
        ]
        self.diode_fields_structure = [
            ("阳极电流限制 (A):", "IlimitAnode", config_settings.DIODE_DEFAULT_ILIMIT_ANODE),
            ("阴极电流限制 (A):", "IlimitCathode", config_settings.DIODE_DEFAULT_ILIMIT_CATHODE),
            ("阳极NPLC:", "Anode_nplc", config_settings.DIODE_DEFAULT_ANODE_NPLC),
            ("阴极NPLC:", "Cathode_nplc", config_settings.DIODE_DEFAULT_CATHODE_NPLC),
            ("阳极起始电压 (V):", "Vanode_start", config_settings.DIODE_DEFAULT_VANODE_START),
            ("阳极终止电压 (V):", "Vanode_stop", config_settings.DIODE_DEFAULT_VANODE_STOP),
            ("阳极电压步进 (V):", "Vanode_step", config_settings.DIODE_DEFAULT_VANODE_STEP),
            ("稳定延时 (s):", "settling_delay", config_settings.DIODE_DEFAULT_SETTLING_DELAY)
        ]
        # New: Stress Test fields structure
        self.stress_fields_structure = [
            ("漏极应力电压 (V):", "VD_stress_val", config_settings.STRESS_DEFAULT_VD_STRESS),
            ("栅极应力电压 (V):", "VG_stress_val", config_settings.STRESS_DEFAULT_VG_STRESS),
            ("源极应力电压 (V):", "VS_stress_val", config_settings.STRESS_DEFAULT_VS_STRESS),
            ("应力持续时间 (s):", "stress_duration_val", config_settings.STRESS_DEFAULT_DURATION),
            ("应力测量间隔 (s):", "stress_measure_interval_val", config_settings.STRESS_DEFAULT_MEASURE_INTERVAL),
            ("初始稳定延时 (s):", "initial_settling_delay_stress", config_settings.STRESS_DEFAULT_INITIAL_SETTLING_DELAY), # New field
            ("漏极电流限制 (A):", "IlimitDrain_stress", config_settings.STRESS_DEFAULT_ILIMIT_DRAIN),
            ("栅极电流限制 (A):", "IlimitGate_stress", config_settings.STRESS_DEFAULT_ILIMIT_GATE),
            ("源极电流限制 (A):", "IlimitSource_stress", config_settings.STRESS_DEFAULT_ILIMIT_SOURCE),
            ("漏极NPLC:", "Drain_nplc_stress", config_settings.STRESS_DEFAULT_DRAIN_NPLC),
            ("栅极NPLC:", "Gate_nplc_stress", config_settings.STRESS_DEFAULT_GATE_NPLC),
            ("源极NPLC:", "Source_nplc_stress", config_settings.STRESS_DEFAULT_SOURCE_NPLC),
        ]


        self.gt_params_vars = {}
        self.oc_params_vars = {}
        self.bd_params_vars = {}
        self.diode_params_vars = {}
        self.stress_params_vars = {} # New

        self.gt_enable_backward = tk.BooleanVar(value=True)
        self.diode_enable_backward = tk.BooleanVar(value=True)
        
        # New: Variable for post-stress characterization method
        self.post_stress_char_method = tk.StringVar(value="栅转移特性 (Gate Transfer)") # Default to Gate Transfer

        self._create_main_layout()

        self.live_plot_handler = live_plot_module.LivePlotHandler(self, self.right_pane_frame_for_live_plot)
        self.measurement_handler = measurement_handler.MeasurementHandler(self, self.live_plot_handler)
        self.history_tab_handler_instance = history_tab_module.HistoryTabHandler(self, self.history_tab)

        gui_utils.toggle_device_parameter_input(self)
        gui_utils.set_status(self, "准备就绪 (Ready)")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        if hasattr(self.live_plot_handler, 'live_annotation_managers'):
            for manager in self.live_plot_handler.live_annotation_managers: manager.disconnect_motion_event()
            self.live_plot_handler.live_annotation_managers.clear()
        if hasattr(self.live_plot_handler, 'live_crosshair_features'):
            for ch in self.live_plot_handler.live_crosshair_features: ch.disconnect()
            self.live_plot_handler.live_crosshair_features.clear()
        if hasattr(self.history_tab_handler_instance, 'history_annotation_managers'):
            for manager in self.history_tab_handler_instance.history_annotation_managers: manager.disconnect_motion_event()
            self.history_tab_handler_instance.history_annotation_managers.clear()
        if hasattr(self.history_tab_handler_instance, 'history_crosshair_features'):
            for ch in self.history_tab_handler_instance.history_crosshair_features: ch.disconnect()
            self.history_tab_handler_instance.history_crosshair_features.clear()
        self.root.destroy()

    def _create_main_layout(self):
        self._create_control_and_status_bar()
        self.main_horizontal_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_horizontal_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5,0))
        self.left_vertical_pane = ttk.PanedWindow(self.main_horizontal_pane, orient=tk.VERTICAL)
        self.main_horizontal_pane.add(self.left_vertical_pane, weight=1)
        self._create_file_device_settings_frame()
        self.notebook_frame_container = ttk.Frame(self.left_vertical_pane, padding=(0,0))
        self.left_vertical_pane.add(self.notebook_frame_container, weight=3)
        self._create_notebook(self.notebook_frame_container)
        self.right_pane_frame_for_live_plot = ttk.Frame(self.main_horizontal_pane, padding=(0,0))
        self.main_horizontal_pane.add(self.right_pane_frame_for_live_plot, weight=2)
        self.root.after_idle(lambda: self.main_horizontal_pane.sashpos(0, 380))
        self._on_tab_changed()

    def _create_file_device_settings_frame(self):
        self.common_settings_frame = ttk.LabelFrame(self.left_vertical_pane, text="通用设置 (Common Settings)",
                                                    padding=(self.style_config['padx'], self.style_config['pady']))
        self.left_vertical_pane.add(self.common_settings_frame, weight=1)

        dir_frame = ttk.Frame(self.common_settings_frame)
        dir_frame.pack(fill=tk.X, expand=True, pady=(4,2))
        dir_frame.columnconfigure(1, weight=1)
        ttk.Label(dir_frame, text="输出路径 (Output Path):", font=self.style_config['font_label']).grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.entry_output_dir = ttk.Entry(dir_frame, textvariable=self.output_dir)
        self.entry_output_dir.grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(dir_frame, text="浏览... (Browse...)", command=lambda: gui_utils.browse_directory(self), width=12).grid(row=0, column=2, sticky=tk.E, padx=(5,0))

        file_frame = ttk.Frame(self.common_settings_frame)
        file_frame.pack(fill=tk.X, expand=True, pady=(2,4))
        file_frame.columnconfigure(1, weight=1)
        ttk.Label(file_frame, text="文件名 (File Name):", font=self.style_config['font_label']).grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.entry_file_name_base = ttk.Entry(file_frame, textvariable=self.file_name_base)
        self.entry_file_name_base.grid(row=0, column=1, sticky=tk.EW, padx=5)

        device_frame = ttk.LabelFrame(self.common_settings_frame, text="器件参数 (Device Parameters - for Current Density)")
        device_frame.pack(fill=tk.X, expand=True, padx=5, pady=(8,4), ipady=5)
        radio_frame = ttk.Frame(device_frame)
        radio_frame.pack(fill=tk.X, expand=True, pady=(6,2))
        ttk.Radiobutton(radio_frame, text="横向 (Lateral, mA/mm)", variable=self.device_type, value="lateral", command=lambda: gui_utils.toggle_device_parameter_input(self)).pack(side=tk.LEFT, padx=10, expand=True, anchor=tk.W)
        ttk.Radiobutton(radio_frame, text="纵向 (Vertical, A/cm²)", variable=self.device_type, value="vertical", command=lambda: gui_utils.toggle_device_parameter_input(self)).pack(side=tk.LEFT, padx=10, expand=True, anchor=tk.W)
        param_grid = ttk.Frame(device_frame)
        param_grid.pack(fill=tk.X, expand=True, pady=(2,4))
        param_grid.columnconfigure(1, weight=0); param_grid.columnconfigure(0, weight=0)
        self.lbl_channel_width = ttk.Label(param_grid, text="宽度 W (µm):", font=self.style_config['font_label'])
        self.lbl_channel_width.grid(row=0, column=0, sticky=tk.E, padx=(10,2), pady=3)
        self.entry_channel_width = ttk.Entry(param_grid, textvariable=self.channel_width_um, width=self.style_config['entry_width'])
        self.entry_channel_width.grid(row=0, column=1, padx=(0,10), pady=3, sticky=tk.W)
        self.lbl_area = ttk.Label(param_grid, text="面积 Area (µm²):", font=self.style_config['font_label'])
        self.lbl_area.grid(row=1, column=0, sticky=tk.E, padx=(10,2), pady=3)
        self.entry_area = ttk.Entry(param_grid, textvariable=self.area_um2, width=self.style_config['entry_width'])
        self.entry_area.grid(row=1, column=1, padx=(0,10), pady=3, sticky=tk.W)

    def _on_tab_changed(self, event=None):
        if not all(hasattr(self, attr) for attr in ['notebook', 'common_settings_frame', 'left_vertical_pane', 'main_horizontal_pane', 'right_pane_frame_for_live_plot', 'notebook_frame_container']): return
        try:
            selected_tab_widget_id = self.notebook.select()
            selected_tab_text = self.notebook.tab(selected_tab_widget_id, "text") if selected_tab_widget_id else ""
        except tk.TclError: selected_tab_text = ""
        
        is_history_tab = (selected_tab_text == '历史记录 (History)')
        current_left_panes = self.left_vertical_pane.panes()
        is_common_settings_visible = False
        if self.common_settings_frame:
            try: is_common_settings_visible = str(self.common_settings_frame) in current_left_panes
            except tk.TclError: is_common_settings_visible = False
        
        if is_history_tab:
            if is_common_settings_visible: self.left_vertical_pane.forget(self.common_settings_frame)
        else:
            if not is_common_settings_visible and self.common_settings_frame:
                is_notebook_container_visible = False
                if self.notebook_frame_container:
                    try: is_notebook_container_visible = str(self.notebook_frame_container) in current_left_panes
                    except tk.TclError: is_notebook_container_visible = False
                if is_notebook_container_visible: self.left_vertical_pane.insert(0, self.common_settings_frame, weight=1)
                else:
                    self.left_vertical_pane.add(self.common_settings_frame, weight=1)
                    if self.notebook_frame_container and not (str(self.notebook_frame_container) in self.left_vertical_pane.panes()):
                         self.left_vertical_pane.add(self.notebook_frame_container, weight=3)
        
        current_main_panes = self.main_horizontal_pane.panes()
        is_right_pane_currently_visible = False
        if self.right_pane_frame_for_live_plot:
            try: is_right_pane_currently_visible = str(self.right_pane_frame_for_live_plot) in current_main_panes
            except tk.TclError: is_right_pane_currently_visible = False
        
        if is_history_tab:
            if is_right_pane_currently_visible: self.main_horizontal_pane.forget(self.right_pane_frame_for_live_plot)
        else:
            if not is_right_pane_currently_visible and self.right_pane_frame_for_live_plot:
                is_left_vertical_pane_visible = False
                if self.left_vertical_pane:
                    try: is_left_vertical_pane_visible = str(self.left_vertical_pane) in current_main_panes
                    except tk.TclError: is_left_vertical_pane_visible = False
                if is_left_vertical_pane_visible: self.main_horizontal_pane.add(self.right_pane_frame_for_live_plot, weight=3)
                else:
                    for pane_path in list(self.main_horizontal_pane.panes()):
                        try: self.main_horizontal_pane.forget(self.root.nametowidget(pane_path))
                        except tk.TclError: pass
                    self.main_horizontal_pane.add(self.left_vertical_pane, weight=1)
                    self.main_horizontal_pane.add(self.right_pane_frame_for_live_plot, weight=3)

    def _create_notebook(self, parent_frame):
        self.notebook = ttk.Notebook(parent_frame)
        self.notebook.pack(expand=True, fill='both', padx=0, pady=0)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        self.gate_transfer_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.output_char_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.breakdown_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.diode_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.stress_tab = ttk.Frame(self.notebook, padding=(0,0)) # New Stress Tab
        self.history_tab = ttk.Frame(self.notebook)
        
        for tab in [self.gate_transfer_tab, self.output_char_tab, self.breakdown_tab, self.diode_tab, self.stress_tab, self.history_tab]:
            tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
            
        self.notebook.add(self.gate_transfer_tab, text='栅转移特性 (Gate Transfer)')
        self.notebook.add(self.output_char_tab, text='输出特性 (Output Characteristics)')
        self.notebook.add(self.stress_tab, text='应力测试 (Stress Test)') # Add Stress Tab
        self.notebook.add(self.breakdown_tab, text='晶体管击穿 (Transistor Breakdown)')
        self.notebook.add(self.diode_tab, text='二极管IV (Diode IV)')
        self.notebook.add(self.history_tab, text='历史记录 (History)')
        
        self._populate_measurement_tabs()

    def _populate_measurement_tabs(self):
        # Gate Transfer Tab
        frame_gt = self.gate_transfer_tab
        ttk.Label(frame_gt, text="栅转移特性参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        measurement_settings_gt = [f for f in self.gt_fields_structure if f[1] in ["IlimitDrain", "IlimitGate", "Drain_nplc", "Gate_nplc", "settling_delay"]]
        vg_settings_gt = [f for f in self.gt_fields_structure if f[1] in ["Vg_start", "Vg_stop", "step"]]
        vd_settings_gt = [f for f in self.gt_fields_structure if f[1] == "Vd"]
        gui_utils.create_param_frame(self, frame_gt, "基本测量设置", measurement_settings_gt, self.gt_params_vars)
        gui_utils.create_param_frame(self, frame_gt, "Vg 扫描设置", vg_settings_gt, self.gt_params_vars, context_keys={'start':'Vg_start', 'stop':'Vg_stop', 'step':'step'})
        gui_utils.create_param_frame(self, frame_gt, "Vd 固定偏置", vd_settings_gt, self.gt_params_vars, columns=1)
        ttk.Checkbutton(frame_gt, text="启用反向扫描 (Enable Backward Sweep)", variable=self.gt_enable_backward).pack(anchor=tk.W, padx=self.style_config['padx']+5, pady=(5,0), fill=tk.X)
        gui_utils.add_reset_button_to_tab(self, frame_gt, self.gt_params_vars, self.gt_fields_structure, "栅转移特性")

        # Output Characteristics Tab
        frame_oc = self.output_char_tab
        ttk.Label(frame_oc, text="输出特性参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        measurement_settings_oc = [f for f in self.oc_fields_structure if f[1] in ["IlimitDrain", "IlimitGate", "Drain_nplc", "Gate_nplc", "settling_delay"]]
        vg_settings_oc = [f for f in self.oc_fields_structure if f[1] in ["Vg_start", "Vg_stop", "Vg_step"]]
        vd_settings_oc = [f for f in self.oc_fields_structure if f[1] in ["Vd_start", "Vd_stop", "Vd_step"]]
        gui_utils.create_param_frame(self, frame_oc, "基本测量设置", measurement_settings_oc, self.oc_params_vars)
        gui_utils.create_param_frame(self, frame_oc, "Vg 扫描设置", vg_settings_oc, self.oc_params_vars, context_keys={'start':'Vg_start', 'stop':'Vg_stop', 'step':'Vg_step'})
        gui_utils.create_param_frame(self, frame_oc, "Vd 扫描设置", vd_settings_oc, self.oc_params_vars, context_keys={'start':'Vd_start', 'stop':'Vd_stop', 'step':'Vd_step'})
        gui_utils.add_reset_button_to_tab(self, frame_oc, self.oc_params_vars, self.oc_fields_structure, "输出特性")

        # Stress Test Tab (New)
        frame_st = self.stress_tab
        ttk.Label(frame_st, text="应力测试参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        
        stress_voltage_fields = [f for f in self.stress_fields_structure if f[1] in ["VD_stress_val", "VG_stress_val", "VS_stress_val"]]
        stress_time_fields = [f for f in self.stress_fields_structure if f[1] in ["stress_duration_val", "stress_measure_interval_val", "initial_settling_delay_stress"]] # Added new delay
        stress_limit_nplc_fields = [f for f in self.stress_fields_structure if f[1] not in ["VD_stress_val", "VG_stress_val", "VS_stress_val", "stress_duration_val", "stress_measure_interval_val", "initial_settling_delay_stress"]]
        
        gui_utils.create_param_frame(self, frame_st, "应力电压设置", stress_voltage_fields, self.stress_params_vars, columns=1)
        gui_utils.create_param_frame(self, frame_st, "应力时间与延时设置", stress_time_fields, self.stress_params_vars, columns=1) # Changed to 1 column for better layout with 3 items
        gui_utils.create_param_frame(self, frame_st, "电流限制和NPLC设置", stress_limit_nplc_fields, self.stress_params_vars, columns=2)

        # Post-Stress Characterization Selection
        post_stress_frame = ttk.LabelFrame(frame_st, text="应力后特性表征 (Post-Stress Characterization)", padding=(self.style_config['padx']-4, self.style_config['pady']-4))
        post_stress_frame.pack(fill=tk.X, expand=True, padx=self.style_config['padx']-2, pady=(10,2), ipady=5)
        
        ttk.Label(post_stress_frame, text="选择表征方法:", font=self.style_config['font_label']).pack(side=tk.LEFT, padx=(5,5), pady=5)
        char_methods = ["无 (None)", "栅转移特性 (Gate Transfer)", "输出特性 (Output Characteristics)"] # Add more as needed
        self.post_stress_char_combobox = ttk.Combobox(post_stress_frame, textvariable=self.post_stress_char_method, values=char_methods, state="readonly", width=30)
        self.post_stress_char_combobox.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.post_stress_char_combobox.set("栅转移特性 (Gate Transfer)") # Default selection
        
        gui_utils.add_reset_button_to_tab(self, frame_st, self.stress_params_vars, self.stress_fields_structure, "应力测试")


        # Breakdown Tab
        frame_bd = self.breakdown_tab
        ttk.Label(frame_bd, text="晶体管击穿参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        measurement_settings_bd = [f for f in self.bd_fields_structure if f[1] in ["IlimitDrain", "IlimitGate", "Drain_nplc", "Gate_nplc", "Vg", "settling_delay"]]
        vd_settings_bd = [f for f in self.bd_fields_structure if f[1] in ["Vd_start", "Vd_stop", "Vd_step"]]
        gui_utils.create_param_frame(self, frame_bd, "测量设置", measurement_settings_bd, self.bd_params_vars)
        gui_utils.create_param_frame(self, frame_bd, "Vd 扫描设置", vd_settings_bd, self.bd_params_vars, context_keys={'start':'Vd_start', 'stop':'Vd_stop', 'step':'Vd_step'})
        gui_utils.add_reset_button_to_tab(self, frame_bd, self.bd_params_vars, self.bd_fields_structure, "晶体管击穿")

        # Diode Tab
        frame_diode = self.diode_tab
        ttk.Label(frame_diode, text="二极管IV参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        measurement_settings_diode = [f for f in self.diode_fields_structure if f[1] in ["IlimitAnode", "IlimitCathode", "Anode_nplc", "Cathode_nplc", "settling_delay"]]
        vanode_settings_diode = [f for f in self.diode_fields_structure if f[1] in ["Vanode_start", "Vanode_stop", "Vanode_step"]]
        gui_utils.create_param_frame(self, frame_diode, "测量设置", measurement_settings_diode, self.diode_params_vars)
        gui_utils.create_param_frame(self, frame_diode, "阳极扫描设置", vanode_settings_diode, self.diode_params_vars, context_keys={'start':'Vanode_start', 'stop':'Vanode_stop', 'step':'Vanode_step'})
        ttk.Checkbutton(frame_diode, text="启用反向扫描 (Enable Backward Sweep)", variable=self.diode_enable_backward).pack(anchor=tk.W, padx=self.style_config['padx']+5, pady=(5,0), fill=tk.X)
        gui_utils.add_reset_button_to_tab(self, frame_diode, self.diode_params_vars, self.diode_fields_structure, "二极管IV")

    def _create_control_and_status_bar(self):
        self.bottom_frame = ttk.Frame(self.root, padding=(self.style_config['padx'], self.style_config['pady'] // 2))
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=12, pady=(4, 8))
        btn_container = ttk.Frame(self.bottom_frame)
        btn_container.pack(side=tk.TOP, pady=(0, 5))
        s = ttk.Style(); s.theme_use('clam')
        s.configure('Run.TButton', font=self.style_config['font_button'], foreground='white', background='#28a745', borderwidth=1, padding=6)
        s.map('Run.TButton', background=[('active', '#218838'), ('pressed', '#1e7e34')])
        s.configure('Exit.TButton', font=self.style_config['font_button'], foreground='white', background='#dc3545', padding=6)
        s.map('Exit.TButton', background=[('active', '#c82333'), ('pressed', '#bd2130')])
        self.run_button = ttk.Button(btn_container, text="▶ 运行 (Run)", command=lambda: self.measurement_handler.run_measurement(), style='Run.TButton', width=14 )
        self.run_button.pack(side=tk.LEFT, padx=20, ipady=4)
        exit_button = ttk.Button(btn_container, text="退出 (Exit)", command=self._on_closing, style='Exit.TButton', width=14)
        exit_button.pack(side=tk.RIGHT, padx=20, ipady=4)
        self.status_bar_label = ttk.Label(self.bottom_frame, text="准备就绪 (Ready)", anchor=tk.W, relief=tk.SUNKEN, padding=(5,2))
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))

if __name__ == '__main__':
    app_root = tk.Tk()
    gui = MeasurementApp(app_root)
    default_dir_from_gui_init = gui.output_dir.get()
    if not os.path.exists(default_dir_from_gui_init):
        try:
            os.makedirs(default_dir_from_gui_init)
            print(f"已创建默认输出目录: {default_dir_from_gui_init}")
        except Exception as e:
            new_dir = os.getcwd()
            print(f"无法创建默认输出目录 {default_dir_from_gui_init}: {e}。使用当前目录: {new_dir}", file=sys.stderr)
            gui.output_dir.set(new_dir)
            messagebox.showwarning("目录警告", f"无法创建默认目录:\n{default_dir_from_gui_init}\n\n输出目录已设置为当前工作目录:\n{new_dir}")
    if hasattr(gui, 'history_tab_handler_instance') and gui.history_tab_handler_instance and \
       hasattr(gui.history_tab_handler_instance, 'history_plot_canvas') and gui.history_tab_handler_instance.history_plot_canvas is not None:
        gui.history_tab_handler_instance.refresh_file_list()
    else:
        print("历史记录绘图区域未成功初始化，跳过初始文件列表刷新。", file=sys.stderr)
    if hasattr(gui, 'live_plot_handler') and gui.live_plot_handler and \
       hasattr(gui.live_plot_handler, 'live_plot_canvas') and gui.live_plot_handler.live_plot_canvas is None:
        print("实时绘图区域未成功初始化。", file=sys.stderr)
    app_root.mainloop()
