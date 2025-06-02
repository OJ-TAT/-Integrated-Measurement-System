# measurement_handler.py
import tkinter as tk
from tkinter import messagebox
import os
import threading
import traceback
import queue
import sys
import numpy as np
from datetime import datetime # For timestamping post-stress files

import gate_transfer_module
import output_module
import breakdown_module
import diode_module
import stress_module # New import
import config_settings
import gui_utils
import instrument_utils

class MeasurementHandler:
    def __init__(self, app_instance, live_plot_handler_instance):
        self.app = app_instance
        self.live_plot_handler = live_plot_handler_instance
        self.measurement_queue = queue.Queue()
        self.app.root.after(100, self.process_measurement_queue)
        self.current_instrument_instance = None # To hold the instrument instance during a sequence

    def _collect_and_validate_common_params(self):
        config = {}
        output_dir_val = self.app.output_dir.get().strip()
        if not output_dir_val or not os.path.isdir(output_dir_val):
            messagebox.showerror("目录错误", "请选择或输入一个有效的输出目录。")
            return None
        config['output_dir'] = output_dir_val

        file_name_base_val = self.app.file_name_base.get().strip()
        if not gui_utils.validate_filename_base(file_name_base_val): return None
        config['file_name'] = file_name_base_val # This will be the base for all parts of the sequence

        config['device_type'] = self.app.device_type.get()
        try:
            raw_val_cw_um = self.app.channel_width_um.get().strip()
            raw_val_area_um2 = self.app.area_um2.get().strip()

            if config['device_type'] == 'lateral':
                if not raw_val_cw_um: raise ValueError("横向器件的沟道宽度 W (µm) 不能为空。")
                config['channel_width_um'] = float(raw_val_cw_um)
                if config['channel_width_um'] <= 0: raise ValueError("沟道宽度 W (µm) 必须为正数。")
                config['area_um2'] = 0.0
            else: # Vertical
                if not raw_val_area_um2: raise ValueError("纵向器件的器件面积 Area (µm²) 不能为空。")
                config['area_um2'] = float(raw_val_area_um2)
                if config['area_um2'] <= 0: raise ValueError("器件面积 Area (µm²) 必须为正数。")
                config['channel_width_um'] = 0.0
        except ValueError as e:
            messagebox.showerror("通用器件参数错误", str(e))
            return None
        return config

    def _validate_specific_params(self, params_vars_dict, param_definition_structure, config_dict_to_fill, context_name):
        for label_text, key, default_or_var in param_definition_structure:
            if isinstance(default_or_var, tk.StringVar):
                var = default_or_var
            elif key in params_vars_dict and "var" in params_vars_dict[key]:
                var = params_vars_dict[key]["var"]
            else:
                messagebox.showerror("内部错误", f"参数 '{key}' 在 '{context_name}' 中未找到对应的变量。")
                return False
            
            val_str = var.get().strip()
            try:
                if not val_str:
                    raise ValueError(f"'{label_text.strip(':')}' 在 '{context_name}' 中不能为空。")
                
                if context_name == "Output Characteristics" and key == "Vg_step": # Vg_step for OC is number of segments
                    val_f = float(val_str)
                    if not val_f.is_integer() or val_f < 0:
                        raise ValueError("Vg 扫描段数必须是0或正整数。")
                    val = int(val_f)
                elif "nplc" in key.lower():
                    val = float(val_str)
                    if not (0.001 <= val <= 60):
                         print(f"  警告: {key} 的NPLC值为 {val}，超出典型的 0.001-60 范围。")
                else:
                    val = float(val_str)
                config_dict_to_fill[key] = val
            except ValueError as ve:
                messagebox.showerror("参数验证错误", f"'{label_text.strip(':')}' 在 '{context_name}' 中的值无效。输入: '{val_str}'。(详情: {ve})")
                return False
        return True

    def _actual_measurement_task_decorated(self, measurement_runner_func, config_dict, measurement_name_override=None):
        """
        Wrapper to run a single measurement function (like run_gate_transfer_measurement).
        Handles instrument connection and status updates.
        """
        measurement_display_name = measurement_name_override or config_dict.get('measurement_type_name', '测量')
        gui_utils.set_status(self.app, f"正在运行 {measurement_display_name}...")
        self.app.root.update_idletasks()

        # Ensure GPIB address and timeout are in the config for the runner function
        config_dict[config_settings.CONFIG_KEY_GPIB_ADDRESS] = config_dict.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
        config_dict[config_settings.CONFIG_KEY_TIMEOUT] = config_dict.get(config_settings.CONFIG_KEY_TIMEOUT, config_settings.DEFAULT_TIMEOUT)

        result_package = measurement_runner_func(config_dict) # This function now expects config with GPIB and timeout
        
        # Ensure the result_package has the correct measurement_type_name for GUI processing
        if 'measurement_type_name' not in result_package or result_package['measurement_type_name'] != measurement_display_name:
            result_package['measurement_type_name'] = measurement_display_name
            
        self.measurement_queue.put(result_package)
        return result_package # Return for sequential tasks

    def _run_stress_then_gate_transfer_sequence(self, combined_config):
        """
        Runs Stress measurement followed by Gate Transfer measurement.
        """
        stress_config = combined_config['stress_params']
        gt_config = combined_config['gt_params']
        common_config_for_sequence = combined_config['common_params']
        
        # --- Stage 1: Stress Measurement ---
        gui_utils.set_status(self.app, f"正在运行应力阶段 (Running Stress Phase)... (1/2)")
        self.app.root.update_idletasks()

        # Prepare full config for stress_module.run_stress_measurement
        current_stress_config = {**common_config_for_sequence, **stress_config}
        current_stress_config["measurement_type_name"] = "应力阶段 (Stress Phase)" # Specific name for this part
        
        # Use a specific timeout for stress if defined, otherwise default
        current_stress_config[config_settings.CONFIG_KEY_TIMEOUT] = getattr(config_settings, 'STRESS_TIMEOUT', config_settings.DEFAULT_TIMEOUT)

        stress_result_package = stress_module.run_stress_measurement(current_stress_config)
        
        # Ensure the result package has the correct name for queue processing
        stress_result_package['measurement_type_name'] = "应力阶段 (Stress Phase)"
        self.measurement_queue.put(stress_result_package)

        if stress_result_package.get('status') == 'error':
            gui_utils.set_status(self.app, f"应力阶段失败: {stress_result_package.get('message', '未知错误')}", error=True)
            self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)") # Re-enable run button
            return # Stop sequence if stress fails

        # --- Stage 2: Gate Transfer Measurement (Post-Stress) ---
        gui_utils.set_status(self.app, f"正在运行应力后栅转移特性测量 (Post-Stress Gate Transfer)... (2/2)")
        self.app.root.update_idletasks()

        # Modify filename for post-stress characterization
        # Use the base filename from common_config and append a suffix
        post_stress_file_name_base = common_config_for_sequence.get('file_name', "")
        if post_stress_file_name_base:
            post_stress_file_name_base += "_post_stress_GT"
        else: # If no base name, create one
            post_stress_file_name_base = f"post_stress_GT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


        current_gt_config = {
            **common_config_for_sequence, 
            **gt_config, 
            'file_name': post_stress_file_name_base # Use the modified filename
        }
        current_gt_config["measurement_type_name"] = "应力后栅转移 (Post-Stress GT)" # Specific name
        current_gt_config[config_settings.CONFIG_KEY_TIMEOUT] = config_settings.DEFAULT_TIMEOUT # Standard timeout for GT

        gt_result_package = gate_transfer_module.run_gate_transfer_measurement(current_gt_config)
        
        gt_result_package['measurement_type_name'] = "应力后栅转移 (Post-Stress GT)"
        self.measurement_queue.put(gt_result_package)

        if gt_result_package.get('status') == 'error':
            gui_utils.set_status(self.app, f"应力后栅转移测量失败: {gt_result_package.get('message', '未知错误')}", error=True)
        else:
            gui_utils.set_status(self.app, "应力测试序列完成。(Stress sequence complete.)")
        
        self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)") # Re-enable run button at the end

    def run_measurement(self):
        self.app.run_button.config(state=tk.DISABLED, text="运行中... (Running...)")
        gui_utils.set_status(self.app, "正在准备测量... (Preparing measurement...)")
        self.app.root.update_idletasks()

        common_config = self._collect_and_validate_common_params()
        if common_config is None:
            self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
            gui_utils.set_status(self.app, "准备就绪：通用参数无效。(Ready: Common parameters invalid.)", error=True)
            return

        selected_tab_widget = self.app.notebook.nametowidget(self.app.notebook.select())
        selected_tab_text = self.app.notebook.tab(selected_tab_widget, "text")
        
        specific_validation_ok = False
        measurement_runner_func = None
        current_config_dict = common_config.copy() # Start with common params
        
        measurement_name_context_map = {
            '栅转移特性 (Gate Transfer)': "Gate Transfer",
            '输出特性 (Output Characteristics)': "Output Characteristics",
            '晶体管击穿 (Transistor Breakdown)': "Breakdown Characteristics",
            '二极管IV (Diode IV)': "Diode Characterization",
            '应力测试 (Stress Test)': "Stress Test" # New
        }
        measurement_name_context = measurement_name_context_map.get(selected_tab_text, "Unknown Measurement")
        # current_config_dict["measurement_type_name"] = measurement_name_context # This will be set per stage for sequences

        try:
            if measurement_name_context == "Gate Transfer":
                if self._validate_specific_params(self.app.gt_params_vars, self.app.gt_fields_structure, current_config_dict, measurement_name_context):
                    current_config_dict['enable_backward'] = self.app.gt_enable_backward.get()
                    # ... (existing GT validation)
                    specific_validation_ok = True # Assume existing validation is fine
                    if specific_validation_ok: measurement_runner_func = gate_transfer_module.run_gate_transfer_measurement
            
            elif measurement_name_context == "Output Characteristics":
                if self._validate_specific_params(self.app.oc_params_vars, self.app.oc_fields_structure, current_config_dict, measurement_name_context):
                    # ... (existing OC validation)
                    specific_validation_ok = True # Assume existing validation is fine
                    if specific_validation_ok: measurement_runner_func = output_module.run_output_measurement

            elif measurement_name_context == "Breakdown Characteristics":
                if self._validate_specific_params(self.app.bd_params_vars, self.app.bd_fields_structure, current_config_dict, measurement_name_context):
                    # ... (existing BD validation)
                    specific_validation_ok = True
                    if specific_validation_ok: measurement_runner_func = breakdown_module.run_breakdown_measurement
            
            elif measurement_name_context == "Diode Characterization":
                if self._validate_specific_params(self.app.diode_params_vars, self.app.diode_fields_structure, current_config_dict, measurement_name_context):
                    current_config_dict['enable_backward'] = self.app.diode_enable_backward.get()
                    # ... (existing Diode validation)
                    specific_validation_ok = True
                    if specific_validation_ok: measurement_runner_func = diode_module.run_diode_measurement

            elif measurement_name_context == "Stress Test": # New Handling for Stress Test Tab
                stress_params_config = {} # For stress-specific GUI params
                if self._validate_specific_params(self.app.stress_params_vars, self.app.stress_fields_structure, stress_params_config, "应力测试参数"):
                    post_char_method_selected = self.app.post_stress_char_method.get()
                    
                    if post_char_method_selected == "栅转移特性 (Gate Transfer)":
                        gt_params_config = {} # For GT-specific GUI params
                        # IMPORTANT: Collect GT params from the GT tab's current settings
                        if self._validate_specific_params(self.app.gt_params_vars, self.app.gt_fields_structure, gt_params_config, "应力后栅转移参数"):
                            gt_params_config['enable_backward'] = self.app.gt_enable_backward.get() # Get backward sweep setting for GT
                            # Add other GT specific validations if necessary here (like step vs start/stop)
                            vg_s, vg_e, vg_st_val = gt_params_config['Vg_start'], gt_params_config['Vg_stop'], gt_params_config['step']
                            if vg_s != vg_e and (vg_st_val == 0 or ((vg_e > vg_s and vg_st_val < 0) or (vg_e < vg_s and vg_st_val > 0))):
                                messagebox.showerror("输入错误 (应力后栅转移)", "应力后栅转移的 Vg 步进 (V) 符号与扫描方向不符或在扫描时为零。请检查“栅转移特性”标签页的参数。")
                                specific_validation_ok = False
                            else:
                                specific_validation_ok = True
                                combined_sequence_config = {
                                    'common_params': common_config.copy(), # Pass the already validated common params
                                    'stress_params': stress_params_config,
                                    'gt_params': gt_params_config
                                }
                                # Use a dedicated runner for the sequence
                                measurement_runner_func = self._run_stress_then_gate_transfer_sequence
                                current_config_dict = combined_sequence_config # The runner function will take this combined dict
                        else:
                            specific_validation_ok = False # GT params validation failed
                            gui_utils.set_status(self.app, "应力后栅转移参数验证失败。请检查“栅转移特性”标签页的参数。", error=True)
                    
                    elif post_char_method_selected == "输出特性 (Output Characteristics)":
                        # TODO: Implement Stress then Output Characteristics
                        messagebox.showinfo("提示", "“应力后输出特性”功能暂未实现。")
                        specific_validation_ok = False # Mark as not OK to prevent running
                    
                    elif post_char_method_selected == "无 (None)":
                        # Standalone stress test
                        current_config_dict.update(stress_params_config) # Add stress params to common_config
                        current_config_dict["measurement_type_name"] = "应力测试 (Stress Test)" # Set name for standalone stress
                        specific_validation_ok = True
                        measurement_runner_func = stress_module.run_stress_measurement # Runner for standalone stress
                    else:
                        messagebox.showerror("错误", f"未知的应力后表征方法: {post_char_method_selected}")
                        specific_validation_ok = False
                else:
                    specific_validation_ok = False # Stress params validation failed
            
            elif selected_tab_text == '历史记录 (History)':
                 messagebox.showinfo("提示", "运行按钮不适用于此选项卡。")
                 self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
                 gui_utils.set_status(self.app, "准备就绪 (Ready)")
                 return
            else:
                 messagebox.showerror("错误", f"未知的标签页: {selected_tab_text}")
                 self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
                 gui_utils.set_status(self.app, f"错误：未知的标签页 '{selected_tab_text}'", error=True)
                 return

            if not specific_validation_ok and measurement_name_context != "Stress Test": # Don't show generic fail if Stress Test had its own more specific messages
                gui_utils.set_status(self.app, f"{measurement_name_context} 参数验证失败。(Parameter validation failed.)", error=True)
            
            if specific_validation_ok and measurement_runner_func and current_config_dict:
                if measurement_name_context == "Stress Test" and measurement_runner_func == self._run_stress_then_gate_transfer_sequence:
                    gui_utils.set_status(self.app, f"正在开始应力然后栅转移序列...")
                    # For sequences, the runner itself handles status updates for each stage
                elif measurement_name_context == "Stress Test" and measurement_runner_func == stress_module.run_stress_measurement:
                     gui_utils.set_status(self.app, f"正在开始独立应力测试...")
                else: # For single, non-sequence measurements
                    current_config_dict["measurement_type_name"] = measurement_name_context # Set for single measurements
                    gui_utils.set_status(self.app, f"正在开始 {measurement_name_context} 测量...")
                
                # Pass the correct runner and config to the thread
                if measurement_runner_func == self._run_stress_then_gate_transfer_sequence:
                    # For sequence, _actual_measurement_task_decorated is not directly used here.
                    # The sequence runner handles its own instrument interactions.
                    measurement_thread = threading.Thread(target=self._run_stress_then_gate_transfer_sequence,
                                                          args=(current_config_dict,))
                else: # For single measurements (GT, OC, BD, Diode, standalone Stress)
                    measurement_thread = threading.Thread(target=self._actual_measurement_task_decorated,
                                                          args=(measurement_runner_func, current_config_dict, measurement_name_context))
                
                measurement_thread.daemon = True
                measurement_thread.start()
            else:
                 self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
                 if not measurement_runner_func and specific_validation_ok:
                     gui_utils.set_status(self.app, f"错误：{measurement_name_context} 未找到测量函数。", error=True)
        
        except Exception as e_setup:
            messagebox.showerror("应用程序设置错误", f"设置 {measurement_name_context} 测量时发生意外错误: {e_setup}")
            print(f"---应用程序设置错误追溯 ({measurement_name_context} in run_measurement)---\n{traceback.format_exc()}\n---", file=sys.stderr)
            self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
            gui_utils.set_status(self.app, "应用程序错误，请查看控制台。", error=True)

    def process_measurement_queue(self):
        try:
            while not self.measurement_queue.empty():
                result_dict = self.measurement_queue.get_nowait()
                if not isinstance(result_dict, dict):
                    messagebox.showerror("队列错误", f"测量队列中存在意外的项目类型: {type(result_dict)}")
                    if hasattr(self.app, 'run_button'): self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
                    continue
                
                measurement_name = result_dict.get("measurement_type_name", "测量") # Use the name from the result package
                status_message = ""
                is_error = False

                if result_dict.get('status') == "success_data_ready":
                    plot_ok, plot_msg = self.live_plot_handler.update_live_plot(result_dict)
                    status_message = plot_msg
                    if not plot_ok: is_error = True
                    if plot_ok and result_dict.get('csv_file_path'):
                         status_message += f" CSV: {os.path.basename(result_dict.get('csv_file_path'))}"
                elif result_dict.get('status') == 'error':
                    error_msg_detail = result_dict.get('message', f'{measurement_name} 中发生未知错误。')
                    if 'traceback' in result_dict and result_dict['traceback']:
                        print(f"---来自工作线程的错误追溯 ({measurement_name})---\n{result_dict['traceback']}\n---", file=sys.stderr)
                    messagebox.showerror(f"{measurement_name} 失败", error_msg_detail)
                    self.live_plot_handler.clear_live_plot_area(f"{measurement_name} 失败")
                    status_message = f"{measurement_name} 失败: {error_msg_detail}"
                    is_error = True
                else:
                    unknown_err_msg = f"从 {measurement_name} 收到未知的结果状态: {result_dict.get('status', 'N/A')}"
                    messagebox.showerror("结果错误", unknown_err_msg)
                    self.live_plot_handler.clear_live_plot_area(f"{measurement_name} 未知结果")
                    status_message = unknown_err_msg
                    is_error = True

                # Only re-enable run button if it's not a multi-stage process still ongoing
                # For sequences, the sequence runner function (_run_stress_then_gate_transfer_sequence)
                # is responsible for re-enabling the button at the very end.
                # Individual stages of a sequence should not re-enable it prematurely.
                # We can check if the measurement_name indicates it's a final part of a sequence or a standalone test.
                is_final_stage_or_standalone = not ("应力阶段" in measurement_name and "序列完成" not in status_message)

                if is_final_stage_or_standalone: # Re-enable button if it's a standalone or the last part of a sequence
                    if hasattr(self.app, 'run_button'): self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
                
                gui_utils.set_status(self.app, status_message, error=is_error)

                if hasattr(self.app, 'history_tab_handler_instance') and self.app.history_tab_handler_instance:
                    self.app.history_tab_handler_instance.refresh_file_list()
        except queue.Empty: pass
        except Exception as e:
            tb_q_str = traceback.format_exc()
            q_err_msg = f"处理测量队列时发生严重错误: {e}"
            messagebox.showerror("GUI错误", q_err_msg)
            print(f"处理 process_measurement_queue 时发生严重错误: {e}\n{tb_q_str}", file=sys.stderr)
            if hasattr(self.app, 'run_button'): self.app.run_button.config(state=tk.NORMAL, text="▶ 运行 (Run)")
            if hasattr(self.live_plot_handler, 'clear_live_plot_area'): self.live_plot_handler.clear_live_plot_area("GUI 错误")
            gui_utils.set_status(self.app, "GUI 队列处理错误。(GUI queue processing error.)", error=True)
        self.app.root.after(100, self.process_measurement_queue)

