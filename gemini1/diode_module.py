# diode_module.py
import pyvisa
import numpy as np
import matplotlib
import matplotlib.pyplot as plt # Module-level import
from datetime import datetime
import os
import sys
import traceback
import instrument_utils
import config_settings
from measurement_base import MeasurementBase
import plotting_utils

def _split_diode_data_internal(data_dict, num_points_forward):
    forward_data = {}
    backward_data = {}

    for key_init in data_dict.keys(): # Initialize with empty arrays
        forward_data[key_init] = np.array([])
        backward_data[key_init] = np.array([])

    if num_points_forward <= 0: # If no forward points expected, assume all data is forward
        for key, full_array in data_dict.items():
            if isinstance(full_array, np.ndarray):
                forward_data[key] = full_array
        return forward_data, backward_data

    for key, full_array in data_dict.items():
        if not isinstance(full_array, np.ndarray):
            continue

        actual_len = len(full_array)

        # Assign forward part
        if actual_len >= num_points_forward:
            forward_data[key] = full_array[:num_points_forward]
        elif actual_len > 0 : # Data is shorter than expected for forward sweep
            forward_data[key] = full_array
        # else: forward_data[key] remains empty if actual_len is 0

        # Assign backward part
        if actual_len > num_points_forward: # If there's any data beyond the forward part
            # Backward sweep can be at most num_points_forward long, or shorter if data ends
            backward_part_len = min(num_points_forward, actual_len - num_points_forward)
            if backward_part_len > 0:
                 backward_data[key] = full_array[num_points_forward : num_points_forward + backward_part_len]
        # else: backward_data[key] remains empty

    return forward_data, backward_data


