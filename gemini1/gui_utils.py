# gui_utils.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import re
import os
from datetime import datetime
import config_settings # For default values if needed in reset functions
import matplotlib.lines # For Line2D

class PlotAnnotationManager:
    """Manages a single annotation for a Matplotlib axes using ax.annotate."""
    def __init__(self, ax, fig_canvas):
        self.ax = ax
        self.fig_canvas = fig_canvas
        self.annotation = self.ax.annotate("", xy=(0,0), xytext=(20,20),
                                            textcoords="offset points",
                                            bbox=dict(boxstyle="round,pad=0.3", fc="lemonchiffon", alpha=0.75),
                                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2"),
                                            visible=False,
                                            fontfamily="sans-serif",
                                            fontsize=8,
                                            clip_on=True)
        self.cid_motion = None

    def connect_motion_event(self):
        if self.fig_canvas and self.cid_motion is None:
            self.cid_motion = self.fig_canvas.mpl_connect('motion_notify_event', self.on_motion)

    def disconnect_motion_event(self):
        if self.cid_motion and self.fig_canvas:
            self.fig_canvas.mpl_disconnect(self.cid_motion)
            self.cid_motion = None
        self.hide_annotation()

    def hide_annotation(self):
        if self.annotation and self.annotation.get_visible(): 
            self.annotation.set_visible(False)
            if self.fig_canvas and self.fig_canvas.get_tk_widget().winfo_exists():
                try:
                    self.fig_canvas.draw_idle()
                except tk.TclError: pass 

    def on_motion(self, event):
        if not event.inaxes:
            if self.annotation and self.annotation.get_visible():
                self.hide_annotation()
            return

        ax_event = event.inaxes
        is_relevant_ax = (ax_event == self.ax)
        if not is_relevant_ax:
            is_twin = False
            if hasattr(self.ax, 'get_shared_x_axes') and self.ax.get_shared_x_axes().joined(self.ax, ax_event):
                is_twin = True
            if not is_twin and hasattr(self.ax, 'get_shared_y_axes') and self.ax.get_shared_y_axes().joined(self.ax, ax_event):
                is_twin = True
            if not is_twin:
                if self.annotation and self.annotation.get_visible():
                    self.hide_annotation()
                return

        found_point = False
        min_dist_pixel_sq = (10)**2 
        closest_x_data, closest_y_data_on_line = None, None
        closest_line_label = None

        for line in ax_event.lines:
            if not line.get_visible(): continue
            x_data, y_data = line.get_data()
            if len(x_data) == 0: continue
            try:
                if event.xdata is None or event.ydata is None: continue
                xy_pixels_line = ax_event.transData.transform(np.vstack((x_data, y_data)).T)
                x_pixels_line, y_pixels_line = xy_pixels_line[:,0], xy_pixels_line[:,1]
                mouse_x_pixel, mouse_y_pixel = event.x, event.y
                distances_pixel_sq = (x_pixels_line - mouse_x_pixel)**2 + (y_pixels_line - mouse_y_pixel)**2
                if distances_pixel_sq.size > 0:
                    current_min_idx = np.nanargmin(distances_pixel_sq)
                    if np.isnan(distances_pixel_sq[current_min_idx]): continue
                    current_min_dist_pixel_sq = distances_pixel_sq[current_min_idx]
                    if current_min_dist_pixel_sq < min_dist_pixel_sq:
                        min_dist_pixel_sq = current_min_dist_pixel_sq
                        closest_x_data = x_data[current_min_idx]
                        closest_y_data_on_line = y_data[current_min_idx]
                        closest_line_label = line.get_label()
                        found_point = True
            except Exception: continue 

        if found_point:
            text = f"X: {closest_x_data:.3e}\nY: {closest_y_data_on_line:.3e}"
            if closest_line_label and not closest_line_label.startswith('_'):
                text = f"{closest_line_label}\n{text}"
            annotation_anchor_x = closest_x_data
            try:
                _, annotation_anchor_y = self.ax.transData.inverted().transform((event.x, event.y))
            except:
                 annotation_anchor_y = closest_y_data_on_line if ax_event == self.ax else self.ax.get_ylim()[0]
            self.update_annotation(annotation_anchor_x, annotation_anchor_y, text)
        else:
            if self.annotation and self.annotation.get_visible():
                 self.hide_annotation()

    def update_annotation(self, x, y, text):
        if not self.annotation: return
        self.annotation.xy = (x,y) 
        self.annotation.set_text(text)
        self.annotation.set_visible(True)
        if self.fig_canvas and self.fig_canvas.get_tk_widget().winfo_exists():
            try:
                self.fig_canvas.draw_idle()
            except tk.TclError: pass

