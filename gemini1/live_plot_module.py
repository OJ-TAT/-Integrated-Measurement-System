# live_plot_module.py
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import traceback
import sys

import gui_utils 
import gate_transfer_module 
import output_module
import breakdown_module
import diode_module

class LivePlotHandler:
    def __init__(self, app_instance, parent_frame):
        self.app = app_instance
        self.parent_frame = parent_frame
        self.style = gui_utils.get_style() # This uses the correct get_style
        self.live_plot_figure = None
        self.live_plot_canvas = None
        self.live_plot_toolbar = None
        self.live_plot_canvas_widget = None
        self.live_annotation_managers = []
        self.live_crosshair_features = []
        self.gt_live_plot_type = tk.StringVar(value="default_live") # Default to 4-plot
        self.last_live_plot_data_package = None 
        self.gt_plot_controls_frame = None
        self.live_params_display_frame = None
        self.live_plot_params_labels = {} 
        self._create_live_plot_area_with_controls()

    def _create_live_plot_area_with_controls(self):
        main_live_plot_frame = ttk.LabelFrame(self.parent_frame, text="实时绘图 (Live Plot)")
        main_live_plot_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        main_live_plot_frame.columnconfigure(0, weight=1)
        main_live_plot_frame.rowconfigure(2, weight=1) # Canvas area should expand

        self.gt_plot_controls_frame = ttk.Frame(main_live_plot_frame)
        self.gt_plot_controls_frame.grid(row=0, column=0, sticky="ew", pady=(2,3))
        ttk.Label(self.gt_plot_controls_frame, text="栅转移绘图类型 (GT Plot Type):").pack(side=tk.LEFT, padx=(0,5))
        gt_plot_types = [
            ("线性 Id/Ig + gm", "linear_all"), ("对数 |Id|+|Ig|", "log_currents"),
            ("仅 gm", "gm_only"), ("默认四图", "default_live")
        ]
        for text, mode in gt_plot_types:
            rb = ttk.Radiobutton(self.gt_plot_controls_frame, text=text, variable=self.gt_live_plot_type, value=mode, command=self._on_gt_live_plot_type_change)
            rb.pack(side=tk.LEFT, padx=3)
        self.gt_plot_controls_frame.grid_remove() # Hide initially

        self.live_params_display_frame = ttk.Frame(main_live_plot_frame)
        self.live_params_display_frame.grid(row=1, column=0, sticky="ew", pady=(3,5), padx=5)
        self.live_params_display_frame.grid_remove() # Hide initially

        canvas_area = ttk.Frame(main_live_plot_frame)
        canvas_area.grid(row=2, column=0, sticky="nsew")
        canvas_area.rowconfigure(0, weight=1)
        canvas_area.columnconfigure(0, weight=1)

        try:
            self.live_plot_figure = plt.Figure(figsize=(5, 4), dpi=100)
            self.live_plot_canvas = FigureCanvasTkAgg(self.live_plot_figure, master=canvas_area)
            self.live_plot_canvas_widget = self.live_plot_canvas.get_tk_widget()
            self.live_plot_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.live_plot_toolbar = NavigationToolbar2Tk(self.live_plot_canvas, canvas_area, pack_toolbar=False)
            self.live_plot_toolbar.update()
            self.live_plot_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            self.clear_live_plot_area("等待测量... (Waiting for measurement...)")
        except Exception as e:
            print(f"关键错误: 实时绘图区域初始化失败: {e}\n{traceback.format_exc()}", file=sys.stderr)
            self.live_plot_figure = None; self.live_plot_canvas = None
            error_label = ttk.Label(canvas_area, text=f"实时绘图区域初始化失败:\n{e}", foreground="red", wraplength=300)
            error_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
            
    def update_live_plot(self, result_package):
        self.last_live_plot_data_package = result_package.copy()
        measurement_name = result_package.get("measurement_type_name", "测量")
        plot_function_generate = None
        
        if measurement_name == "Gate Transfer":
            self.gt_plot_controls_frame.grid() 
            # Parameters to display for Gate Transfer (mobility removed)
            gt_params_to_display = {
                'Vth_fwd_calc': result_package.get('Vth_fwd_calc'), 
                'min_ss_fwd_calc': result_package.get('min_ss_fwd_calc'),
                'max_gm_fwd': result_package.get('max_gm_fwd'), 
                'Vg_at_max_gm_fwd': result_package.get('Vg_at_max_gm_fwd'),
                'Ion_fwd': result_package.get('Ion_fwd'), 
                'Ioff_fwd': result_package.get('Ioff_fwd'),
                'Ion_Ioff_ratio_fwd': result_package.get('Ion_Ioff_ratio_fwd')
            }
            self._update_live_plot_params_display(gt_params_to_display)
            result_package['live_plot_type'] = self.gt_live_plot_type.get()
            plot_function_generate = gate_transfer_module.generate_gate_transfer_plot
        else: # For other measurement types
            self.gt_plot_controls_frame.grid_remove() # Hide GT plot type controls
            self._update_live_plot_params_display(None) # Clear or hide params display
            if "Output Characteristics" == measurement_name: plot_function_generate = output_module.generate_output_plot
            elif "Breakdown Characteristics" == measurement_name: plot_function_generate = breakdown_module.generate_breakdown_plot
            elif "Diode Characterization" == measurement_name: plot_function_generate = diode_module.generate_diode_plot
        
        if plot_function_generate and self.live_plot_figure and self.live_plot_canvas:
            try:
                result_package['target_figure'] = self.live_plot_figure
                for manager in self.live_annotation_managers: manager.disconnect_motion_event()
                self.live_annotation_managers.clear()
                for crosshair in self.live_crosshair_features: crosshair.disconnect()
                self.live_crosshair_features.clear()

                plot_success = plot_function_generate(result_package)
                if plot_success:
                    for ax_sub in self.live_plot_figure.axes:
                        manager = gui_utils.PlotAnnotationManager(ax_sub, self.live_plot_canvas)
                        manager.connect_motion_event(); self.live_annotation_managers.append(manager)
                        crosshair = gui_utils.CrosshairFeature(self.app, ax_sub, self.live_plot_canvas)
                        crosshair.connect(); self.live_crosshair_features.append(crosshair)
                    self.live_plot_canvas.draw_idle()
                    return True, f"{measurement_name} 完成。"
                else:
                    self.clear_live_plot_area(f"{measurement_name} 绘图失败")
                    return False, f"为 {measurement_name} 生成绘图失败。"
            except Exception as plot_e:
                tb_plot_str = traceback.format_exc()
                self.clear_live_plot_area(f"{measurement_name} 绘图异常")
                print(f"{measurement_name} 的绘图异常: {plot_e}\n{tb_plot_str}", file=sys.stderr)
                return False, f"为 {measurement_name} 生成绘图时发生错误: {plot_e}"
        elif not (self.live_plot_figure and self.live_plot_canvas):
            return False, f"{measurement_name} 完成，但实时绘图区域不可用。"
        else: 
            self.clear_live_plot_area(f"{measurement_name} 数据已处理 (无绘图)")
            return True, f"{measurement_name} 数据处理完成 (无绘图函数)。"

    def _on_gt_live_plot_type_change(self):
        if self.last_live_plot_data_package and \
           self.last_live_plot_data_package.get("measurement_type_name") == "Gate Transfer" and \
           self.live_plot_figure and self.live_plot_canvas:
            
            current_plot_type = self.gt_live_plot_type.get()
            package_for_replot = self.last_live_plot_data_package.copy()
            package_for_replot['live_plot_type'] = current_plot_type
            package_for_replot['target_figure'] = self.live_plot_figure

            # Refresh displayed parameters (mobility removed)
            gt_params_to_display = {
                'Vth_fwd_calc': package_for_replot.get('Vth_fwd_calc'), 
                'min_ss_fwd_calc': package_for_replot.get('min_ss_fwd_calc'),
                'max_gm_fwd': package_for_replot.get('max_gm_fwd'), 
                'Vg_at_max_gm_fwd': package_for_replot.get('Vg_at_max_gm_fwd'),
                'Ion_fwd': package_for_replot.get('Ion_fwd'), 
                'Ioff_fwd': package_for_replot.get('Ioff_fwd'),
                'Ion_Ioff_ratio_fwd': package_for_replot.get('Ion_Ioff_ratio_fwd')
            }
            self._update_live_plot_params_display(gt_params_to_display)

            for manager in self.live_annotation_managers: manager.disconnect_motion_event()
            self.live_annotation_managers.clear()
            for crosshair in self.live_crosshair_features: crosshair.disconnect()
            self.live_crosshair_features.clear()

            plot_success = gate_transfer_module.generate_gate_transfer_plot(package_for_replot)
            if plot_success:
                for ax_sub in self.live_plot_figure.axes:
                    manager = gui_utils.PlotAnnotationManager(ax_sub, self.live_plot_canvas)
                    manager.connect_motion_event(); self.live_annotation_managers.append(manager)
                    crosshair = gui_utils.CrosshairFeature(self.app, ax_sub, self.live_plot_canvas)
                    crosshair.connect(); self.live_crosshair_features.append(crosshair)
                self.live_plot_canvas.draw_idle()
                gui_utils.set_status(self.app, f"栅转移实时绘图已更新为: {current_plot_type}")
            else:
                self.clear_live_plot_area("重新绘制栅转移图失败")
                gui_utils.set_status(self.app, "重新绘制栅转移图失败", error=True)
        elif not self.last_live_plot_data_package or self.last_live_plot_data_package.get("measurement_type_name") != "Gate Transfer":
            gui_utils.set_status(self.app, "无栅转移数据可供重新绘图 (No Gate Transfer data to replot)")
            self._update_live_plot_params_display(None)
        else:
            gui_utils.set_status(self.app, "实时绘图区域未准备好。(Live plot area not ready.)", error=True)

    def clear_live_plot_area(self, message=""):
        if self.live_plot_figure is None: return
        
        for manager in self.live_annotation_managers: manager.disconnect_motion_event()
        self.live_annotation_managers.clear()
        for crosshair in self.live_crosshair_features: crosshair.disconnect()
        self.live_crosshair_features.clear()

        self.live_plot_figure.clear()
        ax = self.live_plot_figure.add_subplot(111)
        if message: ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=12, transform=ax.transAxes)
        else: ax.set_xlabel(""); ax.set_ylabel(""); ax.set_title("")
        ax.grid(False)
        if self.live_plot_canvas:
            manager = gui_utils.PlotAnnotationManager(ax, self.live_plot_canvas)
            manager.connect_motion_event(); self.live_annotation_managers.append(manager)
            crosshair = gui_utils.CrosshairFeature(self.app, ax, self.live_plot_canvas)
            crosshair.connect(); self.live_crosshair_features.append(crosshair)
            try: self.live_plot_canvas.draw_idle()
            except Exception as e_draw: print(f"Error during draw_idle in clear_live_plot_area: {e_draw}", file=sys.stderr)
        self._update_live_plot_params_display(None) # Clear params display when plot is cleared

    def _update_live_plot_params_display(self, params_dict=None):
        for widget in self.live_params_display_frame.winfo_children(): widget.destroy()
        if not params_dict:
            self.live_params_display_frame.grid_remove()
            return
        self.live_params_display_frame.grid()
        # param_display_order without mobility
        param_display_order = [
            ('Vth_fwd_calc', 'V_th (V)'), ('min_ss_fwd_calc', 'SS_min (mV/dec)'),
            ('max_gm_fwd', 'g_m_max (S)'), ('Vg_at_max_gm_fwd', 'Vg @ g_m_max (V)'),
            ('Ion_fwd', 'I_on (A)'), ('Ioff_fwd', 'I_off (A)'), ('Ion_Ioff_ratio_fwd', 'I_on/I_off')
        ]
        row_idx, col_idx, max_cols = 0, 0, 2 # Adjusted max_cols for fewer params
        for key, display_name in param_display_order:
            value = params_dict.get(key)
            is_valid_number = value is not None and isinstance(value, (int, float, np.number)) and not np.isnan(value)
            if is_valid_number:
                if isinstance(value, float):
                    # Formatting remains the same, just fewer params
                    if abs(value) < 1e-9 and abs(value) > 0 : text_val = f"{value:.2e}" 
                    elif abs(value) > 1e4 or (abs(value) < 1e-2 and abs(value) > 0): text_val = f"{value:.3e}"
                    else: text_val = f"{value:.3f}"
                else: text_val = str(value)
                
                lbl_text = f"{display_name}: {text_val}"
                lbl = ttk.Label(self.live_params_display_frame, text=lbl_text, font=self.style['font_label'])
                lbl.grid(row=row_idx, column=col_idx, padx=(0,15), pady=1, sticky="w")
                col_idx += 1
                if col_idx >= max_cols: col_idx, row_idx = 0, row_idx + 1
        
        if row_idx == 0 and col_idx == 0: # No valid params were displayed
            self.live_params_display_frame.grid_remove()