class DiodeMeasurement(MeasurementBase):
    def __init__(self):
        super().__init__(measurement_type_name_short="Diode", plot_file_suffix=".png")
        self.num_points_per_sweep = 0

    def _get_tsp_script_path_key(self, config):
        return config_settings.CONFIG_KEY_TSP_DIODE

    def _get_default_tsp_script_path(self, config):
        return config_settings.DEFAULT_TSP_DIODE

    def _prepare_tsp_parameters(self, config):
        Vanode_start = config['Vanode_start']
        Vanode_stop = config['Vanode_stop']
        Vanode_step = config['Vanode_step']
        enable_backward = config.get('enable_backward', False)

        self.num_points_per_sweep = 1 # Default for single point
        if Vanode_step != 0:
            if Vanode_start == Vanode_stop: # Single point measurement
                 self.num_points_per_sweep = 1
            else: # Sweep
                self.num_points_per_sweep = int(round(abs(Vanode_stop - Vanode_start) / abs(Vanode_step))) + 1
        elif Vanode_start != Vanode_stop: # Step is 0 but start != stop
            raise ValueError("If Vanode_start != Vanode_stop, then Vanode_step cannot be zero for Diode measurement.")

        return {
            'Vanode_start': Vanode_start,
            'Vanode_stop': Vanode_stop,
            'Vanode_step': Vanode_step,
            'IlimitAnode': config['IlimitAnode'],
            'IlimitCathode': config['IlimitCathode'],
            'Anode_nplc': config['Anode_nplc'],
            'Cathode_nplc': config['Cathode_nplc'],
            'enable_backward': "1" if enable_backward else "0",
            "settling_delay": config.get('settling_delay', config_settings.DIODE_DEFAULT_SETTLING_DELAY) # Added
        }

    def _get_primary_buffer_info(self, config):
        expected_total_points = self.num_points_per_sweep
        if config.get('enable_backward', False):
            expected_total_points *= 2
        # Anode current buffer is primary for determining points
        return config_settings.SMUA_NVBUFFER1, expected_total_points

    def _get_buffers_to_read_config(self, config, buffer_read_count):
        return {
            'time_abs': (config_settings.ANODE_TIMESTAMP_BUFFER_PATH, buffer_read_count),
            'anode_voltage_set': (config_settings.ANODE_VOLTAGE_SET_BUFFER_PATH, buffer_read_count),
            'anode_voltage_read': (config_settings.ANODE_VOLTAGE_READ_BUFFER_PATH, buffer_read_count),
            'anode_current': (config_settings.ANODE_CURRENT_READ_BUFFER_PATH, buffer_read_count),
            'cathode_current_buffer': (config_settings.CATHODE_CURRENT_READ_BUFFER_PATH, buffer_read_count)
        }

    def _get_priority_keys_for_consistent_length(self):
        # Prioritize buffers that are most critical for defining a valid data point
        return ['anode_current', 'anode_voltage_read', 'anode_voltage_set']


    def _perform_specific_data_processing(self, config):
        # Calculate relative time from absolute timestamps
        if self.consistent_len > 0 and 'time_abs' in self.processed_data and \
           isinstance(self.processed_data['time_abs'], np.ndarray) and \
           not np.all(np.isnan(self.processed_data['time_abs'])): # Check for all NaNs

            time_abs_valid = self.processed_data['time_abs'][~np.isnan(self.processed_data['time_abs'])]
            start_time = np.min(time_abs_valid) if time_abs_valid.size > 0 else 0
            self.processed_data['Time'] = self.processed_data['time_abs'] - start_time
        elif 'Time' not in self.processed_data: # Ensure 'Time' key exists
            self.processed_data['Time'] = np.full(self.consistent_len, np.nan) if self.consistent_len > 0 else np.array([])

        # Note: Current density calculation is handled by MeasurementBase's _perform_common_data_processing
        # No specific current density calculation here unless Diode has unique needs not covered by base.

    def _get_csv_header_info(self, config):
        header_cols_ordered = ['Time', 'anode_voltage_set', 'anode_voltage_read', 'anode_current']
        csv_header_list = ["Time(s)", "VAnode_set(V)", "VAnode_read(V)", "IAnode(A)"]

        # Conditionally add cathode current if it's valid and present
        if 'cathode_current_buffer' in self.processed_data and \
           isinstance(self.processed_data['cathode_current_buffer'], np.ndarray) and \
           self.processed_data['cathode_current_buffer'].size == self.consistent_len and \
           not np.all(np.isnan(self.processed_data['cathode_current_buffer'])): # Check for all NaNs
            header_cols_ordered.append('cathode_current_buffer')
            csv_header_list.append("ICathode_buffer(A)")

        csv_header_base = ",".join(csv_header_list)
        return header_cols_ordered, csv_header_base

    def _get_specific_metadata_comments(self, config):
        comments = ""
        comments += f"# Vanode_start (set): {config.get('Vanode_start', 'N/A')}\n"
        comments += f"# Vanode_stop (set): {config.get('Vanode_stop', 'N/A')}\n"
        comments += f"# Vanode_step (set): {config.get('Vanode_step', 'N/A')}\n"
        comments += f"# Enable Backward: {config.get('enable_backward', False)}\n"
        comments += f"# Settling Delay (s): {config.get('settling_delay', 'N/A')}\n" # Added
        comments += f"# Num Points Fwd Expected: {self.num_points_per_sweep}\n"
        return comments

    def _prepare_plot_data_package(self, config):
        # Determine which voltage data to use for plotting (prefer read, fallback to set)
        voltage_for_plot_key = 'anode_voltage_read'
        if not ('anode_voltage_read' in self.processed_data and \
                isinstance(self.processed_data['anode_voltage_read'], np.ndarray) and \
                self.processed_data['anode_voltage_read'].size == self.consistent_len and \
                not np.all(np.isnan(self.processed_data['anode_voltage_read']))):
            voltage_for_plot_key = 'anode_voltage_set'

        # Prepare data for potential splitting into forward/backward sweeps
        temp_plot_data_for_splitting = {
            'voltage_plot': self.processed_data.get(voltage_for_plot_key, np.array([])),
            'anode_current_plot': self.processed_data.get('anode_current', np.array([])),
            'cathode_current_plot': self.processed_data.get('cathode_current_buffer', np.array([]))
        }

        forward_plot_data = {}
        backward_plot_data = {}
        actual_enable_backward_for_plot = False # Flag to indicate if backward data is valid for plotting

        if config.get('enable_backward', False) and self.consistent_len > 0:
            forward_plot_data, backward_plot_data = _split_diode_data_internal(
                temp_plot_data_for_splitting, self.num_points_per_sweep
            )

            # Check if backward data is actually usable for plotting
            bwd_v_plot = backward_plot_data.get('voltage_plot', np.array([]))
            if bwd_v_plot.size > 0 and \
               (backward_plot_data.get('anode_current_plot', np.array([])).size == bwd_v_plot.size or \
                backward_plot_data.get('cathode_current_plot', np.array([])).size == bwd_v_plot.size):
                actual_enable_backward_for_plot = True
            else: # If backward voltage is empty, or currents don't match, revert to all-forward
                if not (forward_plot_data.get('voltage_plot', np.array([])).size > 0): # If fwd also became empty
                     forward_plot_data = temp_plot_data_for_splitting # Use original full data as forward
        else: # Not enabled backward, or no data
            forward_plot_data = temp_plot_data_for_splitting


        return {
            "forward_plot_data": forward_plot_data,
            "backward_plot_data": backward_plot_data,
            "enable_backward_plot": actual_enable_backward_for_plot,
            "png_file_path": self.png_file_path,
            "csv_file_path": self.csv_file_path,
            "measurement_type_name": self.measurement_type_name_full,
            "status": "success_data_ready"
        }