class CrosshairFeature:
    """Manages a crosshair on a Matplotlib axes and updates status bar."""
    def __init__(self, app_instance, ax, fig_canvas, color='gray', linestyle=':', linewidth=0.7, useblit=False):
        self.app_instance = app_instance
        self.ax = ax
        self.fig_canvas = fig_canvas
        self.useblit = useblit
        self.background = None

        self.hline = matplotlib.lines.Line2D([], [], color=color, linestyle=linestyle, linewidth=linewidth, visible=False, animated=useblit)
        self.vline = matplotlib.lines.Line2D([], [], color=color, linestyle=linestyle, linewidth=linewidth, visible=False, animated=useblit)
        self.ax.add_line(self.hline)
        self.ax.add_line(self.vline)
        
        self.cid_motion = None
        self.cid_leave_axes = None
        self.cid_draw = None

    def connect(self):
        if self.fig_canvas:
            if self.cid_motion is None:
                self.cid_motion = self.fig_canvas.mpl_connect('motion_notify_event', self.on_motion)
            if self.cid_leave_axes is None:
                self.cid_leave_axes = self.fig_canvas.mpl_connect('axes_leave_event', self.on_leave_axes)
            if self.useblit and self.cid_draw is None:
                self.cid_draw = self.fig_canvas.mpl_connect('draw_event', self.on_draw)

    def disconnect(self):
        if self.fig_canvas:
            if self.cid_motion: self.fig_canvas.mpl_disconnect(self.cid_motion); self.cid_motion = None
            if self.cid_leave_axes: self.fig_canvas.mpl_disconnect(self.cid_leave_axes); self.cid_leave_axes = None
            if self.useblit and self.cid_draw: self.fig_canvas.mpl_disconnect(self.cid_draw); self.cid_draw = None
        self.hide()

    def on_draw(self, event):
        if self.useblit:
            self.background = self.fig_canvas.copy_from_bbox(self.ax.bbox)
            if self.hline.get_visible(): self.ax.draw_artist(self.hline)
            if self.vline.get_visible(): self.ax.draw_artist(self.vline)

    def on_motion(self, event):
        if not event.inaxes == self.ax:
            if self.hline.get_visible() or self.vline.get_visible():
                self.hide()
                set_status(self.app_instance, "准备就绪 (Ready)")
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            if self.hline.get_visible() or self.vline.get_visible(): self.hide()
            return

        self.hline.set_data(self.ax.get_xlim(), [y, y])
        self.vline.set_data([x, x], self.ax.get_ylim())
        
        if not self.hline.get_visible(): self.hline.set_visible(True)
        if not self.vline.get_visible(): self.vline.set_visible(True)

        set_status(self.app_instance, f"X: {x:.3f}, Y: {y:.4e}")

        if self.useblit and self.background is not None:
            self.fig_canvas.restore_region(self.background)
            self.ax.draw_artist(self.hline)
            self.ax.draw_artist(self.vline)
            self.fig_canvas.blit(self.ax.bbox)
        else: 
            self.fig_canvas.draw_idle()

    def on_leave_axes(self, event):
        if event.inaxes == self.ax:
            self.hide()
            set_status(self.app_instance, "准备就绪 (Ready)")

    def hide(self):
        was_visible = self.hline.get_visible() or self.vline.get_visible()
        self.hline.set_visible(False)
        self.vline.set_visible(False)
        if was_visible:
            if self.useblit and self.background is not None:
                self.fig_canvas.restore_region(self.background)
                self.fig_canvas.blit(self.ax.bbox)
            elif self.fig_canvas and self.fig_canvas.get_tk_widget().winfo_exists():
                try:
                    self.fig_canvas.draw_idle()
                except tk.TclError: pass

