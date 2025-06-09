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
# import json # Removed for sash persistence rollback

import gui_utils
import history_tab_module
import live_plot_module
import measurement_handler
import gate_transfer_module
import output_module
import breakdown_module
import diode_module
import stress_module 
import config_settings

class MeasurementApp:
    # CONFIG_FILE_NAME = "gui_layout_config.json" # Removed for sash persistence rollback

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("集成测量系统 (Integrated Measurement System v1.17.5_condensed_layout)") # Reverted version, then new layout
        self.root.minsize(1000, 800)
        self.root.state('zoomed')
        self.root.configure(bg='#F0F0F0')

        self.style_config = gui_utils.get_style()

        self.output_dir = tk.StringVar(value=config_settings.DEFAULT_OUTPUT_DIR)
        self.file_name_base = tk.StringVar() 
        self.device_type = tk.StringVar(value="lateral")
        self.channel_width_um = tk.StringVar(value=config_settings.DEVICE_DEFAULT_CHANNEL_WIDTH_UM)
        self.area_um2 = tk.StringVar(value=config_settings.DEVICE_DEFAULT_AREA_UM2)

        # --- Auto Device ID StringVars ---
        self.project_prefix = tk.StringVar(value="MyChip")
        self.current_cell_id = tk.StringVar(value="1")
        self.current_row_id = tk.StringVar(value="A")
        self.current_col_id = tk.StringVar(value="1")
        
        # --- Configuration for Auto Device ID ---
        self.ROW_IDS = [chr(ord('A') + i) for i in range(10)] 
        self.MAX_COL = 12 
        self.MAX_CELL = 4 

        # --- PanedWindow Weights ---
        self.COMMON_SETTINGS_PANE_WEIGHT = 5 
        self.RECENT_FILES_PANE_WEIGHT = 2 
        self.NOTEBOOK_PANE_WEIGHT = 80 

        # --- Recent Files Listbox ---
        self.recent_files_listbox = None
        self.recent_files_frame_container = None


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
        self.stress_fields_structure = [
            ("漏极应力电压 (V):", "VD_stress_val", config_settings.STRESS_DEFAULT_VD_STRESS),
            ("栅极应力电压 (V):", "VG_stress_val", config_settings.STRESS_DEFAULT_VG_STRESS),
            ("源极应力电压 (V):", "VS_stress_val", config_settings.STRESS_DEFAULT_VS_STRESS),
            ("应力持续时间 (s):", "stress_duration_val", config_settings.STRESS_DEFAULT_DURATION),
            ("应力测量间隔 (s):", "stress_measure_interval_val", config_settings.STRESS_DEFAULT_MEASURE_INTERVAL),
            ("初始稳定延时 (s):", "initial_settling_delay_stress", config_settings.STRESS_DEFAULT_INITIAL_SETTLING_DELAY),
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
        self.stress_params_vars = {}

        self.gt_enable_backward = tk.BooleanVar(value=True)
        self.diode_enable_backward = tk.BooleanVar(value=True)
        
        self.post_stress_char_method = tk.StringVar(value="栅转移特性 (Gate Transfer)")

        self._create_main_layout()

        self.live_plot_handler = live_plot_module.LivePlotHandler(self, self.right_pane_frame_for_live_plot)
        self.measurement_handler = measurement_handler.MeasurementHandler(self, self.live_plot_handler)
        self.history_tab_handler_instance = history_tab_module.HistoryTabHandler(self, self.history_tab)

        gui_utils.toggle_device_parameter_input(self)
        gui_utils.set_status(self, "准备就绪 (Ready)")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self._set_update_file_name_base()
        self.refresh_recent_files_list() 


    def _on_closing(self):
        # Original closing logic (without sash saving)
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
        self._create_recent_files_preview_frame() 
        
        self.notebook_frame_container = ttk.Frame(self.left_vertical_pane, padding=(0,0)) 
        self._create_notebook(self.notebook_frame_container) 

        self.right_pane_frame_for_live_plot = ttk.Frame(self.main_horizontal_pane, padding=(0,0))
        self.main_horizontal_pane.add(self.right_pane_frame_for_live_plot, weight=2)
        
        self._on_tab_changed() 
        self.root.after_idle(lambda: self.main_horizontal_pane.sashpos(0, 420)) 


    def _create_file_device_settings_frame(self):
        self.common_settings_frame = ttk.LabelFrame(self.left_vertical_pane, text="通用设置 (Common Settings)",
                                                    padding=(self.style_config['padx'], self.style_config['pady']))

        dir_frame = ttk.Frame(self.common_settings_frame)
        dir_frame.pack(fill=tk.X, expand=True, pady=(4,2))
        dir_frame.columnconfigure(1, weight=9)
        ttk.Label(dir_frame, text="输出路径 (Output Path):", font=self.style_config['font_label']).grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.entry_output_dir = ttk.Entry(dir_frame, textvariable=self.output_dir)
        self.entry_output_dir.grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(dir_frame, text="浏览... (Browse...)", command=lambda: gui_utils.browse_directory(self, self.refresh_recent_files_list), width=12).grid(row=0, column=2, sticky=tk.E, padx=(5,0))

        # --- Auto Device ID Generation Frame ---
        auto_id_outer_frame = ttk.LabelFrame(self.common_settings_frame, text="自动器件ID生成 (Auto Device ID Generation)", padding=(self.style_config['padx']-2, self.style_config['pady']-2))
        auto_id_outer_frame.pack(fill=tk.X, expand=True, pady=(6,4), padx=2)
        
        # Frame for ID inputs on one line
        auto_id_input_frame = ttk.Frame(auto_id_outer_frame)
        auto_id_input_frame.pack(fill=tk.X, expand=True)

        # Layout for Auto ID inputs on a single row
        prefix_label = ttk.Label(auto_id_input_frame, text="项目前缀:", font=self.style_config['font_label'])
        prefix_label.grid(row=0, column=0, sticky=tk.W, padx=(5,1), pady=2)
        prefix_entry = ttk.Entry(auto_id_input_frame, textvariable=self.project_prefix, width=12) # Adjusted width
        prefix_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0,3), pady=2)

        cell_label = ttk.Label(auto_id_input_frame, text="单元:", font=self.style_config['font_label'])
        cell_label.grid(row=0, column=2, sticky=tk.W, padx=(3,1), pady=2)
        cell_entry = ttk.Entry(auto_id_input_frame, textvariable=self.current_cell_id, width=2) # Adjusted width
        cell_entry.grid(row=0, column=3, sticky=tk.W, padx=(0,3), pady=2)

        row_label = ttk.Label(auto_id_input_frame, text="行:", font=self.style_config['font_label'])
        row_label.grid(row=0, column=4, sticky=tk.W, padx=(3,1), pady=2)
        row_entry = ttk.Entry(auto_id_input_frame, textvariable=self.current_row_id, width=2) # Adjusted width
        row_entry.grid(row=0, column=5, sticky=tk.W, padx=(0,3), pady=2)

        col_label = ttk.Label(auto_id_input_frame, text="列:", font=self.style_config['font_label'])
        col_label.grid(row=0, column=6, sticky=tk.W, padx=(3,1), pady=2)
        col_entry = ttk.Entry(auto_id_input_frame, textvariable=self.current_col_id, width=2) # Adjusted width
        col_entry.grid(row=0, column=7, sticky=tk.W, padx=(0,5), pady=2)
        
        auto_id_input_frame.columnconfigure(1, weight=1) # Allow prefix entry to expand a bit more

        # Frame for Auto ID buttons (remains below the input line)
        auto_id_button_frame = ttk.Frame(auto_id_outer_frame)
        auto_id_button_frame.pack(fill=tk.X, expand=True, pady=(5,0)) 
        
        set_name_button = ttk.Button(auto_id_button_frame, text="设置/更新文件名前缀", command=self._set_update_file_name_base, width=20)
        set_name_button.pack(side=tk.LEFT, padx=(5,5), expand=True, fill=tk.X)
        
        increment_button = ttk.Button(auto_id_button_frame, text="递增至下一器件", command=self._increment_device_id, width=20)
        increment_button.pack(side=tk.LEFT, padx=(0,5), expand=True, fill=tk.X)
        
        # --- File Name (Base) ---
        file_frame = ttk.Frame(self.common_settings_frame)
        file_frame.pack(fill=tk.X, expand=True, pady=(2,4))
        file_frame.columnconfigure(1, weight=1)
        ttk.Label(file_frame, text="文件名 (File Name):", font=self.style_config['font_label']).grid(row=0, column=0, sticky=tk.W, padx=(0,5))
        self.entry_file_name_base = ttk.Entry(file_frame, textvariable=self.file_name_base) 
        self.entry_file_name_base.grid(row=0, column=1, sticky=tk.EW, padx=5)

        # --- Device Parameters ---
        device_frame = ttk.LabelFrame(self.common_settings_frame, text="器件参数 (Device Parameters - for Current Density)")
        device_frame.pack(fill=tk.X, expand=True, padx=5, pady=(8,4), ipady=5)
        
        device_param_input_frame = ttk.Frame(device_frame)
        device_param_input_frame.pack(fill=tk.X, expand=True, pady=(2,2))

        # Layout for Device Parameters on a single conceptual line (Lateral options then Vertical options)
        self.radio_lateral = ttk.Radiobutton(device_param_input_frame, text="横向", variable=self.device_type, value="lateral", command=lambda: gui_utils.toggle_device_parameter_input(self))
        self.radio_lateral.grid(row=0, column=0, sticky=tk.W, padx=(10,1))
        self.lbl_channel_width = ttk.Label(device_param_input_frame, text="宽度W(µm):", font=self.style_config['font_label'])
        self.lbl_channel_width.grid(row=0, column=1, sticky=tk.W, padx=(0,1))
        self.entry_channel_width = ttk.Entry(device_param_input_frame, textvariable=self.channel_width_um, width=8) # Adjusted width
        self.entry_channel_width.grid(row=0, column=2, sticky=tk.W, padx=(0,10))

        # Separator or just rely on padx for the next radio button
        separator_label = ttk.Label(device_param_input_frame, text="  |  ") # Optional visual separator
        separator_label.grid(row=0, column=3, sticky=tk.W, padx=(5,5))


        self.radio_vertical = ttk.Radiobutton(device_param_input_frame, text="纵向", variable=self.device_type, value="vertical", command=lambda: gui_utils.toggle_device_parameter_input(self))
        self.radio_vertical.grid(row=0, column=4, sticky=tk.W, padx=(10,1)) 
        self.lbl_area = ttk.Label(device_param_input_frame, text="面积Area(µm²):", font=self.style_config['font_label'])
        self.lbl_area.grid(row=0, column=5, sticky=tk.W, padx=(0,1))
        self.entry_area = ttk.Entry(device_param_input_frame, textvariable=self.area_um2, width=8) # Adjusted width
        self.entry_area.grid(row=0, column=6, sticky=tk.W, padx=(0,10))

        device_param_input_frame.columnconfigure(2, weight=1) 
        device_param_input_frame.columnconfigure(6, weight=1) 


    def _create_recent_files_preview_frame(self):
        self.recent_files_frame_container = ttk.LabelFrame(self.left_vertical_pane, text="近期文件预览 (Recent Files Preview)",
                                               padding=(self.style_config['padx']-2, self.style_config['pady']-2))

        listbox_frame = ttk.Frame(self.recent_files_frame_container)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        listbox_frame.columnconfigure(0, weight=1)
        listbox_frame.rowconfigure(0, weight=1)

        self.recent_files_listbox = tk.Listbox(listbox_frame, height=5, exportselection=False) 
        self.recent_files_listbox.grid(row=0, column=0, sticky="nsew")
        
        recent_files_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.recent_files_listbox.yview)
        recent_files_scrollbar.grid(row=0, column=1, sticky="ns")
        self.recent_files_listbox.config(yscrollcommand=recent_files_scrollbar.set)

        refresh_button = ttk.Button(self.recent_files_frame_container, text="刷新列表 (Refresh List)", command=self.refresh_recent_files_list)
        refresh_button.pack(fill=tk.X, pady=(0,2), padx=2)


    def refresh_recent_files_list(self):
        if not self.recent_files_listbox:
            return
        self.recent_files_listbox.delete(0, tk.END)
        output_dir = self.output_dir.get()

        if not os.path.isdir(output_dir):
            self.recent_files_listbox.insert(tk.END, "输出目录无效或未设置。")
            return
        try:
            files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
            files.sort(key=lambda name: os.path.getmtime(os.path.join(output_dir, name)), reverse=True)
            
            if files:
                for f_name in files[:20]: 
                    self.recent_files_listbox.insert(tk.END, f_name)
            else:
                self.recent_files_listbox.insert(tk.END, "未找到CSV文件。")
        except Exception as e:
            self.recent_files_listbox.insert(tk.END, f"读取文件列表时出错: {e}")
            print(f"Error refreshing recent files list: {e}", file=sys.stderr)


    def _set_update_file_name_base(self):
        prefix = self.project_prefix.get().strip().replace(" ", "_")
        cell = self.current_cell_id.get().strip()
        row = self.current_row_id.get().strip().upper()
        col = self.current_col_id.get().strip()

        if not cell or not row or not col:
            messagebox.showerror("输入错误", "单元、行、列ID不能为空。")
            gui_utils.set_status(self, "单元、行、列ID不能为空 (Cell, Row, Col ID cannot be empty)", error=True)
            return

        try:
            col_int = int(col)
            cell_int = int(cell)
            
            if not (1 <= col_int <= self.MAX_COL):
                 messagebox.showwarning("输入警告", f"列号 {col} 超出当前配置的最大列数 ({self.MAX_COL})。")
            if row not in self.ROW_IDS:
                 messagebox.showwarning("输入警告", f"行号 {row} 不在当前配置的行ID列表 ({', '.join(self.ROW_IDS)}) 中。")
            if not (1 <= cell_int <= self.MAX_CELL):
                 messagebox.showwarning("输入警告", f"单元号 {cell} 超出当前配置的最大单元数 ({self.MAX_CELL})。")

        except ValueError:
            messagebox.showerror("输入错误", "单元和列号必须是数字。")
            gui_utils.set_status(self, "单元和列号必须是数字 (Cell and Column must be numbers)", error=True)
            return
        
        col_formatted = f"{col_int:02d}" 

        base_name_parts = []
        if prefix:
            base_name_parts.append(prefix)
        
        device_part = f"C{cell}_{row}{col_formatted}"
        base_name_parts.append(device_part)
        
        constructed_name = "_".join(base_name_parts)
        self.file_name_base.set(constructed_name)
        gui_utils.set_status(self, f"文件名前缀已更新为: {constructed_name}")

    def _increment_device_id(self):
        try:
            current_c = int(self.current_cell_id.get())
            current_r_str = self.current_row_id.get().upper()
            current_col = int(self.current_col_id.get())

            current_col += 1

            if current_col > self.MAX_COL:
                current_col = 1 
                try:
                    if not self.ROW_IDS: 
                        messagebox.showerror("配置错误", "行ID列表 (ROW_IDS) 为空。")
                        return
                    current_r_idx = self.ROW_IDS.index(current_r_str)
                    current_r_idx += 1
                    if current_r_idx >= len(self.ROW_IDS):
                        current_r_idx = 0 
                        current_c += 1
                        if current_c > self.MAX_CELL:
                            current_c = 1 
                            messagebox.showinfo("提示", "已完成所有单元的循环，单元ID已重置。")
                    self.current_row_id.set(self.ROW_IDS[current_r_idx])
                except ValueError:
                    messagebox.showerror("错误", f"当前行 '{current_r_str}' 无效。请使用预定义行: {', '.join(self.ROW_IDS)}")
                    return
            
            self.current_col_id.set(str(current_col))
            self.current_cell_id.set(str(current_c))
            
            self._set_update_file_name_base()
            gui_utils.set_status(self, f"器件ID已递增至: C{self.current_cell_id.get()}_{self.current_row_id.get()}{int(self.current_col_id.get()):02d}")

        except ValueError:
            messagebox.showerror("错误", "递增器件ID时，单元或列的值无效。请输入数字。")
            gui_utils.set_status(self, "递增器件ID时出错 (Error incrementing device ID)", error=True)
        except Exception as e:
            messagebox.showerror("错误", f"递增器件ID时发生未知错误: {e}")
            gui_utils.set_status(self, f"递增器件ID时发生未知错误: {e}", error=True)


    def _on_tab_changed(self, event=None):
        if not all(hasattr(self, attr) for attr in ['notebook', 'common_settings_frame', 
                                                    'recent_files_frame_container', 
                                                    'left_vertical_pane', 'main_horizontal_pane', 
                                                    'right_pane_frame_for_live_plot', 'notebook_frame_container']):
            return
        try:
            selected_tab_widget_id = self.notebook.select()
            selected_tab_text = self.notebook.tab(selected_tab_widget_id, "text") if selected_tab_widget_id else ""
        except tk.TclError: 
            selected_tab_text = ""
        
        is_history_tab = (selected_tab_text == '历史记录 (History)')

        if self.common_settings_frame and self.common_settings_frame.winfo_exists() and self.common_settings_frame.winfo_ismapped():
            try: self.left_vertical_pane.forget(self.common_settings_frame)
            except tk.TclError: pass
        if self.recent_files_frame_container and self.recent_files_frame_container.winfo_exists() and self.recent_files_frame_container.winfo_ismapped():
            try: self.left_vertical_pane.forget(self.recent_files_frame_container)
            except tk.TclError: pass
        if self.notebook_frame_container and self.notebook_frame_container.winfo_exists() and self.notebook_frame_container.winfo_ismapped():
            try: self.left_vertical_pane.forget(self.notebook_frame_container)
            except tk.TclError: pass
        
        if is_history_tab:
            if self.notebook_frame_container and self.notebook_frame_container.winfo_exists():
                current_panes = []
                try: current_panes = self.left_vertical_pane.panes()
                except tk.TclError: pass
                if str(self.notebook_frame_container) not in current_panes:
                    self.left_vertical_pane.add(self.notebook_frame_container, weight=1) 
        else: 
            if self.common_settings_frame and self.common_settings_frame.winfo_exists():
                current_panes = []
                try: current_panes = self.left_vertical_pane.panes()
                except tk.TclError: pass
                if str(self.common_settings_frame) not in current_panes:
                    self.left_vertical_pane.add(self.common_settings_frame, weight=self.COMMON_SETTINGS_PANE_WEIGHT)
            
            if self.recent_files_frame_container and self.recent_files_frame_container.winfo_exists():
                current_panes = []
                try: current_panes = self.left_vertical_pane.panes()
                except tk.TclError: pass
                if str(self.recent_files_frame_container) not in current_panes:
                    self.left_vertical_pane.add(self.recent_files_frame_container, weight=self.RECENT_FILES_PANE_WEIGHT)

            if self.notebook_frame_container and self.notebook_frame_container.winfo_exists():
                current_panes = []
                try: current_panes = self.left_vertical_pane.panes()
                except tk.TclError: pass
                if str(self.notebook_frame_container) not in current_panes:
                    self.left_vertical_pane.add(self.notebook_frame_container, weight=self.NOTEBOOK_PANE_WEIGHT)
        
        current_main_panes_paths = []
        try: current_main_panes_paths = list(self.main_horizontal_pane.panes())
        except tk.TclError: pass

        current_main_panes_widgets_str = []
        for pane_path in current_main_panes_paths:
            try: current_main_panes_widgets_str.append(str(self.root.nametowidget(pane_path)))
            except tk.TclError: pass

        is_right_pane_currently_visible = (self.right_pane_frame_for_live_plot and 
                                           self.right_pane_frame_for_live_plot.winfo_exists() and 
                                           str(self.right_pane_frame_for_live_plot) in current_main_panes_widgets_str)
        
        if is_history_tab:
            if is_right_pane_currently_visible: 
                try: self.main_horizontal_pane.forget(self.right_pane_frame_for_live_plot)
                except tk.TclError: pass
        else: 
            if not is_right_pane_currently_visible and self.right_pane_frame_for_live_plot and self.right_pane_frame_for_live_plot.winfo_exists():
                is_left_pane_visible = (self.left_vertical_pane and 
                                        self.left_vertical_pane.winfo_exists() and 
                                        str(self.left_vertical_pane) in current_main_panes_widgets_str)
                if not is_left_pane_visible and self.left_vertical_pane and self.left_vertical_pane.winfo_exists():
                     self.main_horizontal_pane.add(self.left_vertical_pane, weight=1) 
                self.main_horizontal_pane.add(self.right_pane_frame_for_live_plot, weight=2)


    def _create_notebook(self, parent_frame): 
        self.notebook = ttk.Notebook(parent_frame) 
        self.notebook.pack(expand=True, fill='both', padx=0, pady=0) 
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        self.gate_transfer_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.output_char_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.breakdown_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.diode_tab = ttk.Frame(self.notebook, padding=(0,0))
        self.stress_tab = ttk.Frame(self.notebook, padding=(0,0)) 
        self.history_tab = ttk.Frame(self.notebook) 
        
        for tab_content_frame in [self.gate_transfer_tab, self.output_char_tab, self.breakdown_tab, self.diode_tab, self.stress_tab, self.history_tab]:
            tab_content_frame.columnconfigure(0, weight=1); tab_content_frame.rowconfigure(0, weight=1)
            
        self.notebook.add(self.gate_transfer_tab, text='栅转移特性 (Gate Transfer)')
        self.notebook.add(self.output_char_tab, text='输出特性 (Output Characteristics)')
        self.notebook.add(self.stress_tab, text='应力测试 (Stress Test)')
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

        # Stress Test Tab
        frame_st = self.stress_tab
        ttk.Label(frame_st, text="应力测试参数", font=self.style_config['font_title']).pack(anchor=tk.W, pady=(8,2), fill=tk.X, padx=self.style_config['padx']-2)
        stress_voltage_fields = [f for f in self.stress_fields_structure if f[1] in ["VD_stress_val", "VG_stress_val", "VS_stress_val"]]
        stress_time_fields = [f for f in self.stress_fields_structure if f[1] in ["stress_duration_val", "stress_measure_interval_val", "initial_settling_delay_stress"]]
        stress_limit_nplc_fields = [f for f in self.stress_fields_structure if f[1] not in ["VD_stress_val", "VG_stress_val", "VS_stress_val", "stress_duration_val", "stress_measure_interval_val", "initial_settling_delay_stress"]]
        gui_utils.create_param_frame(self, frame_st, "应力电压设置", stress_voltage_fields, self.stress_params_vars, columns=1)
        gui_utils.create_param_frame(self, frame_st, "应力时间与延时设置", stress_time_fields, self.stress_params_vars, columns=1)
        gui_utils.create_param_frame(self, frame_st, "电流限制和NPLC设置", stress_limit_nplc_fields, self.stress_params_vars, columns=2)
        post_stress_frame = ttk.LabelFrame(frame_st, text="应力后特性表征 (Post-Stress Characterization)", padding=(self.style_config['padx']-4, self.style_config['pady']-4))
        post_stress_frame.pack(fill=tk.X, expand=True, padx=self.style_config['padx']-2, pady=(10,2), ipady=5)
        ttk.Label(post_stress_frame, text="选择表征方法:", font=self.style_config['font_label']).pack(side=tk.LEFT, padx=(5,5), pady=5)
        char_methods = ["无 (None)", "栅转移特性 (Gate Transfer)", "输出特性 (Output Characteristics)"]
        self.post_stress_char_combobox = ttk.Combobox(post_stress_frame, textvariable=self.post_stress_char_method, values=char_methods, state="readonly", width=30)
        self.post_stress_char_combobox.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.post_stress_char_combobox.set("栅转移特性 (Gate Transfer)")
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

    if hasattr(gui, 'refresh_recent_files_list'): 
        gui.refresh_recent_files_list()

    if hasattr(gui, 'live_plot_handler') and gui.live_plot_handler and \
       hasattr(gui.live_plot_handler, 'live_plot_canvas') and gui.live_plot_handler.live_plot_canvas is None:
        print("实时绘图区域未成功初始化。", file=sys.stderr)
    
    app_root.mainloop()
