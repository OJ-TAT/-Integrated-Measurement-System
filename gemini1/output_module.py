# output_module.py
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

class OutputMeasurement(MeasurementBase):
    def __init__(self):
        super().__init__(measurement_type_name_short="Output", plot_file_suffix=".png")
        self.num_actual_vg_points = 0
        self.N_st_for_tsp = 0
        self.vd_voltage_step_for_tsp = 0

    def _get_tsp_script_path_key(self, config):
        return config_settings.CONFIG_KEY_TSP_OUTPUT

    def _get_default_tsp_script_path(self, config):
        return config_settings.DEFAULT_TSP_OUTPUT_CHAR

    def _prepare_tsp_parameters(self, config):
        Vg_start = config['Vg_start']
        Vg_stop = config['Vg_stop']
        vg_scan_segments_from_gui = int(config['Vg_step']) # Vg_step from GUI is number of segments
        Vd_start = config['Vd_start']
        Vd_stop = config['Vd_stop']
        self.vd_voltage_step_for_tsp = config['Vd_step'] # Vd_step from GUI is actual step value

        calculated_vg_voltage_step_for_tsp_sg = 0.0
        if Vg_start != Vg_stop:
            if vg_scan_segments_from_gui <= 0:
                raise ValueError(f"If Vg_start ({Vg_start}V) != Vg_stop ({Vg_stop}V), Vg scan segments ({vg_scan_segments_from_gui}) must be > 0.")
            calculated_vg_voltage_step_for_tsp_sg = (Vg_stop - Vg_start) / vg_scan_segments_from_gui
        elif vg_scan_segments_from_gui != 0 :
             raise ValueError(f"For single Vg point (Vg_start ({Vg_start}V) == Vg_stop ({Vg_stop}V)), Vg scan segments ({vg_scan_segments_from_gui}) must be 0.")

        # For TSP, Vg_step is the number of iterations (segments)
        vg_loop_iterations_for_tsp_vg_step = vg_scan_segments_from_gui
        self.num_actual_vg_points = vg_scan_segments_from_gui + 1 # Actual number of Vg points measured
        if Vg_start == Vg_stop: # Single Vg point
            self.num_actual_vg_points = 1


        self.N_st_for_tsp = 1 # Number of Vd points for TSP
        if self.vd_voltage_step_for_tsp == 0:
            if Vd_start != Vd_stop:
                raise ValueError("If Vd_start != Vd_stop, then Vd_step (vd_voltage_step_for_tsp) cannot be zero.")
        else:
            if (Vd_stop > Vd_start and self.vd_voltage_step_for_tsp < 0) or \
               (Vd_stop < Vd_start and self.vd_voltage_step_for_tsp > 0):
                raise ValueError(f"Vd voltage step ({self.vd_voltage_step_for_tsp}V) sign mismatch with scan direction (from {Vd_start}V to {Vd_stop}V).")
            self.N_st_for_tsp = int(round(abs(Vd_stop - Vd_start) / abs(self.vd_voltage_step_for_tsp))) + 1

        return {
            "IlimitDrain": config['IlimitDrain'], "IlimitGate": config['IlimitGate'],
            "Drain_nplc": config['Drain_nplc'], "Gate_nplc": config['Gate_nplc'],
            "Vg_start": Vg_start, "Vg_stop": Vg_stop, "sg": calculated_vg_voltage_step_for_tsp_sg,
            "Vg_step": vg_loop_iterations_for_tsp_vg_step, # This is number of Vg segments for TSP loop
            "Vd_start": Vd_start, "Vd_stop": Vd_stop,
            "Vd_step": self.vd_voltage_step_for_tsp, # This is actual Vd step value for TSP
            "N_st": self.N_st_for_tsp, # This is number of Vd points for TSP
            "settling_delay": config.get('settling_delay', config_settings.OC_DEFAULT_SETTLING_DELAY) # Added
        }

    def _get_primary_buffer_info(self, config):
        expected_total_points = self.num_actual_vg_points * self.N_st_for_tsp
        return config_settings.SMUA_NVBUFFER1, expected_total_points

    def _get_buffers_to_read_config(self, config, buffer_read_count):
        return {
            'Time_gate': (config_settings.GATE_SMU_TIMESTAMP_BUFFER_PATH, buffer_read_count),
            'Vg_source': (config_settings.GATE_SMU_VOLTAGE_SOURCEVALUES_BUFFER_PATH, buffer_read_count),
            'Vg_read': (config_settings.GATE_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Vd_read': (config_settings.DRAIN_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Id': (config_settings.DRAIN_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Ig': (config_settings.GATE_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Is_buffer': (config_settings.SOURCE_SMU_IS_BUFFER_READINGS_PATH, buffer_read_count)
        }

    def _get_priority_keys_for_consistent_length(self):
        return ['Id', 'Vd_read', 'Vg_source', 'Vg_read']

    def _perform_specific_data_processing(self, config):
        vg_source_data = self.processed_data.get('Vg_source')
        vg_read_data = self.processed_data.get('Vg_read')
        use_generated_vg = True

        if isinstance(vg_source_data, np.ndarray) and vg_source_data.size == self.consistent_len and not np.all(np.isnan(vg_source_data)):
            self.processed_data['Vg_actual_for_data'] = vg_source_data
            use_generated_vg = False
        elif isinstance(vg_read_data, np.ndarray) and vg_read_data.size == self.consistent_len and not np.all(np.isnan(vg_read_data)):
            self.processed_data['Vg_actual_for_data'] = vg_read_data
            use_generated_vg = False

        if use_generated_vg and self.consistent_len > 0:
            Vg_start = config['Vg_start']
            Vg_stop = config['Vg_stop']
            # self.num_actual_vg_points is already calculated in _prepare_tsp_parameters
            vg_points_ideal_sequence = np.linspace(Vg_start, Vg_stop, self.num_actual_vg_points) if self.num_actual_vg_points > 1 else np.array([Vg_start])
            # self.N_st_for_tsp is also calculated
            vg_repeated_ideal = np.repeat(vg_points_ideal_sequence, self.N_st_for_tsp if self.N_st_for_tsp > 0 else 1)

            if len(vg_repeated_ideal) == self.consistent_len:
                self.processed_data['Vg_actual_for_data'] = vg_repeated_ideal
            elif len(vg_repeated_ideal) > self.consistent_len :
                self.processed_data['Vg_actual_for_data'] = vg_repeated_ideal[:self.consistent_len]
            else: # len(vg_repeated_ideal) < self.consistent_len
                padded_vg = np.full(self.consistent_len, np.nan)
                if len(vg_repeated_ideal) > 0: padded_vg[:len(vg_repeated_ideal)] = vg_repeated_ideal
                self.processed_data['Vg_actual_for_data'] = padded_vg
        elif 'Vg_actual_for_data' not in self.processed_data: # If not using generated and no Vg_source/Vg_read
            self.processed_data['Vg_actual_for_data'] = np.array([])


        if 'Time_gate' in self.processed_data and isinstance(self.processed_data['Time_gate'], np.ndarray) \
           and self.processed_data['Time_gate'].size == self.consistent_len:
            self.processed_data['Time'] = self.processed_data['Time_gate']
        elif 'Time' not in self.processed_data: # Ensure 'Time' key exists
             self.processed_data['Time'] = np.full(self.consistent_len, np.nan) if self.consistent_len > 0 else np.array([])


    def _get_csv_header_info(self, config):
        header_cols = ['Time', 'Vg_actual_for_data', 'Vd_read', 'Id', 'Ig', 'Is', 'Jd', 'Jg', 'Js']
        header_str = (f"Time(s),Vg_actual(V),VDrain_read(V),IDrain(A),IGate(A),ISource(A),"
                      f"Jd({self.jd_unit_plot}),Jg({self.jd_unit_plot}),Js({self.jd_unit_plot})")
        return header_cols, header_str

    def _get_specific_metadata_comments(self, config):
        comments = ""
        comments += f"# Vg_start (set): {config.get('Vg_start', 'N/A')}\n"
        comments += f"# Vg_stop (set): {config.get('Vg_stop', 'N/A')}\n"
        comments += f"# Vg_segments (set): {config.get('Vg_step', 'N/A')}\n" # Vg_step from GUI for OC is segments
        comments += f"# Vd_start (set): {config.get('Vd_start', 'N/A')}\n"
        comments += f"# Vd_stop (set): {config.get('Vd_stop', 'N/A')}\n"
        comments += f"# Vd_step (set): {config.get('Vd_step', 'N/A')}\n" # Vd_step from GUI for OC is actual step
        comments += f"# Settling Delay (s): {config.get('settling_delay', 'N/A')}\n" # Added
        comments += f"# Num Vg points expected: {self.num_actual_vg_points}\n"
        comments += f"# Num Vd points per Vg expected: {self.N_st_for_tsp}\n"
        return comments

    def _prepare_plot_data_package(self, config):
        return {
            "processed_data": self.processed_data,
            "Vd_step_val_config": self.vd_voltage_step_for_tsp, # Use the value prepared for TSP
            "jd_unit_plot": self.jd_unit_plot,
            "png_file_path": self.png_file_path,
            "csv_file_path": self.csv_file_path,
            "measurement_type_name": self.measurement_type_name_full,
            "status": "success_data_ready"
        }

def generate_output_plot(plot_data_package):
    return plotting_utils.generate_plot_with_common_handling(
        plot_data_package,
        _plot_output_figure_content
    )

def _plot_output_figure_content(fig, plot_data_package):
    processed_data = plot_data_package['processed_data']
    vg_actual_data = processed_data.get('Vg_actual_for_data', np.array([]))
    unique_vg_values_raw = np.unique(vg_actual_data) if vg_actual_data.size > 0 else np.array([])
    Vd_step_val_plot = plot_data_package.get('Vd_step_val_config', 0.1)
    jd_unit_plot = plot_data_package.get('jd_unit_plot', "A.U.")
    measurement_name = plot_data_package.get("measurement_type_name", "Output Characteristics")
    ax_id_vd, ax_jd_vd = fig.subplots(2, 1, sharex=True)
    unique_vg_values = unique_vg_values_raw[~np.isnan(unique_vg_values_raw)]
    if len(unique_vg_values) > 0 :
        num_curves = len(unique_vg_values)
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        # Use a colormap if more curves than default colors, otherwise cycle default colors
        colors_plot_list = plt.cm.get_cmap('viridis', num_curves) if num_curves > len(default_colors) else default_colors

        for i, vg_val_plot in enumerate(unique_vg_values):
            if vg_actual_data.size == 0: continue # Should not happen if unique_vg_values is populated
            mask = np.isclose(vg_actual_data, vg_val_plot, atol=1e-5) # Use isclose for float comparison
            if not np.any(mask): continue

            vd_points = processed_data.get('Vd_read', np.array([]))[mask]
            id_points = processed_data.get('Id', np.array([]))[mask]
            jd_points = processed_data.get('Jd', np.array([]))[mask]

            current_color_idx = i % len(default_colors) if num_curves <= len(default_colors) else i
            current_color = default_colors[current_color_idx] if num_curves <= len(default_colors) else colors_plot_list(i / (num_curves -1 if num_curves > 1 else 1))


            if vd_points.size > 0 and id_points.size == vd_points.size:
                sort_indices = np.argsort(vd_points)
                ax_id_vd.plot(vd_points[sort_indices], id_points[sort_indices], marker='o', linestyle='-', ms=3, color=current_color, label=f"$V_G$={vg_val_plot:.2f}V")
            if vd_points.size > 0 and jd_points.size == vd_points.size:
                sort_indices = np.argsort(vd_points)
                ax_jd_vd.plot(vd_points[sort_indices], jd_points[sort_indices], marker='o', linestyle='-', ms=3, color=current_color) # No label for Jd plot to avoid duplicate legend items
    else:
        fig_text = f"{measurement_name}\nNo valid data or Vg values to plot"
        if plot_data_package.get('csv_file_path'): fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
        ax_id_vd.text(0.5, 0.5, fig_text, ha='center', va='center', transform=ax_id_vd.transAxes, fontsize=10, wrap=True)
        ax_jd_vd.text(0.5, 0.5, fig_text, ha='center', va='center', transform=ax_jd_vd.transAxes, fontsize=10, wrap=True) # Show error on both if no data

    ax_id_vd.set_title(f'$I_D$ vs $V_D$')
    ax_id_vd.set_ylabel('$I_D$ (A)')
    ax_id_vd.grid(True,alpha=0.4)
    if ax_id_vd.lines:
        num_id_curves = len(ax_id_vd.lines)
        legend_ncol_id = 1
        if 0 < num_id_curves <= 4: legend_ncol_id = num_id_curves
        elif 4 < num_id_curves <= 8: legend_ncol_id = 2
        elif num_id_curves > 8: legend_ncol_id = 3 # Max 3 columns for legend
        if num_id_curves <= 12: # Only show legend if not too many curves
            ax_id_vd.legend(loc="best", fontsize=7, ncol=legend_ncol_id)
        else:
            ax_id_vd.text(0.98, 0.98, f"{num_id_curves} $V_G$ curves\n(Legend omitted)",
                          transform=ax_id_vd.transAxes, ha='right', va='top', fontsize=7,
                          bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', alpha=0.7))


    ax_jd_vd.set_title(f'$J_D$ vs $V_D$')
    ax_jd_vd.set_xlabel('$V_D$ (V)')
    ax_jd_vd.set_ylabel(f'$J_D$ ({jd_unit_plot})')
    ax_jd_vd.grid(True,alpha=0.4)

    # Set x-axis limits based on actual Vd data range
    vd_plot_data_all = processed_data.get('Vd_read', np.array([]))
    if vd_plot_data_all.size > 0 and not np.all(np.isnan(vd_plot_data_all)):
         min_vd_plot, max_vd_plot = np.nanmin(vd_plot_data_all), np.nanmax(vd_plot_data_all)
         plot_padding = abs(Vd_step_val_plot) * 0.5 if Vd_step_val_plot !=0 else (abs(max_vd_plot - min_vd_plot) * 0.1 if max_vd_plot != min_vd_plot else 0.1)
         if plot_padding == 0 and max_vd_plot == min_vd_plot : plot_padding = 0.1 # Ensure some padding for single point Vd
         xlim_min, xlim_max = min_vd_plot - plot_padding, max_vd_plot + plot_padding
         if xlim_min < xlim_max : ax_id_vd.set_xlim(xlim_min, xlim_max) # sharex=True handles ax_jd_vd

    fig.suptitle(f'{measurement_name} Curves', fontsize=14, y=0.99)
    try:
        fig.tight_layout(rect=[0, 0, 1, 0.95]) # Adjust rect to make space for suptitle
    except Exception as e_layout:
        # print(f"Warning: tight_layout failed for Output plot: {e_layout}", file=sys.stderr)
        pass # Continue if tight_layout fails

@instrument_utils.handle_measurement_errors
def run_output_measurement(config):
    config["measurement_type_name"] = "Output Characteristics"
    GPIB_ADDRESS = config.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
    TIMEOUT = config.get(config_settings.CONFIG_KEY_TIMEOUT, config_settings.DEFAULT_TIMEOUT)
    oc_measurement = OutputMeasurement()
    with instrument_utils.visa_instrument(GPIB_ADDRESS, TIMEOUT, config["measurement_type_name"]) as inst:
        plot_data_package = oc_measurement.perform_measurement_flow(config, inst)
    return plot_data_package