STYLE_CONFIG = {
    'font_title': ('TkDefaultFont', 11, 'bold'),
    'font_label': ('TkDefaultFont', 9),
    'font_button': ('TkDefaultFont', 10, 'bold'),
    'bg_frame': '#F8F9FA',
    'padx': 12, 'pady': 8, 'entry_width': 18,
    'entry_path_width': 40,
    'entry_bg_normal': 'white',
    'entry_bg_warning': 'lemon chiffon',
    'entry_bg_error': 'pink'
}

def param_entry_validator(app_instance, P, entry_widget_name, param_key, params_vars_dict=None, start_key=None, stop_key=None, step_key=None):
    try:
        entry_widget = app_instance.root.nametowidget(entry_widget_name)
    except tk.TclError:
        return True # Widget might not exist yet, allow

    valid_bg = STYLE_CONFIG['entry_bg_normal']
    warning_bg = STYLE_CONFIG['entry_bg_warning']
    error_bg = STYLE_CONFIG['entry_bg_error']
    current_bg = valid_bg

    if P == "": # Allow empty, might be handled by specific logic
        entry_widget.config(background=valid_bg)
        # If step is empty, reset related start/stop backgrounds if they are not in error
        if params_vars_dict and step_key == param_key:
            for k_related in [start_key, stop_key]:
                if k_related and params_vars_dict.get(k_related, {}).get("widget"):
                    related_widget = params_vars_dict[k_related]["widget"]
                    if related_widget.cget('background') != error_bg: # Don't clear actual errors
                         related_widget.config(background=valid_bg)
        return True

    try:
        val = float(P)
        # Specific validations
        if "Ilimit" in param_key:
            if val <= 0 or val > 10: current_bg = warning_bg # Example limit
        elif "nplc" in param_key.lower(): # Case-insensitive check for NPLC
            if not (0.001 <= val <= 60): current_bg = warning_bg
        elif step_key and param_key == step_key: # If this is a step entry
            # Special handling for Vg_step in Output Characteristics (number of segments)
            is_oc_vg_step = False
            if hasattr(app_instance, 'notebook') and app_instance.notebook: # Check if notebook exists
                try:
                    current_tab_text = app_instance.notebook.tab(app_instance.notebook.select(), "text")
                    if param_key == "Vg_step" and "Output Characteristics" in current_tab_text: 
                        is_oc_vg_step = True
                        # For OC Vg_step (segments), it must be an integer >= 0
                        if not val.is_integer() or val < 0:
                            current_bg = error_bg
                except tk.TclError: # Tab might not be selected or notebook not fully initialized
                    pass 
            
            if not is_oc_vg_step: # General step validation (not OC Vg_step)
                if val == 0 and params_vars_dict and start_key and stop_key:
                    start_val_str = params_vars_dict.get(start_key, {}).get("var", tk.StringVar()).get()
                    stop_val_str = params_vars_dict.get(stop_key, {}).get("var", tk.StringVar()).get()
                    if start_val_str and stop_val_str:
                        try:
                            if float(start_val_str) != float(stop_val_str):
                                current_bg = error_bg # Step is 0 but start != stop
                        except ValueError: pass # Ignore if start/stop are not valid floats yet
        
        # Cross-validation for start, stop, step
        if params_vars_dict and start_key and stop_key and step_key and \
           (param_key == start_key or param_key == stop_key or param_key == step_key):
            # Check if this is the Vg_step for Output Characteristics, which has different rules
            is_oc_vg_step_context = False
            if hasattr(app_instance, 'notebook') and app_instance.notebook:
                try:
                    current_tab_text = app_instance.notebook.tab(app_instance.notebook.select(), "text")
                    if param_key == "Vg_step" and "Output Characteristics" in current_tab_text:
                        is_oc_vg_step_context = True
                except tk.TclError:
                    pass

            if not is_oc_vg_step_context: # Apply general start/stop/step validation
                start_val_str = params_vars_dict.get(start_key, {}).get("var", tk.StringVar()).get()
                stop_val_str = params_vars_dict.get(stop_key, {}).get("var", tk.StringVar()).get()
                step_val_str = params_vars_dict.get(step_key, {}).get("var", tk.StringVar()).get()
                
                # Reset backgrounds of related fields if they are not in error state themselves
                start_widget = params_vars_dict.get(start_key, {}).get("widget")
                stop_widget = params_vars_dict.get(stop_key, {}).get("widget")
                step_widget_to_update = params_vars_dict.get(step_key, {}).get("widget") # The step widget itself

                widgets_to_reset_bg = []
                if param_key != start_key and start_widget: widgets_to_reset_bg.append(start_widget)
                if param_key != stop_key and stop_widget: widgets_to_reset_bg.append(stop_widget)
                if param_key != step_key and step_widget_to_update: widgets_to_reset_bg.append(step_widget_to_update)

                for w in widgets_to_reset_bg:
                     if w.cget('background') != error_bg : w.config(background=valid_bg)


                if start_val_str and stop_val_str and step_val_str: # If all three have values
                    try:
                        start_v, stop_v, step_v = float(start_val_str), float(stop_val_str), float(step_val_str)
                        widget_for_step_feedback = step_widget_to_update # Usually the step entry

                        if start_v != stop_v: # If it's a sweep
                            if step_v == 0:
                                if widget_for_step_feedback: widget_for_step_feedback.config(background=error_bg)
                                if param_key == step_key: current_bg = error_bg # Mark current step entry as error
                            elif (stop_v > start_v and step_v < 0) or \
                                 (stop_v < start_v and step_v > 0): # Sign mismatch
                                if widget_for_step_feedback: widget_for_step_feedback.config(background=warning_bg)
                                if param_key == step_key: current_bg = warning_bg
                            else: # Valid step sign
                                if widget_for_step_feedback and widget_for_step_feedback.cget('background') != error_bg : # Don't clear actual errors on step
                                    widget_for_step_feedback.config(background=valid_bg)
                        else: # start_v == stop_v (single point)
                            # Step can be anything (often 0 or non-zero for single point measurement definition)
                            # So, if start==stop, the step field itself usually doesn't need error/warning based on its own value.
                            if widget_for_step_feedback and widget_for_step_feedback.cget('background') != error_bg:
                                widget_for_step_feedback.config(background=valid_bg)
                    except ValueError:
                        pass # One of them is not a valid float, individual validation will handle it
        
        entry_widget.config(background=current_bg)
        return True
    except ValueError: # Current entry P is not a float
        entry_widget.config(background=error_bg)
        return True # Return True to allow focus out, visual feedback is enough

