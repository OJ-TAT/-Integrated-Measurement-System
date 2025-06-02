# breakdown_module.py
import pyvisa
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime
import os
import sys
import traceback
import instrument_utils
import config_settings
from measurement_base import MeasurementBase
import plotting_utils

class BreakdownMeasurement(MeasurementBase):
    def __init__(self):
        super().__init__(measurement_type_name_short="Breakdown", plot_file_suffix="_linear_log.png")
        self.N_st = 0 # Number of Vd points

    def _get_tsp_script_path_key(self, config):
        return config_settings.CONFIG_KEY_TSP_BREAKDOWN

    def _get_default_tsp_script_path(self, config):
        return config_settings.DEFAULT_TSP_BREAKDOWN

    def _prepare_tsp_parameters(self, config):
        Vd_start = config['Vd_start']
        Vd_stop = config['Vd_stop']
        Vd_step_val = config['Vd_step']
        self.N_st = 1 # Default to 1 point if start == stop and step is 0
        if Vd_step_val == 0:
            if Vd_start != Vd_stop:
                raise ValueError("If Vd_start != Vd_stop, then Vd_step cannot be zero for Breakdown.")
        else: # Vd_step_val is not zero
            if (Vd_stop > Vd_start and Vd_step_val < 0) or \
               (Vd_stop < Vd_start and Vd_step_val > 0):
                raise ValueError(f"Vd voltage step ({Vd_step_val}V) sign mismatch with scan direction (from {Vd_start}V to {Vd_stop}V) for Breakdown.")
            self.N_st = int(round(abs(Vd_stop - Vd_start) / abs(Vd_step_val))) + 1

        return {
            "IlimitDrain": config['IlimitDrain'], "IlimitGate": config['IlimitGate'],
            "Drain_nplc": config['Drain_nplc'], "Gate_nplc": config['Gate_nplc'],
            "Vg": config['Vg'], "Vd_start": Vd_start, "Vd_stop": Vd_stop, "Vd_step": Vd_step_val,
            "settling_delay": config.get('settling_delay', config_settings.BD_DEFAULT_SETTLING_DELAY) # Added
        }

    def _get_primary_buffer_info(self, config):
        expected_total_points = self.N_st
        return config_settings.SMUA_NVBUFFER1, expected_total_points # Drain current buffer as primary

    def _get_buffers_to_read_config(self, config, buffer_read_count):
        return {
            'Time_gate': (config_settings.GATE_SMU_TIMESTAMP_BUFFER_PATH, buffer_read_count), # Using gate timestamp as primary time
            'Vg_read': (config_settings.GATE_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Vd_read': (config_settings.DRAIN_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Id': (config_settings.DRAIN_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Ig': (config_settings.GATE_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Is_buffer': (config_settings.SOURCE_SMU_IS_BUFFER_READINGS_PATH, buffer_read_count)
        }

    def _get_priority_keys_for_consistent_length(self):
        return ['Id', 'Vd_read'] # Id from drain SMU, Vd_read from drain SMU

    def _perform_specific_data_processing(self, config):
        # Vg_final is the actual Vg applied, should be constant from config['Vg']
        # but can also be read from Vg_read if available and consistent
        vg_read_data = self.processed_data.get('Vg_read')
        if isinstance(vg_read_data, np.ndarray) and vg_read_data.size == self.consistent_len and not np.all(np.isnan(vg_read_data)):
            # If Vg_read is good, use its mean as Vg_final for metadata, but individual points for data
            self.processed_data['Vg_final'] = vg_read_data # Store the array
        elif self.consistent_len > 0 :
            self.processed_data['Vg_final'] = np.full(self.consistent_len, config.get('Vg', np.nan))
        else: # consistent_len is 0
            self.processed_data['Vg_final'] = np.array([])

        # Use Time_gate as the primary time source if available
        if 'Time_gate' in self.processed_data and isinstance(self.processed_data['Time_gate'], np.ndarray) \
           and self.processed_data['Time_gate'].size == self.consistent_len:
            self.processed_data['Time'] = self.processed_data['Time_gate']
        elif 'Time' not in self.processed_data: # Ensure 'Time' key exists
             self.processed_data['Time'] = np.full(self.consistent_len, np.nan) if self.consistent_len > 0 else np.array([])


    def _get_csv_header_info(self, config):
        header_cols = ['Time', 'Vg_final', 'Vd_read', 'Id', 'Ig', 'Is', 'Jd', 'Jg', 'Js']
        header_str = (f"Time(s),Vg_actual(V),Vd_read(V),Id(A),Ig(A),Is(A),"
                      f"Jd({self.jd_unit_plot}),Jg({self.jd_unit_plot}),Js({self.jd_unit_plot})")
        return header_cols, header_str

    def _get_specific_metadata_comments(self, config):
        comments = ""
        comments += f"# Vg_set: {config.get('Vg', 'N/A')}\n"
        comments += f"# Vd_start (set): {config.get('Vd_start', 'N/A')}\n"
        comments += f"# Vd_stop (set): {config.get('Vd_stop', 'N/A')}\n"
        comments += f"# Vd_step (set): {config.get('Vd_step', 'N/A')}\n"
        comments += f"# Settling Delay (s): {config.get('settling_delay', 'N/A')}\n" # Added
        comments += f"# Num Vd points expected: {self.N_st}\n"
        # Add average Vg_read if available and different from Vg_set
        vg_final_data = self.processed_data.get('Vg_final', np.array([]))
        if vg_final_data.size > 0 and not np.all(np.isnan(vg_final_data)):
            avg_vg_read = np.nanmean(vg_final_data)
            if not np.isnan(avg_vg_read):
                 comments += f"# Avg Vg_read (V): {avg_vg_read:.3f}\n"
        return comments

    def _prepare_plot_data_package(self, config):
        # Determine Vg for title: use set Vg, but if Vg_final (from Vg_read) is valid, prefer its mean
        vg_for_title = config.get('Vg', np.nan)
        vg_final_data = self.processed_data.get('Vg_final', np.array([]))
        if vg_final_data.size > 0 and not np.all(np.isnan(vg_final_data)):
            avg_vg_read = np.nanmean(vg_final_data)
            if not np.isnan(avg_vg_read):
                vg_for_title = avg_vg_read

        return {
            "processed_data": self.processed_data,
            "Vg_set_for_title": vg_for_title, # Use the determined Vg for title
            "png_file_path": self.png_file_path,
            "csv_file_path": self.csv_file_path,
            "measurement_type_name": self.measurement_type_name_full,
            "status": "success_data_ready",
            "jd_unit_plot": self.jd_unit_plot
        }

def generate_breakdown_plot(plot_data_package):
    return plotting_utils.generate_plot_with_common_handling(
        plot_data_package,
        _plot_breakdown_figure_content
    )

def _plot_breakdown_figure_content(fig, plot_data_package):
    processed_data = plot_data_package['processed_data']
    vg_set_for_title = plot_data_package.get("Vg_set_for_title", np.nan)
    measurement_name = plot_data_package.get("measurement_type_name", "Breakdown Characteristics")

    ax1, ax2 = fig.subplots(2, 1, sharex=True) # Create 2 subplots, sharing x-axis

    vd_plot = processed_data.get('Vd_read', np.array([]))
    id_plot = processed_data.get('Id', np.array([]))
    ig_plot = processed_data.get('Ig', np.array([]))
    is_plot = processed_data.get('Is', np.array([]))

    has_data = vd_plot.size > 0 and \
               (id_plot.size == vd_plot.size or \
                ig_plot.size == vd_plot.size or \
                is_plot.size == vd_plot.size)

    plot_title_base = f'{measurement_name}'
    if not np.isnan(vg_set_for_title):
        plot_title_base += f' ($V_G \\approx$ {vg_set_for_title:.2f}V)' # Use approx if from Vg_read mean

    if not has_data:
        fig_text = f"{plot_title_base}\nNo valid data to plot"
        if plot_data_package.get('csv_file_path'): fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
        ax1.text(0.5, 0.5, fig_text, ha='center', va='center', transform=ax1.transAxes, fontsize=10, wrap=True)
        ax2.text(0.5, 0.5, "", ha='center', va='center', transform=ax2.transAxes) # Keep second plot blank
        ax1.set_title(plot_title_base + " - Linear Scale")
        ax2.set_title(plot_title_base + " - Log Scale") # Still show title for log scale
    else:
        # Linear plot (ax1)
        if id_plot.size == vd_plot.size and not np.all(np.isnan(id_plot)):
            ax1.plot(vd_plot, id_plot, color='blue', linestyle='-', marker='o', ms=3, label='$I_D$')
        if is_plot.size == vd_plot.size and not np.all(np.isnan(is_plot)):
            ax1.plot(vd_plot, is_plot, color='green', linestyle='-', marker='o', ms=3, label='$I_S$')
        if ig_plot.size == vd_plot.size and not np.all(np.isnan(ig_plot)):
            ax1.plot(vd_plot, ig_plot, color='red', linestyle='--', marker='None', label='$I_G$')

        ax1.set_ylabel('Current (A)')
        ax1.set_title(plot_title_base + ' - Linear Scale')
        ax1.grid(True, alpha=0.4)
        if ax1.lines: ax1.legend(loc="best")
        ax1.set_yscale('linear')

        # Log plot (ax2)
        # Plot absolute values for log scale, only if they are greater than a small threshold (e.g., 1e-14)
        if id_plot.size == vd_plot.size:
            id_abs = np.abs(id_plot)
            valid_log_id = (id_abs > 1e-14) & ~np.isnan(vd_plot)
            if np.any(valid_log_id):
                ax2.plot(vd_plot[valid_log_id], id_abs[valid_log_id], color='blue', linestyle='-', marker='o', ms=3, label='$|I_D|$')

        if is_plot.size == vd_plot.size:
            is_abs = np.abs(is_plot)
            valid_log_is = (is_abs > 1e-14) & ~np.isnan(vd_plot)
            if np.any(valid_log_is):
                ax2.plot(vd_plot[valid_log_is], is_abs[valid_log_is], color='green', linestyle='-', marker='o', ms=3, label='$|I_S|$')

        if ig_plot.size == vd_plot.size:
            ig_abs = np.abs(ig_plot)
            valid_log_ig = (ig_abs > 1e-14) & ~np.isnan(vd_plot)
            if np.any(valid_log_ig):
                ax2.plot(vd_plot[valid_log_ig], ig_abs[valid_log_ig], color='red', linestyle='--', marker='None', label='$|I_G|$')

        ax2.set_yscale('log')
        ax2.set_ylabel('|Current| (A)')
        ax2.set_xlabel('$V_D$ (V)') # X-label only on the bottom plot due to sharex
        ax2.set_title(plot_title_base + ' - Log Scale')
        ax2.grid(True, which="both", alpha=0.3) # Grid for both major and minor ticks on log scale
        if ax2.lines: ax2.legend(loc="best")

    # fig.suptitle(plot_title_base, fontsize=16, y=0.99) # suptitle might be redundant if subplots have titles
    fig.tight_layout(rect=[0,0,1,0.95]) # Adjust rect if suptitle is used and overlaps

@instrument_utils.handle_measurement_errors
def run_breakdown_measurement(config):
    config["measurement_type_name"] = "Breakdown Characteristics"
    GPIB_ADDRESS = config.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
    TIMEOUT = config.get(config_settings.CONFIG_KEY_TIMEOUT, config_settings.DEFAULT_TIMEOUT)
    bd_measurement = BreakdownMeasurement()
    with instrument_utils.visa_instrument(GPIB_ADDRESS, TIMEOUT, config["measurement_type_name"]) as inst:
        plot_data_package = bd_measurement.perform_measurement_flow(config, inst)
    return plot_data_package