def generate_diode_plot(plot_data_package):
    return plotting_utils.generate_plot_with_common_handling(
        plot_data_package,
        _plot_diode_figure_content
    )

def _plot_diode_figure_content(fig, plot_data_package):
    forward_plot_data = plot_data_package.get('forward_plot_data', {})
    backward_plot_data = plot_data_package.get('backward_plot_data', {})
    enable_backward_plot = plot_data_package.get('enable_backward_plot', False)
    measurement_name = plot_data_package.get("measurement_type_name", "Diode Characterization")

    ax1 = fig.add_subplot(1, 2, 1) # Linear scale
    ax2 = fig.add_subplot(1, 2, 2) # Log scale

    # --- Plotting Forward Sweep Data ---
    fwd_v = forward_plot_data.get('voltage_plot', np.array([]))
    fwd_ia = forward_plot_data.get('anode_current_plot', np.array([]))
    fwd_ic = forward_plot_data.get('cathode_current_plot', np.array([]))

    has_fwd_ia_data = fwd_v.size > 0 and fwd_ia.size == fwd_v.size and not np.all(np.isnan(fwd_ia))
    has_fwd_ic_data = fwd_v.size > 0 and fwd_ic.size == fwd_v.size and not np.all(np.isnan(fwd_ic))

    if has_fwd_ia_data:
        ax1.plot(fwd_v, fwd_ia, color='blue', linestyle='-', marker='o', markersize=3, linewidth=1, label='Forward $I_{Anode}$')
    if has_fwd_ic_data:
        ax1.plot(fwd_v, fwd_ic, color='red', linestyle='-', marker='o', markersize=3, linewidth=1, label='Forward $I_{Cathode}$')

    if has_fwd_ia_data:
        fwd_ia_abs = np.abs(fwd_ia); valid_log_fwd_ia = (fwd_ia_abs > 1e-14) & (~np.isnan(fwd_v))
        if np.any(valid_log_fwd_ia):
            ax2.semilogy(fwd_v[valid_log_fwd_ia], fwd_ia_abs[valid_log_fwd_ia],
                         color='blue', linestyle='-', marker='o', markersize=3, linewidth=1, label='Forward $|I_{Anode}|$')
    if has_fwd_ic_data:
        fwd_ic_abs = np.abs(fwd_ic); valid_log_fwd_ic = (fwd_ic_abs > 1e-14) & (~np.isnan(fwd_v))
        if np.any(valid_log_fwd_ic):
            ax2.semilogy(fwd_v[valid_log_fwd_ic], fwd_ic_abs[valid_log_fwd_ic],
                         color='red', linestyle='-', marker='o', markersize=3, linewidth=1, label='Forward $|I_{Cathode}|$')

    # --- Plotting Backward Sweep Data (if enabled and valid) ---
    if enable_backward_plot:
        bwd_v = backward_plot_data.get('voltage_plot', np.array([]))
        bwd_ia = backward_plot_data.get('anode_current_plot', np.array([]))
        bwd_ic = backward_plot_data.get('cathode_current_plot', np.array([]))

        has_bwd_ia_data = bwd_v.size > 0 and bwd_ia.size == bwd_v.size and not np.all(np.isnan(bwd_ia))
        has_bwd_ic_data = bwd_v.size > 0 and bwd_ic.size == bwd_v.size and not np.all(np.isnan(bwd_ic))

        if has_bwd_ia_data:
            ax1.plot(bwd_v, bwd_ia, color='deepskyblue', linestyle='--', marker='s', markersize=3, linewidth=1, label='Backward $I_{Anode}$', alpha=0.7)
        if has_bwd_ic_data:
            ax1.plot(bwd_v, bwd_ic, color='lightcoral', linestyle='--', marker='s', markersize=3, linewidth=1, label='Backward $I_{Cathode}$', alpha=0.7)

        if has_bwd_ia_data:
            bwd_ia_abs = np.abs(bwd_ia); valid_log_bwd_ia = (bwd_ia_abs > 1e-14) & (~np.isnan(bwd_v))
            if np.any(valid_log_bwd_ia):
                ax2.semilogy(bwd_v[valid_log_bwd_ia], bwd_ia_abs[valid_log_bwd_ia],
                             color='deepskyblue', linestyle='--', marker='s', markersize=3, linewidth=1, label='Backward $|I_{Anode}|$', alpha=0.7)
        if has_bwd_ic_data:
            bwd_ic_abs = np.abs(bwd_ic); valid_log_bwd_ic = (bwd_ic_abs > 1e-14) & (~np.isnan(bwd_v))
            if np.any(valid_log_bwd_ic):
                ax2.semilogy(bwd_v[valid_log_bwd_ic], bwd_ic_abs[valid_log_bwd_ic],
                             color='lightcoral', linestyle='--', marker='s', markersize=3, linewidth=1, label='Backward $|I_{Cathode}|$', alpha=0.7)

    # --- Axes Formatting ---
    ax1.set_xlabel('Voltage (V)'); ax1.set_ylabel('Current (A)')
    ax1.set_title('Linear Scale Currents'); ax1.grid(True, alpha=0.4)
    if ax1.lines: ax1.legend(loc="best")
    ax1.set_yscale('linear')

    ax2.set_xlabel('Voltage (V)'); ax2.set_ylabel('$|Current|$ (A)')
    ax2.set_title('Semi-log Scale Currents'); ax2.grid(True, which="both", alpha=0.3)
    if ax2.lines: ax2.legend(loc="best")
    ax2.set_yscale('log')

    if not (ax1.lines or ax2.lines): # If no data was plotted on either axis
        fig_text = f"{measurement_name}\nNo valid data to plot"
        if plot_data_package.get('csv_file_path'): fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
        ax1.text(0.5,0.5, fig_text, ha='center', va='center', transform=ax1.transAxes, fontsize=10, wrap=True)
        ax2.text(0.5,0.5, "", ha='center', va='center', transform=ax2.transAxes) # Keep second plot blank if first has error text

    fig.suptitle(f'{measurement_name} Curve', fontsize=16, y=1.02) # Adjusted y for suptitle
    fig.tight_layout(rect=[0,0,1,0.97]) # Adjust rect for suptitle

@instrument_utils.handle_measurement_errors
def run_diode_measurement(config):
    config["measurement_type_name"] = "Diode Characterization"
    GPIB_ADDRESS = config.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
    TIMEOUT = config.get(config_settings.CONFIG_KEY_TIMEOUT, config_settings.DIODE_TIMEOUT) # Use specific diode timeout

    diode_measurement = DiodeMeasurement()
    with instrument_utils.visa_instrument(GPIB_ADDRESS, TIMEOUT, config["measurement_type_name"]) as inst:
        plot_data_package = diode_measurement.perform_measurement_flow(config, inst)
    return plot_data_package