def create_param_frame(app_instance, parent_tab_frame, title, param_list_details, param_vars_dict, columns=2, entry_width=None, context_keys=None):
    style = STYLE_CONFIG
    param_group_frame = ttk.LabelFrame(parent_tab_frame, text=title, padding=(style['padx']-4, style['pady']-4)) if title else ttk.Frame(parent_tab_frame, padding=(style['padx']-4, style['pady']-4))
    param_group_frame.pack(fill=tk.X, expand=True, padx=style['padx']-2, pady=style['pady']-2, ipady=2)
    actual_entry_width = entry_width if entry_width is not None else style['entry_width']

    for i, (label_text, key, default_val_or_var) in enumerate(param_list_details):
        row, col_group = divmod(i, columns)
        lbl = ttk.Label(param_group_frame, text=label_text, font=style['font_label'])
        lbl.grid(row=row, column=col_group*2, sticky=tk.E, padx=(5,2), pady=3)
        
        # Check if default_val_or_var is already a StringVar (passed from main_app for mobility params)
        if isinstance(default_val_or_var, tk.StringVar):
            var = default_val_or_var
        else: # It's a default string value, create a new StringVar
            var = tk.StringVar(value=str(default_val_or_var)) # Ensure it's a string

        entry = tk.Entry(param_group_frame, textvariable=var, width=actual_entry_width, background=style['entry_bg_normal'])
        
        start_k = context_keys.get('start') if context_keys else None
        stop_k = context_keys.get('stop') if context_keys else None
        step_k = context_keys.get('step') if context_keys else None
        
        # Pass the correct dictionary of parameter variables for the current tab
        current_tab_param_vars = param_vars_dict 

        entry.bind("<FocusOut>", lambda event, e=entry, k=key, pv=current_tab_param_vars, sk=start_k, ek=stop_k, stk=step_k, app=app_instance: 
                   param_entry_validator(app, e.get(), str(e), k, pv, sk, ek, stk))
        entry.bind("<KeyRelease>", lambda event, e=entry, k=key, pv=current_tab_param_vars, sk=start_k, ek=stop_k, stk=step_k, app=app_instance: 
                   param_entry_validator(app, e.get(), str(e), k, pv, sk, ek, stk))

        entry.grid(row=row, column=col_group*2+1, sticky=tk.EW, padx=(0,10), pady=3)
        param_vars_dict[key] = {"var": var, "widget": entry} # Store var and widget
        param_group_frame.columnconfigure(col_group*2+1, weight=1)
        param_group_frame.columnconfigure(col_group*2, weight=0)
    return param_group_frame

