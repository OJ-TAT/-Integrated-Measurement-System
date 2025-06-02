# history_tab_module.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import re
from datetime import datetime
import traceback
import sys # For sys.stderr

import instrument_utils
import gui_utils
import plotting_utils # For displaying errors on plot
# Import measurement classes if needed for recalculating parameters
from gate_transfer_module import GateTransferMeasurement
# from output_module import OutputMeasurement # Example, uncomment if needed
# from breakdown_module import BreakdownMeasurement # Example, uncomment if needed
# from diode_module import DiodeMeasurement # Example, uncomment if needed
import config_settings # For default NPLC, etc., if needed for recalculation config

# A more extensive default color cycle for history plots
DEFAULT_COLOR_CYCLE = [
    "#0011ff", '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '#ffbb78',
    '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7',
    '#dbdb8d', '#9edae5', '#393b79', '#637939', '#8c6d31', '#843c39',
    '#7b4173', '#5254a3', '#6b6ecf', '#9c9ede'
]

class HistoryTabHandler:
    def __init__(self, app_instance, tab_frame):
        self.app = app_instance
        self.tab_frame = tab_frame
        self.style = gui_utils.get_style()

        self.history_listbox = None
        self.history_plot_figure = None
        self.history_plot_canvas = None
        self.history_plot_toolbar = None
        self.history_metadata_text = None
        
        self.history_use_log_y = tk.BooleanVar(value=False)
        self.history_y_auto_scale = tk.BooleanVar(value=True)
        self.history_y_min_var = tk.StringVar(value="")
        self.history_y_max_var = tk.StringVar(value="")
        
        self.history_annotation_managers = []
        self.history_crosshair_features = [] 
        self.history_plot_overlay_legend_frame = None
        self.history_overlay_plot_data = [] 

        self.key_label_color_assignments = {} 
        self.color_cycle = DEFAULT_COLOR_CYCLE 

        self._populate_history_tab()

    def _populate_history_tab(self):
        history_main_h_pane = ttk.PanedWindow(self.tab_frame, orient=tk.HORIZONTAL)
        history_main_h_pane.pack(fill=tk.BOTH, expand=True)

        left_history_pane_container = ttk.Frame(history_main_h_pane, padding=(0,0,5,0))
        history_main_h_pane.add(left_history_pane_container, weight=1) 
        left_history_v_pane = ttk.PanedWindow(left_history_pane_container, orient=tk.VERTICAL)
        left_history_v_pane.pack(fill=tk.BOTH, expand=True)

        list_area_frame = ttk.LabelFrame(left_history_v_pane, text="文件列表 (File List)")
        list_area_frame.columnconfigure(0, weight=1)
        list_area_frame.rowconfigure(0, weight=1) 
        left_history_v_pane.add(list_area_frame, weight=3) 

        self.history_listbox = tk.Listbox(list_area_frame, selectmode=tk.EXTENDED, exportselection=False)
        self.history_listbox.grid(row=0, column=0, sticky="nsew", pady=(0,5))
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_file_select)
        self.history_listbox.bind("<Double-1>", lambda event: self._plot_selected_history_files_action())
        history_scrollbar = ttk.Scrollbar(list_area_frame, orient=tk.VERTICAL, command=self.history_listbox.yview)
        history_scrollbar.grid(row=0, column=1, sticky="ns", pady=(0,5))
        self.history_listbox.config(yscrollcommand=history_scrollbar.set)

        controls_area_frame = ttk.Frame(left_history_v_pane)
        left_history_v_pane.add(controls_area_frame, weight=2) 

        plot_options_frame = ttk.LabelFrame(controls_area_frame, text="绘图选项 (Plot Options)")
        plot_options_frame.pack(fill=tk.X, expand=False, pady=(5,0), padx=2)
        self.history_log_y_check = ttk.Checkbutton(plot_options_frame, text="对数Y轴 (Log Y)", variable=self.history_use_log_y, command=self._plot_selected_history_files_action_if_selected)
        self.history_log_y_check.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.history_y_auto_scale_check = ttk.Checkbutton(plot_options_frame, text="Y轴自动缩放 (Auto Y-Scale)", variable=self.history_y_auto_scale, command=self._toggle_history_y_scale_entries)
        self.history_y_auto_scale_check.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self.history_y_min_label = ttk.Label(plot_options_frame, text="Y最小 (Y Min):", font=self.style['font_label'])
        self.history_y_min_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.history_y_min_entry = ttk.Entry(plot_options_frame, textvariable=self.history_y_min_var, width=10, state=tk.DISABLED)
        self.history_y_min_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        self.history_y_max_label = ttk.Label(plot_options_frame, text="Y最大 (Y Max):", font=self.style['font_label'])
        self.history_y_max_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.history_y_max_entry = ttk.Entry(plot_options_frame, textvariable=self.history_y_max_var, width=10, state=tk.DISABLED)
        self.history_y_max_entry.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        self.history_y_min_entry.bind("<KeyRelease>", lambda event: self._plot_selected_history_files_action_if_selected_and_manual_scale())
        self.history_y_max_entry.bind("<KeyRelease>", lambda event: self._plot_selected_history_files_action_if_selected_and_manual_scale())
        
        self.history_plot_overlay_legend_frame = ttk.LabelFrame(controls_area_frame, text="系列控制 (Overlay Series Control)")
        
        button_frame_row1 = ttk.Frame(controls_area_frame)
        button_frame_row1.pack(fill=tk.X, expand=False, pady=(5,2))
        button_frame_row1.columnconfigure(0, weight=1); button_frame_row1.columnconfigure(1, weight=1)
        button_frame_row1.columnconfigure(2, weight=1); button_frame_row1.columnconfigure(3, weight=1)
        ttk.Button(button_frame_row1, text="刷新列表 (Refresh)", command=self.refresh_file_list).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(button_frame_row1, text="绘制选中项 (Plot)", command=self._plot_selected_history_files_action).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(button_frame_row1, text="重命名文件 (Rename)", command=self._rename_selected_history_file).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(button_frame_row1, text="合并选中系列到CSV (Merge Series)", command=self._merge_selected_history_to_csv).grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        
        button_frame_row2 = ttk.Frame(controls_area_frame)
        button_frame_row2.pack(fill=tk.X, expand=False, pady=(2,0))
        button_frame_row2.columnconfigure(0, weight=1)
        ttk.Button(button_frame_row2, text="提取选中栅转移参数 (Extract GT Params)", command=self._batch_extract_gt_params).grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        right_history_pane_container = ttk.Frame(history_main_h_pane, padding=(5,0,0,0))
        history_main_h_pane.add(right_history_pane_container, weight=3) 
        right_history_v_pane = ttk.PanedWindow(right_history_pane_container, orient=tk.VERTICAL)
        right_history_v_pane.pack(fill=tk.BOTH, expand=True)

        plot_area_frame = ttk.LabelFrame(right_history_v_pane, text="绘图预览 (Plot Preview)")
        plot_area_frame.rowconfigure(0, weight=1); plot_area_frame.columnconfigure(0, weight=1)
        right_history_v_pane.add(plot_area_frame, weight=3)

        try:
            self.history_plot_figure = plt.Figure(figsize=(6,5), dpi=100)
            self.history_plot_canvas = FigureCanvasTkAgg(self.history_plot_figure, master=plot_area_frame)
            self.history_plot_canvas_widget = self.history_plot_canvas.get_tk_widget()
            self.history_plot_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.history_plot_toolbar = NavigationToolbar2Tk(self.history_plot_canvas, plot_area_frame, pack_toolbar=False)
            self.history_plot_toolbar.update(); self.history_plot_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            self._clear_history_plot_area()
        except Exception as e:
            print(f"关键错误: 历史记录绘图区域初始化失败: {e}\n{traceback.format_exc()}", file=sys.stderr)
            error_label = ttk.Label(plot_area_frame, text=f"绘图区域初始化失败:\n{e}", foreground="red")
            error_label.pack(padx=10, pady=10)

        metadata_frame = ttk.LabelFrame(right_history_v_pane, text="文件元数据 (File Metadata)")
        metadata_frame.rowconfigure(0, weight=1); metadata_frame.columnconfigure(0, weight=1)
        right_history_v_pane.add(metadata_frame, weight=1)
        self.history_metadata_text = tk.Text(metadata_frame, wrap=tk.WORD, height=6, state=tk.DISABLED, font=self.style['font_label'])
        meta_scroll = ttk.Scrollbar(metadata_frame, command=self.history_metadata_text.yview)
        self.history_metadata_text.config(yscrollcommand=meta_scroll.set)
        self.history_metadata_text.grid(row=0, column=0, sticky="nsew")
        meta_scroll.grid(row=0, column=1, sticky="ns")

        self.refresh_file_list() 
        self._toggle_history_y_scale_entries()
        self.app.root.after_idle(lambda: history_main_h_pane.sashpos(0, 350))


    def _on_history_file_select(self, event=None):
        selected_indices = self.history_listbox.curselection()
        if self.history_plot_overlay_legend_frame:
            for widget in self.history_plot_overlay_legend_frame.winfo_children():
                widget.destroy()
            if self.history_plot_overlay_legend_frame.winfo_ismapped():
                self.history_plot_overlay_legend_frame.pack_forget()

        if not self.history_metadata_text: return
        self.history_metadata_text.config(state=tk.NORMAL)
        self.history_metadata_text.delete("1.0", tk.END)

        if len(selected_indices) == 1:
            filename = self.history_listbox.get(selected_indices[0])
            csv_path = os.path.join(self.app.output_dir.get(), filename)
            try:
                metadata_str = ""
                with open(csv_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('#'):
                            metadata_str += line[1:].strip() + "\n"
                        else: break 
                if metadata_str:
                    self.history_metadata_text.insert(tk.END, metadata_str)
                else:
                    self.history_metadata_text.insert(tk.END, "未找到元数据。(No metadata found in comments.)")
            except Exception as e:
                print(f"读取元数据时出错 ({filename}): {e}", file=sys.stderr)
                self.history_metadata_text.insert(tk.END, f"读取元数据失败。(Failed to read metadata.)\nError: {e}")
        elif len(selected_indices) > 1:
            self.history_metadata_text.insert(tk.END, "选择了多个文件。元数据预览仅适用于单个文件。\n(Multiple files selected. Metadata preview for single file only.)")
        else:
             self.history_metadata_text.insert(tk.END, "请选择一个文件以查看元数据。\n(Select a file to view its metadata.)")
        self.history_metadata_text.config(state=tk.DISABLED)

    def _prepare_data_package_for_file(self, csv_path, filename):
        measurement_type = self._infer_measurement_type_from_filename(filename)
        if not measurement_type:
            messagebox.showerror("错误", f"无法从文件名推断测量类型: {filename}")
            return None
        try:
            key_mappings = {
                'Time': 'Time',
                'Vg_actual': 'Vg_actual_for_data', 'Vg_final': 'Vg_actual_for_data',
                'Vd_read': 'Vd_read', 'VDrain_read': 'Vd_read',
                'Id': 'Id', 'IDrain': 'Id',
                'Ig': 'Ig', 'IGate': 'Ig',
                'Is': 'Is', 'ISource': 'Is',
                'Jd': 'Jd', 'Jg': 'Jg', 'Js': 'Js',
                'gm': 'gm', 'SS': 'SS',
                'VAnode_set': 'anode_voltage_set', 'VAnode_read': 'anode_voltage_read',
                'IAnode': 'anode_current', 'ICathode_buffer': 'cathode_current'
            }
            df = pd.read_csv(csv_path, comment='#')
            if df.empty:
                messagebox.showwarning("警告", f"文件 {filename} 为空或仅包含注释。")
                return None
            metadata = {}
            with open(csv_path, 'r', encoding='utf-8') as f_header:
                for line in f_header:
                    if line.startswith('#'):
                        line_content = line[1:].strip()
                        if ":" in line_content:
                            key, value = line_content.split(":", 1)
                            metadata[key.strip()] = value.strip()
                        else:
                            if "General Comments" not in metadata: metadata["General Comments"] = []
                            metadata["General Comments"].append(line_content)
                    else: break
            
            processed_data_std_keys = {}
            for col_original_case in df.columns:
                col_base = col_original_case.split('(')[0].strip()
                std_key = key_mappings.get(col_base, col_base)
                try:
                    processed_data_std_keys[std_key] = df[col_original_case].values.astype(float)
                except ValueError: 
                    print(f"Warning: Could not convert column '{col_original_case}' to float in {filename}. Using NaN for non-numeric values.", file=sys.stderr)
                    processed_data_std_keys[std_key] = pd.to_numeric(df[col_original_case], errors='coerce').values

            essential_plot_keys = [
                'Vg_actual_for_data', 'Vd_read', 'Id', 'Ig', 'Is', 'gm', 'SS',
                'anode_voltage_read', 'anode_voltage_set', 'anode_current', 'cathode_current',
                'Jd', 'Jg', 'Js', 'Time'
            ]
            for k in essential_plot_keys:
                if k not in processed_data_std_keys:
                    processed_data_std_keys[k] = np.array([])

            return {
                "processed_data": processed_data_std_keys, "csv_file_path": csv_path,
                "png_file_path": os.path.splitext(csv_path)[0] + instrument_utils.get_plot_suffix_for_measurement(instrument_utils.get_short_measurement_type(filename)),
                "measurement_type_name": measurement_type, "status": "success_data_ready",
                "metadata_from_csv": metadata, "filename_short": filename
            }
        except pd.errors.EmptyDataError:
            messagebox.showerror("错误", f"文件为空或格式不正确: {filename}")
            return None
        except Exception as e:
            messagebox.showerror("数据加载错误", f"加载文件时出错 {filename}: {e}\n详细信息请查看控制台。")
            print(f"Error loading data for {filename}: {e}\n{traceback.format_exc()}", file=sys.stderr)
            return None

    def _get_style_for_series(self, key_label, measurement_type):
        style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': 'purple'}
        if measurement_type == "Gate Transfer":
            if key_label == 'Id': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': "#0400ff"} 
            elif key_label == 'Ig': style = {'linestyle': '--', 'marker': 'None', 'ms': 3, 'base_color': "#ff0000"} 
            elif key_label == 'Is': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': "#00ff00"} 
            elif key_label == 'gm': style = {'linestyle': ':', 'marker': 'None', 'ms': 3, 'base_color': '#ff7f0e'} 
        elif measurement_type == "Output Characteristics":
            if key_label == 'Id': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': '#0400ff'}
        elif measurement_type == "Breakdown Characteristics":
            if key_label == 'Id': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': '#0400ff'}
            elif key_label == 'Is': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': '#00ff00'}
            elif key_label == 'Ig': style = {'linestyle': '--', 'marker': 'None', 'ms': 3, 'base_color': '#ff0000'}
        elif measurement_type == "Diode Characterization":
            if key_label == 'anode_current': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': '#0400ff'}
            elif key_label == 'cathode_current': style = {'linestyle': '-', 'marker': 'o', 'ms': 3, 'base_color': '#ff0000'}
        return style

    def _plot_selected_history_files_action(self):
        selected_indices = self.history_listbox.curselection()
        if not selected_indices:
            self._clear_history_plot_area("请从列表中选择文件进行绘制。")
            return

        if self.history_plot_figure is None or self.history_plot_canvas is None:
            messagebox.showerror("错误", "历史记录绘图区域未正确初始化。")
            return

        if self.history_plot_overlay_legend_frame:
            for widget in self.history_plot_overlay_legend_frame.winfo_children(): widget.destroy()
        self.history_overlay_plot_data.clear()
        self.key_label_color_assignments.clear()

        output_char_file_color_idx = 0 # Separate color index for output characteristic files

        for list_idx_actual in selected_indices:
            filename = self.history_listbox.get(list_idx_actual)
            csv_path = os.path.join(self.app.output_dir.get(), filename)
            data_package = self._prepare_data_package_for_file(csv_path, filename)
            if not data_package: continue
            
            processed_data = data_package["processed_data"]
            measurement_type = data_package["measurement_type_name"]
            
            current_x_data_series = np.array([])
            if measurement_type == "Gate Transfer": current_x_data_series = processed_data.get('Vg_actual_for_data', np.array([]))
            elif measurement_type == "Output Characteristics": pass 
            elif measurement_type == "Breakdown Characteristics": current_x_data_series = processed_data.get('Vd_read', np.array([]))
            elif measurement_type == "Diode Characterization": 
                current_x_data_series = processed_data.get('anode_voltage_read', np.array([]))
                if not (current_x_data_series.size > 0 and not np.all(np.isnan(current_x_data_series))):
                    current_x_data_series = processed_data.get('anode_voltage_set', np.array([]))

            if measurement_type == "Output Characteristics":
                unique_vgs_output_all = processed_data.get('Vg_actual_for_data', np.array([]))
                if unique_vgs_output_all.size == 0: continue
                unique_vgs_output = np.unique(unique_vgs_output_all[~np.isnan(unique_vgs_output_all)])
                
                file_base_color = self.color_cycle[output_char_file_color_idx % len(self.color_cycle)]
                output_char_file_color_idx += 1

                for vg_idx, vg_val_output in enumerate(unique_vgs_output):
                    mask_output = np.isclose(processed_data.get('Vg_actual_for_data', []), vg_val_output)
                    if not np.any(mask_output): continue
                    x_data_current_vg = processed_data.get('Vd_read', np.array([]))[mask_output]
                    plot_key, base_key_label = 'Id', 'Id' 
                    y_data_raw_current_vg = processed_data.get(plot_key, np.array([]))[mask_output]
                    
                    series_display_label = f"{plot_key} (Vg={vg_val_output:.2f}V)"
                    if x_data_current_vg.size > 0 and y_data_raw_current_vg.size == x_data_current_vg.size and np.any(~np.isnan(y_data_raw_current_vg)):
                        var = tk.BooleanVar(value=True)
                        series_full_label_for_legend = f"{os.path.splitext(filename)[0]} - {series_display_label}"
                        base_style = self._get_style_for_series(base_key_label, measurement_type)
                        
                        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
                        linestyles = ['-', '--', ':', '-.']
                        current_marker = markers[vg_idx % len(markers)]
                        current_linestyle = linestyles[(vg_idx // len(markers)) % len(linestyles)]

                        series_idx = len(self.history_overlay_plot_data)
                        self.history_overlay_plot_data.append({
                            'x': x_data_current_vg, 'y_raw': y_data_raw_current_vg, 'label': series_full_label_for_legend, 
                            'color': file_base_color, 'linestyle': current_linestyle, 'marker': current_marker,   
                            'ms': base_style['ms'], 'var': var, 'filename': filename, 'current_key': base_key_label, 
                            'measurement_type': measurement_type, 'series_index': series_idx, 
                            'vg_value': vg_val_output, 'is_current_density': False, 'is_secondary_y': False
                        })
                continue 

            current_keys_to_plot = [] 
            if measurement_type == "Gate Transfer": current_keys_to_plot = ['Id', 'Ig', 'Is', 'gm']
            elif measurement_type == "Breakdown Characteristics": current_keys_to_plot = ['Id', 'Ig', 'Is']
            elif measurement_type == "Diode Characterization": current_keys_to_plot = ['anode_current', 'cathode_current']
            
            for key_label in current_keys_to_plot:
                y_data_raw = processed_data.get(key_label)
                if y_data_raw is None or y_data_raw.size == 0 or current_x_data_series.size == 0 or y_data_raw.size != current_x_data_series.size:
                    continue
                
                var = tk.BooleanVar(value=True)
                display_key_label = key_label
                if measurement_type == "Diode Characterization":
                    if key_label == 'anode_current': display_key_label = 'IAnode'
                    elif key_label == 'cathode_current': display_key_label = 'ICathode'
                
                series_full_label_for_legend = f"{os.path.splitext(filename)[0]} - {display_key_label}"
                base_style = self._get_style_for_series(key_label, measurement_type)
                preferred_color = base_style['base_color']

                if key_label not in self.key_label_color_assignments:
                    self.key_label_color_assignments[key_label] = []

                assigned_color_for_series = None
                if preferred_color not in self.key_label_color_assignments[key_label]:
                    assigned_color_for_series = preferred_color
                else:
                    for color_from_cycle in self.color_cycle:
                        if color_from_cycle not in self.key_label_color_assignments[key_label]:
                            assigned_color_for_series = color_from_cycle
                            break
                    if assigned_color_for_series is None: 
                        assigned_color_for_series = self.color_cycle[len(self.key_label_color_assignments[key_label]) % len(self.color_cycle)]
                
                self.key_label_color_assignments[key_label].append(assigned_color_for_series)
                current_plot_color = assigned_color_for_series

                series_idx = len(self.history_overlay_plot_data)
                self.history_overlay_plot_data.append({
                    'x': current_x_data_series, 'y_raw': y_data_raw, 'label': series_full_label_for_legend, 
                    'color': current_plot_color, 'linestyle': base_style['linestyle'], 
                    'marker': base_style['marker'], 'ms': base_style['ms'],               
                    'var': var, 'filename': filename, 'current_key': key_label, 
                    'measurement_type': measurement_type, 
                    'is_secondary_y': key_label == 'gm' and measurement_type == "Gate Transfer", 
                    'series_index': series_idx, 'is_current_density': False, 'vg_value': None
                })
        
        if self.history_overlay_plot_data:
            if not self.history_plot_overlay_legend_frame.winfo_ismapped():
                 self.history_plot_overlay_legend_frame.pack(fill=tk.BOTH, expand=True, pady=(5,0), padx=2)

            legend_canvas = tk.Canvas(self.history_plot_overlay_legend_frame, borderwidth=0, highlightthickness=0)
            legend_content_frame = ttk.Frame(legend_canvas)
            legend_scrollbar = ttk.Scrollbar(self.history_plot_overlay_legend_frame, orient="vertical", command=legend_canvas.yview)
            legend_canvas.configure(yscrollcommand=legend_scrollbar.set)
            legend_scrollbar.pack(side="right", fill="y")
            legend_canvas.pack(side="left", fill="both", expand=True)
            legend_canvas.create_window((0, 0), window=legend_content_frame, anchor="nw")
            
            def on_legend_frame_configure(event, canvas=legend_canvas):
                canvas.configure(scrollregion=canvas.bbox("all"))
            legend_content_frame.bind("<Configure>", lambda e, canvas=legend_canvas: on_legend_frame_configure(e, canvas))

            for series_item in self.history_overlay_plot_data:
                cb = ttk.Checkbutton(legend_content_frame, text=series_item['label'], variable=series_item['var'],
                                     command=lambda s_idx=series_item['series_index']: self._on_series_checkbox_toggle(s_idx))
                cb.pack(anchor='w', padx=2, pady=1, fill='x')
            legend_content_frame.update_idletasks()
            on_legend_frame_configure(None, legend_canvas)
        else:
            if self.history_plot_overlay_legend_frame.winfo_ismapped():
                self.history_plot_overlay_legend_frame.pack_forget()
            self._clear_history_plot_area("选中的文件中没有可绘制的数据系列。")
            if selected_indices:
                messagebox.showinfo("提示", "选中的文件中没有可绘制的数据系列。")
            return

        self._redraw_history_overlay_plot()
        if self.history_plot_canvas:
            try: self.history_plot_canvas.draw_idle()
            except Exception as e_draw: print(f"Error during history_plot_canvas.draw_idle: {e_draw}", file=sys.stderr)

    def _redraw_history_overlay_plot(self):
        if not self.history_plot_figure or not self.history_plot_canvas:
            self._clear_history_plot_area("绘图区域不可用。")
            return
        if not self.history_overlay_plot_data and self.history_listbox.curselection():
            self._clear_history_plot_area("无系列数据可绘制。")
            if self.history_plot_overlay_legend_frame and not self.history_plot_overlay_legend_frame.winfo_ismapped():
                 if any(item.get('var') for item in self.history_overlay_plot_data): # Check if any checkboxes exist
                    self.history_plot_overlay_legend_frame.pack(fill=tk.BOTH, expand=True, pady=(5,0), padx=2)
            return
        elif not self.history_listbox.curselection():
            self._clear_history_plot_area("请选择文件进行绘制。")
            return

        for manager in self.history_annotation_managers: manager.disconnect_motion_event()
        self.history_annotation_managers.clear()
        for crosshair in self.history_crosshair_features: crosshair.disconnect()
        self.history_crosshair_features.clear()
        
        fig = self.history_plot_figure
        fig.clear(); ax = fig.add_subplot(111); ax_twin = None
        manager = gui_utils.PlotAnnotationManager(ax, self.history_plot_canvas)
        manager.connect_motion_event(); self.history_annotation_managers.append(manager)
        crosshair_main = gui_utils.CrosshairFeature(self.app, ax, self.history_plot_canvas)
        crosshair_main.connect(); self.history_crosshair_features.append(crosshair_main)

        plotted_anything_on_overlay = False; first_series_type = None 
        visible_series_items = [item for item in self.history_overlay_plot_data if item['var'].get()]
        
        if not visible_series_items:
            ax.set_title("历史记录图 (无系列选中)", fontsize=10)
            ax.set_xlabel(self._get_x_axis_label_for_type(None))
            ax.set_ylabel("Current (A)")
            ax.grid(False)
            if self.history_plot_canvas: self.history_plot_canvas.draw_idle()
            return

        first_plottable_item = visible_series_items[0]
        first_series_type = first_plottable_item.get('measurement_type', "Unknown")
        x_label_overlay = self._get_x_axis_label_for_type(first_series_type)
        y_label_current_overlay_base = "Current (A)"; y_label_gm_overlay_base = "Transconductance (S)" 
        
        primary_y_is_log = self.history_use_log_y.get()
        if first_series_type == "Output Characteristics" and not any(item.get('is_secondary_y') for item in visible_series_items):
            primary_y_is_log = False 
        
        if primary_y_is_log:
            ax.set_yscale('log'); y_label_parts = y_label_current_overlay_base.split('(')
            ax.set_ylabel(f"|{y_label_parts[0].strip()}| ({y_label_parts[1]}" if len(y_label_parts) > 1 else f"|{y_label_current_overlay_base}|")
        else: ax.set_yscale('linear'); ax.set_ylabel(y_label_current_overlay_base)
        
        lines_for_legend_primary, labels_for_legend_primary = [], []
        lines_for_legend_secondary, labels_for_legend_secondary = [], []

        for series_item in visible_series_items:
            x_data, y_data_raw = series_item['x'], series_item['y_raw']
            is_secondary = series_item.get('is_secondary_y', False)
            current_ax_for_item, current_series_use_log_y = ax, primary_y_is_log
            if is_secondary: 
                current_series_use_log_y = False 
                if ax_twin is None: 
                    ax_twin = ax.twinx()
                    manager_twin = gui_utils.PlotAnnotationManager(ax_twin, self.history_plot_canvas)
                    manager_twin.connect_motion_event(); self.history_annotation_managers.append(manager_twin)
                    crosshair_twin = gui_utils.CrosshairFeature(self.app, ax_twin, self.history_plot_canvas)
                    crosshair_twin.connect(); self.history_crosshair_features.append(crosshair_twin)
                current_ax_for_item = ax_twin
            
            y_data_to_plot = np.abs(y_data_raw) if current_series_use_log_y else y_data_raw
            valid_indices = ~(np.isnan(x_data) | np.isnan(y_data_to_plot))
            if current_series_use_log_y: valid_indices &= (y_data_to_plot > 1e-14)
            
            if np.any(valid_indices):
                sorted_indices = np.argsort(x_data[valid_indices])
                line, = current_ax_for_item.plot(x_data[valid_indices][sorted_indices], y_data_to_plot[valid_indices][sorted_indices], 
                                        label=series_item['label'], color=series_item['color'], 
                                        linestyle=series_item['linestyle'], marker=series_item['marker'], ms=series_item['ms'])
                if is_secondary: lines_for_legend_secondary.append(line); labels_for_legend_secondary.append(series_item['label'])
                else: lines_for_legend_primary.append(line); labels_for_legend_primary.append(series_item['label'])
                plotted_anything_on_overlay = True
        
        ax.set_xlabel(x_label_overlay)
        if ax_twin: 
            ax_twin.set_ylabel(y_label_gm_overlay_base, color='purple'); ax_twin.tick_params(axis='y', labelcolor='purple'); ax_twin.set_yscale('linear') 
        
        all_lines, all_labels = lines_for_legend_primary + lines_for_legend_secondary, labels_for_legend_primary + labels_for_legend_secondary
        if plotted_anything_on_overlay:
            num_overlay_curves = len(all_lines)
            unique_filenames_in_plot = list(set(item['filename'] for item in visible_series_items))
            plot_title = f"历史记录: {os.path.splitext(unique_filenames_in_plot[0])[0]}" if len(unique_filenames_in_plot) == 1 else "叠加图 (Overlay Plot)"
            ax.set_title(plot_title, fontsize=10)
            if num_overlay_curves <= 15: ax.legend(all_lines, all_labels, title="图例 (Legend)", fontsize=7, ncol=max(1, int(np.ceil(num_overlay_curves / 6))), loc='best')
            else: ax.text(0.98, 0.98, f"{num_overlay_curves} series\n(Legend omitted)", transform=ax.transAxes, ha='right', va='top', fontsize=7, bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', alpha=0.7))
        else: 
            ax.set_title("历史记录图 (无系列选中或数据无效)", fontsize=10)
        
        ax.grid(True, which="both" if primary_y_is_log else "major", alpha=0.3)
        if ax_twin: ax_twin.grid(False) 
        
        if not self.history_y_auto_scale.get():
            try:
                ymin_str, ymax_str = self.history_y_min_var.get(), self.history_y_max_var.get()
                if ymin_str and ymax_str: 
                    ymin_val, ymax_val = float(ymin_str), float(ymax_str)
                    if ymin_val < ymax_val:
                        if primary_y_is_log and (ymin_val <= 0 or ymax_val <=0): gui_utils.set_status(self.app, "Y轴范围无效：对数刻度下Y值必须为正。", error=True)
                        else: ax.set_ylim(ymin_val, ymax_val)
                    else: gui_utils.set_status(self.app, "Y轴范围无效: Y最小值必须小于Y最大值。", error=True)
            except ValueError: gui_utils.set_status(self.app, "Y轴范围输入无效，请输入数字。", error=True)
        
        try:
            fig.tight_layout(rect=[0, 0, 1, 0.95]) 
        except Exception: pass
        
        if self.history_plot_canvas: self.history_plot_canvas.draw_idle()

    def _clear_history_plot_area(self, message="选择一个或多个文件进行绘制"):
        if self.history_plot_figure is None: return
        
        for manager in self.history_annotation_managers: manager.disconnect_motion_event()
        self.history_annotation_managers.clear()
        for crosshair in self.history_crosshair_features: crosshair.disconnect()
        self.history_crosshair_features.clear()

        fig = self.history_plot_figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=10, color='grey', transform=ax.transAxes)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("") 
        ax.grid(False)

        if self.history_plot_canvas:
            manager = gui_utils.PlotAnnotationManager(ax, self.history_plot_canvas)
            manager.connect_motion_event()
            self.history_annotation_managers.append(manager)
            crosshair = gui_utils.CrosshairFeature(self.app, ax, self.history_plot_canvas)
            crosshair.connect()
            self.history_crosshair_features.append(crosshair)
            try:
                self.history_plot_canvas.draw_idle()
            except Exception as e_draw:
                print(f"Error during draw_idle in _clear_history_plot_area: {e_draw}", file=sys.stderr)
        
        if self.history_plot_overlay_legend_frame:
            for widget in self.history_plot_overlay_legend_frame.winfo_children():
                widget.destroy()
            if self.history_plot_overlay_legend_frame.winfo_ismapped():
                 self.history_plot_overlay_legend_frame.pack_forget()
        self.history_overlay_plot_data.clear()

    def _batch_extract_gt_params(self):
        selected_indices = self.history_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先选择要提取参数的栅转移文件。")
            gui_utils.set_status(self.app, "参数提取：未选择文件。")
            return

        gate_transfer_files = [
            self.history_listbox.get(i) for i in selected_indices if "GateTransfer" in self.history_listbox.get(i)
        ]
        if not gate_transfer_files:
            messagebox.showinfo("提示", "选中的文件中没有栅转移测试文件。")
            gui_utils.set_status(self.app, "参数提取：未找到栅转移文件。")
            return

        output_summary_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")],
            title="保存提取的参数汇总",
            initialdir=self.app.output_dir.get(),
            parent=self.app.root
        )
        if not output_summary_path:
            gui_utils.set_status(self.app, "参数提取操作已取消。")
            return

        extracted_params_list = []
        current_output_dir = self.app.output_dir.get()
        gui_utils.set_status(self.app, f"正在从 {len(gate_transfer_files)} 个栅转移文件中提取参数...")
        self.app.root.update_idletasks()

        try:
            for i, filename in enumerate(gate_transfer_files):
                gui_utils.set_status(self.app, f"正在处理文件 {i+1}/{len(gate_transfer_files)}: {filename}...")
                self.app.root.update_idletasks()
                csv_path = os.path.join(current_output_dir, filename)
                
                data_package = self._prepare_data_package_for_file(csv_path, filename)
                if not data_package or data_package['status'] != "success_data_ready":
                    print(f"  Skipping {filename} due to data loading error for param extraction.", file=sys.stderr)
                    extracted_params_list.append({'FileName': filename, 'Error': 'DataLoadFail'})
                    continue
                
                meta = data_package['metadata_from_csv']
                temp_config_for_recalc = {
                    'output_dir': self.app.output_dir.get(), 
                    'file_name': os.path.splitext(filename)[0],
                    'device_type': meta.get('Device Type', self.app.device_type.get()),
                    'channel_width': float(meta.get('Channel Width (um)', self.app.channel_width.get() or 0)),
                    'area': float(meta.get('Area (um^2)', self.app.area.get() or 0)),
                    'Vg_start': float(meta.get('Vg_start (set)', config_settings.GT_DEFAULT_VG_START)),
                    'Vg_stop': float(meta.get('Vg_stop (set)', config_settings.GT_DEFAULT_VG_STOP)),
                    'step': float(meta.get('Vg_step (set)', config_settings.GT_DEFAULT_VG_STEP)),
                    'enable_backward': meta.get('Enable Backward', 'True').lower() == 'true',
                    'Vd': float(meta.get('Vd_bias (set)', config_settings.GT_DEFAULT_VD)),
                    'IlimitDrain': meta.get('IlimitDrain', config_settings.GT_DEFAULT_ILIMIT_DRAIN),
                    'IlimitGate': meta.get('IlimitGate', config_settings.GT_DEFAULT_ILIMIT_GATE),
                    'Drain_nplc': meta.get('Drain_nplc', config_settings.GT_DEFAULT_DRAIN_NPLC),
                    'Gate_nplc': meta.get('Gate_nplc', config_settings.GT_DEFAULT_GATE_NPLC),
                }
                
                try:
                    gt_recalc_instance = GateTransferMeasurement()
                    gt_recalc_instance.processed_data = data_package['processed_data'] 
                    gt_recalc_instance.consistent_len = len(data_package['processed_data'].get('Id', []))
                    
                    gt_recalc_instance._prepare_tsp_parameters(temp_config_for_recalc) 
                    gt_recalc_instance._perform_specific_data_processing(temp_config_for_recalc)

                    params_row = {
                        'FileName': filename,
                        'Vth_fwd (V)': f"{gt_recalc_instance.Vth_fwd_calc:.4f}" if not np.isnan(gt_recalc_instance.Vth_fwd_calc) else 'N/A',
                        'SS_min_fwd (mV/dec)': f"{gt_recalc_instance.min_ss_fwd_calc:.2f}" if not np.isnan(gt_recalc_instance.min_ss_fwd_calc) else 'N/A',
                        'Max_gm_fwd (S)': f"{gt_recalc_instance.max_gm_fwd_calc:.4e}" if not np.isnan(gt_recalc_instance.max_gm_fwd_calc) else 'N/A',
                        'Vg_at_Max_gm_fwd (V)': f"{gt_recalc_instance.vg_at_max_gm_fwd_calc:.4f}" if not np.isnan(gt_recalc_instance.vg_at_max_gm_fwd_calc) else 'N/A',
                        'Ion_fwd (A)': f"{gt_recalc_instance.ion_fwd_calc:.4e}" if not np.isnan(gt_recalc_instance.ion_fwd_calc) else 'N/A',
                        'Ioff_fwd (A)': f"{gt_recalc_instance.ioff_fwd_calc:.4e}" if not np.isnan(gt_recalc_instance.ioff_fwd_calc) else 'N/A',
                        'Ion_Ioff_Ratio_fwd': f"{gt_recalc_instance.ion_ioff_ratio_fwd_calc:.4e}" if not np.isnan(gt_recalc_instance.ion_ioff_ratio_fwd_calc) else 'N/A',
                    }
                    extracted_params_list.append(params_row)

                except Exception as e_recalc:
                    print(f"Error recalculating parameters for {filename}: {e_recalc}\n{traceback.format_exc()}", file=sys.stderr)
                    extracted_params_list.append({
                        'FileName': filename, 'Error': f'RecalcFail: {e_recalc}'
                    })
                    continue

            if not extracted_params_list:
                messagebox.showinfo("无参数", "未能从选中的文件中提取任何参数。")
                gui_utils.set_status(self.app, "参数提取完成：无参数提取。"); return

            summary_df = pd.DataFrame(extracted_params_list)
            if output_summary_path.endswith(".csv"):
                summary_df.to_csv(output_summary_path, index=False, encoding='utf-8')
            else: 
                summary_df.to_string(output_summary_path, index=False)
            
            messagebox.showinfo("成功", f"选中的 {len(extracted_params_list)} 个栅转移文件的参数已成功提取到\n{os.path.basename(output_summary_path)}")
            gui_utils.set_status(self.app, f"栅转移参数已成功提取到 {os.path.basename(output_summary_path)}")

        except Exception as e_extract_batch:
            messagebox.showerror("参数提取错误", f"批量提取参数时发生错误: {e_extract_batch}")
            print(f"批量提取参数时发生错误: {e_extract_batch}\n{traceback.format_exc()}", file=sys.stderr)
            gui_utils.set_status(self.app, "批量提取参数时出错。", error=True)

    def _on_mouse_motion_history_plot(self, event):
        for manager in self.history_annotation_managers:
             manager.on_motion(event)

    def _toggle_history_y_scale_entries(self):
        if self.history_y_auto_scale.get():
            self.history_y_min_entry.config(state=tk.DISABLED)
            self.history_y_max_entry.config(state=tk.DISABLED)
        else:
            self.history_y_min_entry.config(state=tk.NORMAL)
            self.history_y_max_entry.config(state=tk.NORMAL)
        self._plot_selected_history_files_action_if_selected()

    def _plot_selected_history_files_action_if_selected(self):
        if self.history_listbox.curselection():
            self._plot_selected_history_files_action()

    def _plot_selected_history_files_action_if_selected_and_manual_scale(self):
        if not self.history_y_auto_scale.get():
            self._plot_selected_history_files_action_if_selected()

    def refresh_file_list(self):
        self.history_listbox.delete(0, tk.END)
        output_dir = self.app.output_dir.get()
        if not os.path.isdir(output_dir):
            self.history_listbox.insert(tk.END, "输出目录无效或未设置。")
            return
        try:
            files = [f for f in os.listdir(output_dir) if f.endswith('.csv') and
                     any(m_type in f for m_type in ["GateTransfer", "Output", "Breakdown", "Diode"])]
            files.sort(key=lambda name: os.path.getmtime(os.path.join(output_dir, name)), reverse=True)
            if files:
                for f_name in files: self.history_listbox.insert(tk.END, f_name)
            else: self.history_listbox.insert(tk.END, "未找到CSV文件。")
        except Exception as e:
            self.history_listbox.insert(tk.END, f"读取文件列表时出错: {e}")
            print(f"Error refreshing file list: {e}", file=sys.stderr)
        self._on_history_file_select()

    def _infer_measurement_type_from_filename(self, filename):
        if "GateTransfer" in filename: return "Gate Transfer"
        if "Output" in filename: return "Output Characteristics"
        if "Breakdown" in filename: return "Breakdown Characteristics"
        if "Diode" in filename: return "Diode Characterization"
        return None

    def _get_base_series_type(self, current_key_label):
        match = re.match(r"([a-zA-Z_]+)\s*\(Vg=", current_key_label)
        if match: return match.group(1)
        return current_key_label

    def _on_series_checkbox_toggle(self, toggled_series_item_index):
        if not self.history_overlay_plot_data or toggled_series_item_index >= len(self.history_overlay_plot_data):
            return
        
        toggled_item = self.history_overlay_plot_data[toggled_series_item_index]
        new_state = toggled_item['var'].get()

        if toggled_item['measurement_type'] == "Output Characteristics":
            toggled_vg_value = toggled_item.get('vg_value')
            toggled_current_key = toggled_item.get('current_key')

            if toggled_vg_value is not None and toggled_current_key == 'Id':
                for i, series_item in enumerate(self.history_overlay_plot_data):
                    if i == toggled_series_item_index: continue
                    if series_item['measurement_type'] == "Output Characteristics" and \
                       series_item.get('current_key') == 'Id' and \
                       series_item.get('vg_value') == toggled_vg_value:
                        # Only update if the var is different to avoid recursion if we had multiple checkboxes for same logical series
                        if series_item['var'].get() != new_state:
                            series_item['var'].set(new_state)
        else:
            base_toggled_series_type = self._get_base_series_type(toggled_item['current_key'])
            # For non-Output types, sync all series of the same base type across all files
            for i, series_item in enumerate(self.history_overlay_plot_data):
                if i == toggled_series_item_index: continue
                # Check if it's the same measurement type and same base series type
                if series_item['measurement_type'] == toggled_item['measurement_type']:
                    base_current_series_type = self._get_base_series_type(series_item['current_key'])
                    if base_current_series_type == base_toggled_series_type:
                        if series_item['var'].get() != new_state:
                            series_item['var'].set(new_state)
        
        self._redraw_history_overlay_plot()


    def _rename_selected_history_file(self):
        selected_indices = self.history_listbox.curselection()
        if not selected_indices or len(selected_indices) > 1:
            messagebox.showinfo("提示", "请先从列表中选择一个文件进行重命名。"); return
        old_filename_csv = self.history_listbox.get(selected_indices[0])
        old_base_name_no_ext = os.path.splitext(old_filename_csv)[0]
        measurement_type_short = instrument_utils.get_short_measurement_type(old_filename_csv)
        if not measurement_type_short:
            messagebox.showerror("错误", "无法从文件名推断测量类型以进行重命名。"); return
        old_png_suffix = instrument_utils.get_plot_suffix_for_measurement(measurement_type_short)
        old_filename_png = old_base_name_no_ext + old_png_suffix
        current_output_dir = self.app.output_dir.get()
        old_path_csv, old_path_png = os.path.join(current_output_dir, old_filename_csv), os.path.join(current_output_dir, old_filename_png)
        initial_suggestion_parts = old_base_name_no_ext.split(f"_{measurement_type_short}_")
        initial_user_part = initial_suggestion_parts[0] if len(initial_suggestion_parts) > 1 and initial_suggestion_parts[0] != "" else ""
        new_user_provided_base_name = simpledialog.askstring("重命名文件", "输入新的用户自定义基本文件名 (不含测量类型和日期):", initialvalue=initial_user_part, parent=self.app.root)
        if new_user_provided_base_name is None: return
        new_user_provided_base_name = new_user_provided_base_name.strip().replace(' ', '_')
        if new_user_provided_base_name and not gui_utils.validate_filename_base(new_user_provided_base_name): return
        timestamp_match = re.search(r'(\d{8}_\d{6})', old_base_name_no_ext)
        timestamp_str = timestamp_match.group(1) if timestamp_match else datetime.now().strftime('%Y%m%d_%H%M%S')
        new_base_name_no_ext = f"{new_user_provided_base_name}_{measurement_type_short}_{timestamp_str}" if new_user_provided_base_name else f"{measurement_type_short}_{timestamp_str}"
        new_filename_csv, new_filename_png = f"{new_base_name_no_ext}.csv", f"{new_base_name_no_ext}{old_png_suffix}"
        new_path_csv, new_path_png = os.path.join(current_output_dir, new_filename_csv), os.path.join(current_output_dir, new_filename_png)
        if new_path_csv == old_path_csv: messagebox.showinfo("提示", "新文件名与旧文件名相同。"); return
        if os.path.exists(new_path_csv) or (os.path.exists(old_path_png) and os.path.exists(new_path_png) and new_path_png != old_path_png):
            messagebox.showerror("错误", "具有新名称的文件已存在。"); return
        try:
            os.rename(old_path_csv, new_path_csv)
            if os.path.exists(old_path_png) and old_path_png != new_path_png : os.rename(old_path_png, new_path_png)
            self.refresh_file_list()
            for i in range(self.history_listbox.size()):
                if self.history_listbox.get(i) == new_filename_csv:
                    self.history_listbox.selection_clear(0, tk.END); self.history_listbox.selection_set(i)
                    self.history_listbox.activate(i); self.history_listbox.see(i); break
            messagebox.showinfo("成功", "文件已成功重命名。")
        except Exception as e: messagebox.showerror("重命名错误", f"重命名文件时出错: {e}")

    def _get_x_axis_label_for_type(self, measurement_type):
        if measurement_type == "Gate Transfer": return "$V_G$ (V)"
        if measurement_type == "Output Characteristics": return "$V_D$ (V)"
        if measurement_type == "Breakdown Characteristics": return "$V_D$ (V)"
        if measurement_type == "Diode Characterization": return "$V_{Anode}$ (V)"
        return "Voltage (V)"

    def _merge_selected_history_to_csv(self):
        if not self.history_overlay_plot_data:
            messagebox.showinfo("提示", "请先在历史记录中选择文件并点击“绘制选中项”以加载系列数据，然后勾选要合并的系列。")
            gui_utils.set_status(self.app, "合并操作：无系列数据可合并。"); return
        all_series_for_df = []
        visible_and_valid_series = [
            item for item in self.history_overlay_plot_data 
            if item['var'].get() and not item.get('is_current_density', False)
        ]
        if not visible_and_valid_series:
            messagebox.showinfo("提示", "请在“系列控制”中勾选至少一个有效的电流/电压数据系列进行合并。")
            gui_utils.set_status(self.app, "合并操作：未勾选任何有效系列。"); return

        for series_item in visible_and_valid_series:
            x_data, y_data = np.asarray(series_item['x']), np.asarray(series_item['y_raw'])
            if x_data.size == 0 or y_data.size == 0 or x_data.size != y_data.size:
                continue
            filename_short = os.path.splitext(os.path.basename(series_item['filename']))[0]
            base_y_axis_key = self._get_base_series_type(series_item['current_key'])
            y_axis_key_safe = re.sub(r'[^\w\.-]', '_', base_y_axis_key) 
            x_axis_type_label = self._get_x_axis_label_for_type(series_item['measurement_type']).replace('$', '').replace('_', '').split('(')[0].strip()
            y_axis_col_part = y_axis_key_safe
            if series_item['measurement_type'] == "Output Characteristics" and base_y_axis_key == 'Id':
                vg_match = re.search(r"Vg=([-\d\.]+)(?:V)?\)", series_item['label'])
                vg_suffix = f"_Vg_{vg_match.group(1).replace('.','p')}" if vg_match else ""
                y_axis_col_part = f"{base_y_axis_key}{vg_suffix}"
            x_col_name_base = f"{filename_short}_{y_axis_col_part}_{x_axis_type_label}"
            y_col_name_base = f"{filename_short}_{y_axis_col_part}"
            x_col_name, y_col_name = x_col_name_base, y_col_name_base
            count = 1
            existing_names_in_df = [s.name for s in all_series_for_df if hasattr(s, 'name')]
            while x_col_name in existing_names_in_df or y_col_name in existing_names_in_df:
                x_col_name = f"{x_col_name_base}_{count}"
                y_col_name = f"{y_col_name_base}_{count}"
                count += 1
            all_series_for_df.append(pd.Series(x_data, name=x_col_name))
            all_series_for_df.append(pd.Series(y_data, name=y_col_name))
        if not all_series_for_df:
            messagebox.showinfo("提示", "未能准备任何有效系列进行合并。"); return
        output_csv_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
            title="保存合并后的勾选系列数据 (宽格式)",
            initialdir=self.app.output_dir.get(), parent=self.app.root
        )
        if not output_csv_path:
            gui_utils.set_status(self.app, "合并操作已取消。"); return
        gui_utils.set_status(self.app, f"正在合并 {len(all_series_for_df)//2} 个勾选的系列...")
        self.app.root.update_idletasks()
        try:
            merged_df = pd.concat(all_series_for_df, axis=1)
            merged_df.to_csv(output_csv_path, index=False, encoding='utf-8')
            messagebox.showinfo("成功", f"选中的 {len(all_series_for_df)//2} 个系列已成功合并到\n{os.path.basename(output_csv_path)}")
            gui_utils.set_status(self.app, f"系列数据已成功合并到 {os.path.basename(output_csv_path)}")
        except Exception as e_merge:
            messagebox.showerror("合并错误", f"合并系列数据时发生错误: {e_merge}")
            print(f"合并系列数据时发生错误: {e_merge}\n{traceback.format_exc()}", file=sys.stderr)
            gui_utils.set_status(self.app, "合并系列数据时出错。", error=True)

