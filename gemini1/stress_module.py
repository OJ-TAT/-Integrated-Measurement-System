# stress_module.py
import numpy as np
import os
import sys # For sys.stderr in case of errors
import traceback # For detailed error tracebacks

import instrument_utils
import config_settings
from measurement_base import MeasurementBase
import plotting_utils

class StressMeasurement(MeasurementBase):
    def __init__(self):
        super().__init__(measurement_type_name_short="Stress", plot_file_suffix="_stress.png")
        self.num_expected_stress_points = 0

    def _get_tsp_script_path_key(self, config):
        return config_settings.CONFIG_KEY_TSP_STRESS

    def _get_default_tsp_script_path(self, config):
        return config_settings.DEFAULT_TSP_STRESS

    def _prepare_tsp_parameters(self, config):
        """
        Prepares parameters for the Stress.tsp script.
        Keys in the returned dict must match placeholders in Stress.tsp.
        """
        duration = config.get('stress_duration_val', float(config_settings.STRESS_DEFAULT_DURATION))
        interval = config.get('stress_measure_interval_val', float(config_settings.STRESS_DEFAULT_MEASURE_INTERVAL))
        initial_settling_delay = config.get('initial_settling_delay_stress', float(config_settings.STRESS_DEFAULT_INITIAL_SETTLING_DELAY)) # New

        if duration < 0: # Duration can be 0 for a single point measurement after initial settling
            raise ValueError("Stress duration must be non-negative.")
        if interval <= 0 and duration > 0: # Interval must be positive if duration > 0 for multiple points
            raise ValueError("Stress measurement interval must be positive if duration is positive.")
        if initial_settling_delay < 0:
            raise ValueError("Initial settling delay must be non-negative.")

        if duration == 0:
            self.num_expected_stress_points = 1 # Only the initial point after settling
        elif interval == 0 : # Duration > 0, interval is 0 -> effectively means 1 point at start, 1 at end.
             self.num_expected_stress_points = 2 # Initial point + one at the end of duration
        elif interval > 0 and duration > 0 :
            if interval > duration:
                # print(f"Warning: Stress measurement interval ({interval}s) is greater than duration ({duration}s). Only initial and one end measurement will occur.", file=sys.stderr)
                self.num_expected_stress_points = 2 # Initial point + one at the end of duration
            else:
                # Number of intervals + initial point at t=0
                self.num_expected_stress_points = int(duration / interval) + 1
                # If duration is not a perfect multiple of interval, one more point might be taken at the very end by the TSP script logic
                if duration % interval != 0:
                     self.num_expected_stress_points +=1 


        tsp_params = {
            "VD_stress_val": config.get('VD_stress_val', config_settings.STRESS_DEFAULT_VD_STRESS),
            "VG_stress_val": config.get('VG_stress_val', config_settings.STRESS_DEFAULT_VG_STRESS),
            "VS_stress_val": config.get('VS_stress_val', config_settings.STRESS_DEFAULT_VS_STRESS),
            "stress_duration_val": duration,
            "stress_measure_interval_val": interval if interval > 0 else duration, # Pass duration if interval is 0 for TSP logic
            "initial_settling_delay": initial_settling_delay, # New parameter
            "IlimitDrain_stress": config.get('IlimitDrain_stress', config_settings.STRESS_DEFAULT_ILIMIT_DRAIN),
            "IlimitGate_stress": config.get('IlimitGate_stress', config_settings.STRESS_DEFAULT_ILIMIT_GATE),
            "IlimitSource_stress": config.get('IlimitSource_stress', config_settings.STRESS_DEFAULT_ILIMIT_SOURCE),
            "Drain_nplc_stress": config.get('Drain_nplc_stress', config_settings.STRESS_DEFAULT_DRAIN_NPLC),
            "Gate_nplc_stress": config.get('Gate_nplc_stress', config_settings.STRESS_DEFAULT_GATE_NPLC),
            "Source_nplc_stress": config.get('Source_nplc_stress', config_settings.STRESS_DEFAULT_SOURCE_NPLC),
        }
        return tsp_params

    def _get_primary_buffer_info(self, config):
        """
        Returns the primary buffer object string for querying data count and the expected number of points.
        Stress.tsp uses smua.nvbuffer1.timestamps as the primary time source.
        """
        return config_settings.DRAIN_SMU_TIMESTAMP_BUFFER_PATH, self.num_expected_stress_points

    def _get_buffers_to_read_config(self, config, buffer_read_count):
        """
        Returns a dictionary defining which buffers to read and their expected counts.
        Keys are internal names, values are tuples of (TSP_buffer_path, count).
        """
        return {
            'Timestamp': (config_settings.DRAIN_SMU_TIMESTAMP_BUFFER_PATH, buffer_read_count), # Primary timestamp
            'Vd_read': (config_settings.DRAIN_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Id': (config_settings.DRAIN_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Vg_read': (config_settings.GATE_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Ig': (config_settings.GATE_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Vs_read': (config_settings.SOURCE_SMU_VS_BUFFER_READINGS_PATH, buffer_read_count),
            'Is_buffer': (config_settings.SOURCE_SMU_IS_BUFFER_READINGS_PATH, buffer_read_count), # Changed to Is_buffer
        }

    def _get_priority_keys_for_consistent_length(self):
        """
        Returns a list of keys to prioritize for determining consistent data length.
        """
        return ['Timestamp', 'Id', 'Vd_read']

    def _perform_specific_data_processing(self, config):
        """
        Performs any data processing specific to the stress measurement.
        The base class handles common processing like current density.
        For stress, we ensure 'Time' is relative if absolute timestamps were read.
        The base class now calls calculate_source_current, which will use 'Is_buffer'.
        """
        if 'Timestamp' in self.processed_data and isinstance(self.processed_data['Timestamp'], np.ndarray):
            ts_data = self.processed_data['Timestamp']
            if ts_data.size > 0 and not np.all(np.isnan(ts_data)):
                # The TSP script with timer.reset() should provide relative time.
                # If initial_settling_delay was used, the first timestamp might be around that value.
                # To make 'Time' start from the beginning of the actual stress period (after initial settling),
                # we can subtract the first valid timestamp.
                first_valid_ts = ts_data[~np.isnan(ts_data)][0] if np.any(~np.isnan(ts_data)) else 0
                self.processed_data['Time'] = ts_data - first_valid_ts
            elif 'Time' not in self.processed_data :
                 self.processed_data['Time'] = np.full(self.consistent_len, np.nan) if self.consistent_len > 0 else np.array([])
        elif 'Time' not in self.processed_data:
            self.processed_data['Time'] = np.full(self.consistent_len, np.nan) if self.consistent_len > 0 else np.array([])

    def _get_csv_header_info(self, config):
        """
        Returns the CSV header column keys (list) and the header string.
        """
        header_cols = ['Time', 'Vd_read', 'Id', 'Vg_read', 'Ig', 'Vs_read', 'Is'] # 'Is' is now calculated or from buffer by base
        header_str_parts = ["Time(s)", "Vd_read(V)", "Id(A)", "Vg_read(V)", "Ig(A)", "Vs_read(V)", "Is(A)"]
        
        device_type = config.get('device_type', 'unknown')
        channel_width_um = config.get('channel_width_um', 0)
        area_um2 = config.get('area_um2', 0)
        jd_unit = "A.U."
        if device_type == "lateral" and channel_width_um > 0: jd_unit = 'mA/mm'
        elif device_type == "vertical" and area_um2 > 0: jd_unit = 'A/cm^2'

        if jd_unit != "A.U.":
            header_cols.extend(['Jd', 'Jg', 'Js'])
            header_str_parts.extend([f"Jd({jd_unit})", f"Jg({jd_unit})", f"Js({jd_unit})"])
            
        header_str = ",".join(header_str_parts)
        return header_cols, header_str

    def _get_specific_metadata_comments(self, config):
        """
        Returns a string of comments specific to this measurement type for CSV metadata.
        """
        comments = ""
        comments += f"# VD_stress_val (set, V): {config.get('VD_stress_val', 'N/A')}\n"
        comments += f"# VG_stress_val (set, V): {config.get('VG_stress_val', 'N/A')}\n"
        comments += f"# VS_stress_val (set, V): {config.get('VS_stress_val', 'N/A')}\n"
        comments += f"# Stress Duration (set, s): {config.get('stress_duration_val', 'N/A')}\n"
        comments += f"# Stress Measure Interval (set, s): {config.get('stress_measure_interval_val', 'N/A')}\n"
        comments += f"# Initial Settling Delay (set, s): {config.get('initial_settling_delay_stress', 'N/A')}\n" # New
        comments += f"# Expected Stress Data Points: {self.num_expected_stress_points}\n"
        comments += f"# IlimitDrain_stress (set, A): {config.get('IlimitDrain_stress', 'N/A')}\n"
        comments += f"# IlimitGate_stress (set, A): {config.get('IlimitGate_stress', 'N/A')}\n"
        comments += f"# IlimitSource_stress (set, A): {config.get('IlimitSource_stress', 'N/A')}\n"
        comments += f"# Drain_nplc_stress (set): {config.get('Drain_nplc_stress', 'N/A')}\n"
        comments += f"# Gate_nplc_stress (set): {config.get('Gate_nplc_stress', 'N/A')}\n"
        comments += f"# Source_nplc_stress (set): {config.get('Source_nplc_stress', 'N/A')}\n"
        return comments

    def _prepare_plot_data_package(self, config):
        """
        Prepares a dictionary of data needed for plotting the stress measurement.
        """
        return {
            "processed_data": self.processed_data,
            "png_file_path": self.png_file_path,
            "csv_file_path": self.csv_file_path,
            "measurement_type_name": self.measurement_type_name_full,
            "status": "success_data_ready",
            "jd_unit_plot": self.jd_unit_plot,
            "VD_stress_val": config.get('VD_stress_val'),
            "VG_stress_val": config.get('VG_stress_val'),
            "VS_stress_val": config.get('VS_stress_val'),
            "stress_duration_val": config.get('stress_duration_val')
        }

def generate_stress_plot(plot_data_package):
    """
    Generates and saves a plot for the stress measurement data.
    """
    return plotting_utils.generate_plot_with_common_handling(
        plot_data_package,
        _plot_stress_figure_content
    )

def _plot_stress_figure_content(fig, plot_data_package):
    """
    Specific plotting logic for stress data. Plots Vd, Id, Vg, Ig, Vs, Is vs. Time.
    """
    processed_data = plot_data_package['processed_data']
    measurement_name = plot_data_package.get("measurement_type_name", "Stress Test")
    
    time_data = processed_data.get('Time', np.array([]))
    vd_data = processed_data.get('Vd_read', np.array([]))
    id_data = processed_data.get('Id', np.array([]))
    vg_data = processed_data.get('Vg_read', np.array([]))
    ig_data = processed_data.get('Ig', np.array([]))
    vs_data = processed_data.get('Vs_read', np.array([]))
    is_data = processed_data.get('Is', np.array([])) # Now 'Is' is consistently populated by MeasurementBase

    ax_volt = fig.add_subplot(3, 1, 1)
    ax_curr_lin = fig.add_subplot(3, 1, 2, sharex=ax_volt)
    ax_curr_log = fig.add_subplot(3, 1, 3, sharex=ax_volt)

    if time_data.size > 0:
        valid_time_indices = ~np.isnan(time_data)
        
        if vd_data.size == time_data.size and not np.all(np.isnan(vd_data[valid_time_indices])):
            ax_volt.plot(time_data[valid_time_indices], vd_data[valid_time_indices], label='$V_D$', marker='.', linestyle='-', markersize=4)
        if vg_data.size == time_data.size and not np.all(np.isnan(vg_data[valid_time_indices])):
            ax_volt.plot(time_data[valid_time_indices], vg_data[valid_time_indices], label='$V_G$', marker='.', linestyle='-', markersize=4)
        if vs_data.size == time_data.size and not np.all(np.isnan(vs_data[valid_time_indices])):
            ax_volt.plot(time_data[valid_time_indices], vs_data[valid_time_indices], label='$V_S$', marker='.', linestyle='-', markersize=4)
    ax_volt.set_ylabel('Voltage (V)')
    ax_volt.set_title(f'{measurement_name}: Voltages vs. Time')
    ax_volt.grid(True, alpha=0.4)
    if ax_volt.lines: ax_volt.legend(loc='best', fontsize='small')

    if time_data.size > 0:
        valid_time_indices = ~np.isnan(time_data)
        if id_data.size == time_data.size and not np.all(np.isnan(id_data[valid_time_indices])):
            ax_curr_lin.plot(time_data[valid_time_indices], id_data[valid_time_indices], label='$I_D$', marker='.', linestyle='-', markersize=4)
        if ig_data.size == time_data.size and not np.all(np.isnan(ig_data[valid_time_indices])):
            ax_curr_lin.plot(time_data[valid_time_indices], ig_data[valid_time_indices], label='$I_G$', marker='.', linestyle='-', markersize=4)
        if is_data.size == time_data.size and not np.all(np.isnan(is_data[valid_time_indices])): # Check Is
            ax_curr_lin.plot(time_data[valid_time_indices], is_data[valid_time_indices], label='$I_S$', marker='.', linestyle='-', markersize=4)
    ax_curr_lin.set_ylabel('Current (A)')
    ax_curr_lin.set_title('Currents vs. Time (Linear Scale)')
    ax_curr_lin.grid(True, alpha=0.4)
    if ax_curr_lin.lines: ax_curr_lin.legend(loc='best', fontsize='small')
    ax_curr_lin.set_yscale('linear')

    if time_data.size > 0:
        valid_time_indices = ~np.isnan(time_data)
        min_current_for_log = 1e-13
        if id_data.size == time_data.size:
            id_abs = np.abs(id_data[valid_time_indices])
            valid_id_log = (id_abs >= min_current_for_log)
            if np.any(valid_id_log):
                 ax_curr_log.plot(time_data[valid_time_indices][valid_id_log], id_abs[valid_id_log], label='$|I_D|$', marker='.', linestyle='-', markersize=4)
        if ig_data.size == time_data.size:
            ig_abs = np.abs(ig_data[valid_time_indices])
            valid_ig_log = (ig_abs >= min_current_for_log)
            if np.any(valid_ig_log):
                 ax_curr_log.plot(time_data[valid_time_indices][valid_ig_log], ig_abs[valid_ig_log], label='$|I_G|$', marker='.', linestyle='-', markersize=4)
        if is_data.size == time_data.size: # Check Is
            is_abs = np.abs(is_data[valid_time_indices])
            valid_is_log = (is_abs >= min_current_for_log)
            if np.any(valid_is_log):
                ax_curr_log.plot(time_data[valid_time_indices][valid_is_log], is_abs[valid_is_log], label='$|I_S|$', marker='.', linestyle='-', markersize=4)

    ax_curr_log.set_xlabel('Time (s)')
    ax_curr_log.set_ylabel('$|$Current$|$ (A)')
    ax_curr_log.set_title('Currents vs. Time (Log Scale)')
    ax_curr_log.grid(True, which="both", alpha=0.3)
    if ax_curr_log.lines: ax_curr_log.legend(loc='best', fontsize='small')
    ax_curr_log.set_yscale('log')
    
    stress_duration_val = plot_data_package.get('stress_duration_val')
    if stress_duration_val is not None and time_data.size > 0 and np.any(~np.isnan(time_data)):
        max_time_data = np.nanmax(time_data[~np.isnan(time_data)])
        max_time_limit = max(float(stress_duration_val) * 1.05, max_time_data * 1.05) # Ensure x-axis covers at least the data or the duration
        min_time_data = np.nanmin(time_data[~np.isnan(time_data)])
        min_time_limit = min(0, min_time_data - max_time_limit * 0.02) # Start from 0 or slightly before data
        if max_time_limit > min_time_limit:
            ax_volt.set_xlim(left=min_time_limit, right=max_time_limit)
    
    if not (ax_volt.lines or ax_curr_lin.lines or ax_curr_log.lines):
        fig.clear()
        fig_text = f"{measurement_name}\nNo valid data to plot"
        if plot_data_package.get('csv_file_path'):
            fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
        fig.text(0.5, 0.5, fig_text, ha='center', va='center', fontsize=12, transform=fig.transFigure)
        return

    try:
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    except Exception:
        pass

@instrument_utils.handle_measurement_errors
def run_stress_measurement(config):
    config["measurement_type_name"] = "Stress Test"
    GPIB_ADDRESS = config.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
    TIMEOUT = config.get(config_settings.CONFIG_KEY_TIMEOUT, getattr(config_settings, 'STRESS_TIMEOUT', config_settings.DEFAULT_TIMEOUT))

    stress_measurement_instance = StressMeasurement() # Renamed to avoid conflict
    with instrument_utils.visa_instrument(GPIB_ADDRESS, TIMEOUT, config["measurement_type_name"]) as inst:
        plot_data_package = stress_measurement_instance.perform_measurement_flow(config, inst)
    return plot_data_package