def add_reset_button_to_tab(app_instance, tab_frame, params_vars_dict_with_widget, fields_structure_list, measurement_name):
    style = STYLE_CONFIG
    btn_frame = ttk.Frame(tab_frame)
    btn_frame.pack(fill=tk.X, pady=(5,10), padx=style['padx']-2)
    reset_button = ttk.Button(btn_frame, text="恢复默认值 (Reset to Defaults)", 
                              command=lambda pv=params_vars_dict_with_widget, fs=fields_structure_list, mn=measurement_name: 
                                  reset_params_to_default(app_instance, pv, fs, mn))
    reset_button.pack(side=tk.RIGHT, padx=5)

def reset_params_to_default(app_instance, params_vars_dict_with_widget, fields_structure_list, measurement_name):
    style = STYLE_CONFIG
    try:
        for _label, key, default_val_or_var in fields_structure_list:
            if key in params_vars_dict_with_widget:
                # If default_val_or_var is a StringVar itself (like for mobility params),
                # we need to get its default from config_settings.
                # Otherwise, it's the direct default string.
                default_to_set = ""
                if isinstance(default_val_or_var, tk.StringVar):
                    # This requires knowing the original default string from config_settings
                    # This part might need adjustment based on how defaults for StringVar-passed fields are stored/retrieved
                    # For now, assume it's a direct value if not a StringVar in fields_structure
                    # Let's find the original default string from config_settings based on the key
                    if measurement_name == "栅转移特性":
                        if key == "channel_length_um_gt": default_to_set = config_settings.GT_DEFAULT_CHANNEL_LENGTH_UM
                        elif key == "c_ox_nF_per_cm2_gt": default_to_set = config_settings.GT_DEFAULT_C_OX_NF_CM2
                        # Add more if other StringVar-passed defaults exist
                    # Add similar blocks for other measurement types if they pass StringVars in fields_structure
                else: # It's a direct default string value
                    default_to_set = str(default_val_or_var)

                params_vars_dict_with_widget[key]["var"].set(default_to_set)
                params_vars_dict_with_widget[key]["widget"].config(background=style['entry_bg_normal'])
        
        # Specific resets for checkboxes if needed
        if measurement_name == "栅转移特性" and hasattr(app_instance, 'gt_enable_backward'):
            app_instance.gt_enable_backward.set(True) # Default for GT
        if measurement_name == "二极管IV" and hasattr(app_instance, 'diode_enable_backward'):
            app_instance.diode_enable_backward.set(True) # Default for Diode

        # Re-validate all fields in this tab after reset
        # Need to find the correct context_keys for each group if they were used
        # This is a simplified re-validation. A more robust way would be to store context_keys with param_vars_dict
        for key_to_reval, data_dict_entry in params_vars_dict_with_widget.items():
            widget = data_dict_entry.get("widget")
            var = data_dict_entry.get("var")
            if widget and var:
                 # Find context keys for this specific key if applicable
                 # This is a simplification; a better approach would be to store context_keys with each param group
                 # or pass the full structure to param_entry_validator.
                 # For now, call without specific context_keys for cross-validation during reset.
                 param_entry_validator(app_instance, var.get(), str(widget), key_to_reval, params_vars_dict_with_widget)
        
        set_status(app_instance, f"{measurement_name} 参数已重置为默认值。(Parameters reset to default.)")
    except Exception as e:
        messagebox.showerror("重置错误 (Reset Error)", f"重置 {measurement_name} 参数时出错: {e}")
        set_status(app_instance, f"重置 {measurement_name} 参数失败。(Failed to reset parameters.)", error=True)

def toggle_device_parameter_input(app_instance):
    """ Toggles the state of device parameter input fields. """
    is_lateral = app_instance.device_type.get() == "lateral"
    # These are entry widgets for W and Area
    app_instance.entry_channel_width.config(state=tk.NORMAL if is_lateral else tk.DISABLED)
    app_instance.entry_area.config(state=tk.NORMAL if not is_lateral else tk.DISABLED)
    
    # These are the StringVars: channel_width_um and area_um2
    if not is_lateral: # Vertical selected
        # If vertical, W is typically not used or derived, clear or disable its input value
        app_instance.channel_width_um.set("") # Or set to a default like "0" or config_settings.DEVICE_DEFAULT_CHANNEL_WIDTH_UM
    else: # Lateral selected
        # If lateral, Area is typically not used, clear or disable its input value
        app_instance.area_um2.set("") # Or set to a default like "0" or config_settings.DEVICE_DEFAULT_AREA_UM2
    # The defaults from config_settings are already set when StringVars are initialized.
    # This function primarily handles enabling/disabling and potentially clearing the non-relevant field.


def browse_directory(app_instance):
    """ Opens a dialog to browse for an output directory. """
    dir_path = filedialog.askdirectory(initialdir=app_instance.output_dir.get())
    if dir_path:
        app_instance.output_dir.set(dir_path)
        if hasattr(app_instance, 'history_tab_handler_instance') and \
           hasattr(app_instance.history_tab_handler_instance, 'refresh_file_list'):
            app_instance.history_tab_handler_instance.refresh_file_list() 
        set_status(app_instance, f"输出目录已更改为: {dir_path}")

def validate_filename_base(filename_base):
    """Validates the base filename part (user input)."""
    if not filename_base: return True 
    if not re.match(r'^[\w\-\s]+$', filename_base): # Allow letters, numbers, underscore, hyphen, space
        messagebox.showerror("文件名错误", "基本文件名只能包含字母、数字、下划线、连字符和空格。")
        return False
    return True

def set_status(app_instance, message, error=False):
    """ Sets the status bar message. """
    if hasattr(app_instance, 'status_bar_label'):
        app_instance.status_bar_label.config(text=message)
        app_instance.status_bar_label.config(foreground="red" if error else "")
    # print(f"Status: {message}") # Also print to console for logging

def get_style():
    """Returns the style configuration dictionary."""
    return STYLE_CONFIG.copy()
