# gate_transfer_module.py
import pyvisa
import numpy as np
import matplotlib
# import matplotlib.pyplot as plt
from datetime import datetime
import os
import sys
import traceback
import instrument_utils
import config_settings
from measurement_base import MeasurementBase 
import plotting_utils 

def _split_sweep_data_internal(data_array, enable_backward_flag, num_points_fwd_expected=0):
    if not isinstance(data_array, np.ndarray):
        return np.array([]), np.array([])
    actual_len = len(data_array)
    if not enable_backward_flag or actual_len == 0:
        return data_array, np.array([])
    if num_points_fwd_expected > 0:
        if actual_len >= num_points_fwd_expected:
            fwd_part = data_array[:num_points_fwd_expected]
            bwd_part_len = min(num_points_fwd_expected, actual_len - num_points_fwd_expected)
            if bwd_part_len > 0:
                bwd_part = data_array[num_points_fwd_expected : num_points_fwd_expected + bwd_part_len]
            else:
                bwd_part = np.array([])
            return fwd_part, bwd_part
        else: 
            return data_array, np.array([])
    else: 
        if actual_len % 2 == 0:
            num_points_forward_inferred = actual_len // 2
            return data_array[:num_points_forward_inferred], data_array[num_points_forward_inferred:]
        else: 
            return data_array, np.array([])

class GateTransferMeasurement(MeasurementBase):
    def __init__(self):
        super().__init__(measurement_type_name_short="GateTransfer", plot_file_suffix=".png")
        self.num_points_per_sweep = 0
        # Removed mobility attribute initializations
        # self.mu_lin_fwd_calc = np.nan 
        # self.mu_sat_fwd_calc = np.nan

    def _get_tsp_script_path_key(self, config):
        return config_settings.CONFIG_KEY_TSP_GATE_TRANSFER

    def _get_default_tsp_script_path(self, config):
        return config_settings.DEFAULT_TSP_GATE_TRANSFER

    def _prepare_tsp_parameters(self, config):
        Vg_start = config['Vg_start']
        Vg_stop = config['Vg_stop']
        vg_step_val = config['step']
        enable_backward = config['enable_backward']

        self.num_points_per_sweep = 1
        if vg_step_val != 0:
            self.num_points_per_sweep = int(round(abs(Vg_stop - Vg_start) / abs(vg_step_val))) + 1
        elif Vg_start != Vg_stop:
            raise ValueError("If Vg_start != Vg_stop, then Vg step (config['step']) cannot be zero.")
        return {
            "IlimitDrain": config['IlimitDrain'], "IlimitGate": config['IlimitGate'],
            "Drain_nplc": config['Drain_nplc'], "Gate_nplc": config['Gate_nplc'],
            "Vd": config['Vd'], "Vg_start": Vg_start, "Vg_stop": Vg_stop,
            "step": vg_step_val, "enable_backward": "1" if enable_backward else "0", 
            "settling_delay": config.get('settling_delay', config_settings.GT_DEFAULT_SETTLING_DELAY)
        }

    def _get_primary_buffer_info(self, config):
        expected_total_points = self.num_points_per_sweep
        if config['enable_backward']:
            expected_total_points *= 2
        return config_settings.NODE2_SMUA_NVBUFFER2, expected_total_points

    def _get_buffers_to_read_config(self, config, buffer_read_count):
        return {
            'Time': (config_settings.GATE_SMU_TIMESTAMP_BUFFER_PATH, buffer_read_count),
            'Vg_read': (config_settings.GATE_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Vg_source': (config_settings.GATE_SMU_VOLTAGE_SOURCEVALUES_BUFFER_PATH, buffer_read_count),
            'Vd_read': (config_settings.DRAIN_SMU_VOLTAGE_READINGS_BUFFER_PATH, buffer_read_count),
            'Id': (config_settings.DRAIN_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Ig': (config_settings.GATE_SMU_CURRENT_READINGS_BUFFER_PATH, buffer_read_count),
            'Is_buffer': (config_settings.SOURCE_SMU_IS_BUFFER_READINGS_PATH, buffer_read_count)
        }

    def _get_priority_keys_for_consistent_length(self):
        return ['Id', 'Vg_read', 'Vg_source']

    def _perform_specific_data_processing(self, config):
        vg_read_data = self.processed_data.get('Vg_read')
        vg_source_data = self.processed_data.get('Vg_source')
        use_generated_vg = True
        if isinstance(vg_read_data, np.ndarray) and vg_read_data.size == self.consistent_len and not np.all(np.isnan(vg_read_data)):
            self.processed_data['Vg_actual_for_data'] = vg_read_data
            use_generated_vg = False
        elif isinstance(vg_source_data, np.ndarray) and vg_source_data.size == self.consistent_len and not np.all(np.isnan(vg_source_data)):
            self.processed_data['Vg_actual_for_data'] = vg_source_data
            use_generated_vg = False

        if use_generated_vg and self.consistent_len > 0:
            Vg_start = config['Vg_start']
            Vg_stop = config['Vg_stop']
            vg_fwd_calc = np.linspace(Vg_start, Vg_stop, self.num_points_per_sweep) if self.num_points_per_sweep > 0 else np.array([Vg_start])
            temp_vg_combined = vg_fwd_calc
            if config['enable_backward'] and self.num_points_per_sweep > 0:
                temp_vg_combined = np.concatenate([vg_fwd_calc, np.flip(vg_fwd_calc)])
            if len(temp_vg_combined) >= self.consistent_len:
                self.processed_data['Vg_actual_for_data'] = temp_vg_combined[:self.consistent_len]
            else:
                padded_vg = np.full(self.consistent_len, np.nan)
                if len(temp_vg_combined) > 0: padded_vg[:len(temp_vg_combined)] = temp_vg_combined
                self.processed_data['Vg_actual_for_data'] = padded_vg
        elif 'Vg_actual_for_data' not in self.processed_data:
             self.processed_data['Vg_actual_for_data'] = np.array([])

        temp_data_for_splitting = self.processed_data.copy()
        self.forward_data = {}
        self.backward_data = {}
        for key, arr_val in temp_data_for_splitting.items():
            fwd_part, bwd_part = _split_sweep_data_internal(arr_val, config['enable_backward'], self.num_points_per_sweep)
            self.forward_data[key] = fwd_part
            self.backward_data[key] = bwd_part

        gm_calc_fwd = np.array([])
        ss_calc_values_fwd = np.array([])
        Vth_fwd = np.nan
        min_ss_fwd = np.nan
        min_index_ss_fwd = None
        ion_fwd = np.nan
        ioff_fwd = np.nan
        ion_ioff_ratio_fwd = np.nan
        max_gm_fwd = np.nan
        vg_at_max_gm_fwd = np.nan
        
        fwd_vg_data = self.forward_data.get('Vg_actual_for_data', np.array([]))
        fwd_id_data = self.forward_data.get('Id', np.array([]))

        if fwd_vg_data.size > 1 and fwd_id_data.size == fwd_vg_data.size:
            valid_indices_fwd = ~np.isnan(fwd_vg_data) & ~np.isnan(fwd_id_data)
            vg_valid_fwd = fwd_vg_data[valid_indices_fwd]
            id_valid_fwd = fwd_id_data[valid_indices_fwd]
            if vg_valid_fwd.size > 1:
                gm_subset_fwd = np.gradient(id_valid_fwd, vg_valid_fwd)
                gm_calc_fwd = np.full(fwd_vg_data.size, np.nan)
                gm_calc_fwd[valid_indices_fwd] = gm_subset_fwd
                if np.any(~np.isnan(gm_calc_fwd)):
                    max_gm_fwd = np.nanmax(gm_calc_fwd)
                    idx_max_gm = np.nanargmax(gm_calc_fwd)
                    vg_at_max_gm_fwd = fwd_vg_data[idx_max_gm]
                id_abs_safe_fwd = np.clip(np.abs(id_valid_fwd), 1e-14, None)
                log_id_fwd = np.log10(id_abs_safe_fwd)
                dlog_Id_dVg_fwd = np.gradient(log_id_fwd, vg_valid_fwd)
                ss_subset_fwd = np.full_like(dlog_Id_dVg_fwd, np.nan)
                valid_dlog_indices_fwd = np.abs(dlog_Id_dVg_fwd) > 1e-9
                ss_subset_fwd[valid_dlog_indices_fwd] = 1000.0 / dlog_Id_dVg_fwd[valid_dlog_indices_fwd]
                ss_calc_values_fwd = np.full(fwd_vg_data.size, np.nan)
                ss_calc_values_fwd[valid_indices_fwd] = ss_subset_fwd
                positive_ss_values_fwd = ss_subset_fwd[ss_subset_fwd > 0]
                if positive_ss_values_fwd.size > 0:
                    min_ss_fwd = np.min(positive_ss_values_fwd)
                    min_ss_indices_in_subset = np.where(ss_subset_fwd == min_ss_fwd)[0]
                    if min_ss_indices_in_subset.size > 0:
                        original_valid_indices_map_fwd = np.where(valid_indices_fwd)[0]
                        min_index_ss_fwd = original_valid_indices_map_fwd[min_ss_indices_in_subset[0]]
                if not np.isnan(max_gm_fwd) and max_gm_fwd > 0:
                    idx_max_gm_fwd = np.nanargmax(gm_calc_fwd)
                    if idx_max_gm_fwd < len(fwd_vg_data) and idx_max_gm_fwd < len(fwd_id_data) and \
                       not np.isnan(fwd_vg_data[idx_max_gm_fwd]) and not np.isnan(fwd_id_data[idx_max_gm_fwd]):
                        vg_at_gm_max_val = fwd_vg_data[idx_max_gm_fwd]
                        id_at_gm_max_val = fwd_id_data[idx_max_gm_fwd]
                        Vth_fwd = vg_at_gm_max_val - (id_at_gm_max_val / max_gm_fwd)
            if id_valid_fwd.size > 0:
                ion_fwd = np.max(np.abs(id_valid_fwd))
                ioff_candidates_abs_fwd = np.abs(id_valid_fwd[np.abs(id_valid_fwd) > 1e-13])
                if not np.isnan(Vth_fwd):
                    ioff_region_mask_fwd = (vg_valid_fwd < (Vth_fwd - 0.5)) & (np.abs(id_valid_fwd) > 1e-13)
                    ioff_candidates_in_region_fwd = np.abs(id_valid_fwd[ioff_region_mask_fwd])
                    if ioff_candidates_in_region_fwd.size > 0: ioff_fwd = np.min(ioff_candidates_in_region_fwd)
                    elif ioff_candidates_abs_fwd.size > 0: ioff_fwd = np.min(ioff_candidates_abs_fwd)
                elif ioff_candidates_abs_fwd.size > 0: ioff_fwd = np.min(ioff_candidates_abs_fwd)
                if not np.isnan(ion_fwd) and not np.isnan(ioff_fwd) and ioff_fwd > 1e-14:
                    ion_ioff_ratio_fwd = ion_fwd / ioff_fwd
            
            # Mobility calculation section is removed.

        self.processed_data['gm'] = np.full(self.consistent_len, np.nan)
        if gm_calc_fwd.size > 0 and len(gm_calc_fwd) == len(self.forward_data.get('Id',[])) :
            self.processed_data['gm'][:len(gm_calc_fwd)] = gm_calc_fwd
        self.processed_data['SS'] = np.full(self.consistent_len, np.nan)
        if ss_calc_values_fwd.size > 0 and len(ss_calc_values_fwd) == len(self.forward_data.get('Id',[])):
            self.processed_data['SS'][:len(ss_calc_values_fwd)] = ss_calc_values_fwd
        
        self.Vth_fwd_calc = Vth_fwd
        self.min_ss_fwd_calc = min_ss_fwd
        self.min_index_ss_fwd_calc = min_index_ss_fwd
        self.ion_fwd_calc = ion_fwd
        self.ioff_fwd_calc = ioff_fwd
        self.ion_ioff_ratio_fwd_calc = ion_ioff_ratio_fwd
        self.max_gm_fwd_calc = max_gm_fwd
        self.vg_at_max_gm_fwd_calc = vg_at_max_gm_fwd
        self.avg_sweep_rate_fwd = 0
        fwd_time_data = self.forward_data.get('Time', np.array([]))
        if fwd_vg_data.size > 1 and fwd_time_data.size == fwd_vg_data.size:
            valid_sr_indices_fwd = ~np.isnan(fwd_time_data) & ~np.isnan(fwd_vg_data)
            if np.sum(valid_sr_indices_fwd) > 1:
                dvdt_fwd = np.gradient(fwd_vg_data[valid_sr_indices_fwd], fwd_time_data[valid_sr_indices_fwd])
                self.avg_sweep_rate_fwd = np.nanmean(dvdt_fwd)
        self.average_drain_bias_fwd = config.get('Vd', np.nan)
        fwd_vd_data = self.forward_data.get('Vd_read', np.array([]))
        if fwd_vd_data.size > 0 and not np.all(np.isnan(fwd_vd_data)):
            self.average_drain_bias_fwd = np.nanmean(fwd_vd_data)

    def _get_csv_header_info(self, config):
        header_cols = ['Time', 'Vg_actual_for_data', 'Id', 'Ig', 'Is', 'Vd_read', 'gm', 'SS', 'Jd', 'Jg', 'Js']
        header_str = f"Time(s),Vg_actual(V),IDrain(A),IGate(A),ISource(A),VDrain_read(V),gm(S),SS(mV/dec),Jd({self.jd_unit_plot}),Jg({self.jd_unit_plot}),Js({self.jd_unit_plot})"
        return header_cols, header_str

    def _get_specific_metadata_comments(self, config):
        comments = ""
        comments += f"# Vd_bias (set): {config.get('Vd', 'N/A'):.3f}\n"
        comments += f"# Vg_start (set): {config.get('Vg_start', 'N/A')}\n"
        comments += f"# Vg_stop (set): {config.get('Vg_stop', 'N/A')}\n"
        comments += f"# Vg_step (set): {config.get('step', 'N/A')}\n"
        comments += f"# Enable Backward: {config.get('enable_backward', False)}\n"
        comments += f"# Settling Delay (s): {config.get('settling_delay', 'N/A')}\n" # Added
        comments += f"# Num Points Fwd Expected: {self.num_points_per_sweep}\n"

        
        if not np.isnan(self.Vth_fwd_calc): comments += f"# Vth_fwd (V): {self.Vth_fwd_calc:.4f}\n"
        if not np.isnan(self.min_ss_fwd_calc): comments += f"# SS_min_fwd (mV/dec): {self.min_ss_fwd_calc:.2f}\n"
        if not np.isnan(self.max_gm_fwd_calc): comments += f"# Max_gm_fwd (S): {self.max_gm_fwd_calc:.4e}\n"
        if not np.isnan(self.vg_at_max_gm_fwd_calc): comments += f"# Vg_at_Max_gm_fwd (V): {self.vg_at_max_gm_fwd_calc:.4f}\n"
        if not np.isnan(self.ion_fwd_calc): comments += f"# Ion_fwd (A): {self.ion_fwd_calc:.4e}\n"
        if not np.isnan(self.ioff_fwd_calc): comments += f"# Ioff_fwd (A): {self.ioff_fwd_calc:.4e}\n"
        if not np.isnan(self.ion_ioff_ratio_fwd_calc): comments += f"# Ion_Ioff_Ratio_fwd: {self.ion_ioff_ratio_fwd_calc:.4e}\n"
        if self.avg_sweep_rate_fwd != 0: comments += f"# Avg_Sweep_Rate_Fwd (V/s): {self.avg_sweep_rate_fwd:.3f}\n"
        if not np.isnan(self.average_drain_bias_fwd): comments += f"# Avg_Drain_Bias_Fwd (V): {self.average_drain_bias_fwd:.3f}\n"
        return comments

    def _prepare_plot_data_package(self, config):
        return {
            "forward_data": self.forward_data,
            "backward_data": self.backward_data,
            "enable_backward_plot": config['enable_backward'] and self.backward_data.get('Vg_actual_for_data', np.array([])).size > 0,
            "gm_fwd_calc": self.processed_data.get('gm', np.array([])), 
            "Vth_fwd_calc": self.Vth_fwd_calc,
            "min_ss_fwd_calc": self.min_ss_fwd_calc,
            "min_index_ss_fwd_calc": self.min_index_ss_fwd_calc,
            "avg_sweep_rate_fwd": self.avg_sweep_rate_fwd,
            "average_drain_bias_fwd": self.average_drain_bias_fwd,
            "jd_unit_plot": self.jd_unit_plot,
            "png_file_path": self.png_file_path,
            "csv_file_path": self.csv_file_path,
            "measurement_type_name": self.measurement_type_name_full,
            "status": "success_data_ready",
            "Ion_fwd": self.ion_fwd_calc,
            "Ioff_fwd": self.ioff_fwd_calc,
            "Ion_Ioff_ratio_fwd": self.ion_ioff_ratio_fwd_calc,
            "max_gm_fwd": self.max_gm_fwd_calc,
            "Vg_at_max_gm_fwd": self.vg_at_max_gm_fwd_calc
        }

@instrument_utils.handle_measurement_errors
def run_gate_transfer_measurement(config):
    config["measurement_type_name"] = "Gate Transfer"
    GPIB_ADDRESS = config.get(config_settings.CONFIG_KEY_GPIB_ADDRESS, config_settings.DEFAULT_GPIB_ADDRESS)
    TIMEOUT = config.get(config_settings.CONFIG_KEY_TIMEOUT, config_settings.DEFAULT_TIMEOUT)
    gt_measurement = GateTransferMeasurement()
    with instrument_utils.visa_instrument(GPIB_ADDRESS, TIMEOUT, config["measurement_type_name"]) as inst:
        plot_data_package = gt_measurement.perform_measurement_flow(config, inst)
    return plot_data_package

# Ensure plotting functions (_plot_gate_transfer_figure_content, _plot_gt_default_live, generate_gate_transfer_plot)
# are present and correctly defined as per previous refactorings.
# For brevity, only generate_gate_transfer_plot is shown here, assuming others are intact.
def generate_gate_transfer_plot(plot_data_package):
    return plotting_utils.generate_plot_with_common_handling(
        plot_data_package,
        _plot_gate_transfer_figure_content # Assumes _plot_gate_transfer_figure_content is defined
    )

def _plot_gate_transfer_figure_content(fig, plot_data_package):
    live_plot_type = plot_data_package.get('live_plot_type', 'default_live')
    forward_data = plot_data_package.get('forward_data', {})
    backward_data = plot_data_package.get('backward_data', {})
    enable_backward_plot = plot_data_package.get('enable_backward_plot', False)
    gm_fwd_for_plot = plot_data_package.get('gm_fwd_calc', np.array([]))
    fwd_vg_len = len(forward_data.get('Vg_actual_for_data', []))
    if len(gm_fwd_for_plot) > fwd_vg_len and fwd_vg_len > 0:
        gm_fwd_plot_actual = gm_fwd_for_plot[:fwd_vg_len]
    else:
        gm_fwd_plot_actual = gm_fwd_for_plot
    Vth_fwd_plot = plot_data_package.get('Vth_fwd_calc')
    average_drain_bias_fwd = plot_data_package.get('average_drain_bias_fwd', np.nan)
    measurement_name = plot_data_package.get("measurement_type_name", "Gate Transfer")
    fwd_vg_plot = forward_data.get('Vg_actual_for_data', np.array([]))
    fwd_id_plot = forward_data.get('Id', np.array([]))
    fwd_ig_plot = forward_data.get('Ig', np.array([]))
    fwd_is_plot = forward_data.get('Is', np.array([]))
    bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
    bwd_id_plot = backward_data.get('Id', np.array([]))
    bwd_ig_plot = backward_data.get('Ig', np.array([]))
    bwd_is_plot = backward_data.get('Is', np.array([]))
    title_base = f'{measurement_name} ($V_D \\approx$ {average_drain_bias_fwd:.2f}V)'

    if live_plot_type == "linear_all":
        ax = fig.add_subplot(111)
        lines_for_legend, labels_for_legend = [], []
        if fwd_vg_plot.size > 0 and fwd_id_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
            l, = ax.plot(fwd_vg_plot, fwd_id_plot, color='blue', linestyle='-', marker='o', ms=3, label='$I_D$ (Fwd)')
            lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if enable_backward_plot and bwd_vg_plot.size > 0 and bwd_id_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            l, = ax.plot(bwd_vg_plot, bwd_id_plot, color='deepskyblue', linestyle='-', marker='o', ms=3, label='$I_D$ (Bwd)', alpha=0.7)
            lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        ax.set_xlabel("$V_G$ (V)"); ax.set_ylabel("$I_D$ (A)", color='blue')
        ax.tick_params(axis='y', labelcolor='blue'); ax.set_yscale('linear'); ax.grid(True, alpha=0.4)
        if fwd_vg_plot.size > 0 and gm_fwd_plot_actual.size == fwd_vg_plot.size and np.any(~np.isnan(gm_fwd_plot_actual)):
            ax_gm = ax.twinx()
            l, = ax_gm.plot(fwd_vg_plot, gm_fwd_plot_actual, color='red', linestyle='--', marker='None', label='$g_m$ (Fwd)')
            ax_gm.set_ylabel("$g_m$ (S)", color='red'); ax_gm.tick_params(axis='y', labelcolor='red')
            ax_gm.set_yscale('linear'); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if lines_for_legend: ax.legend(lines_for_legend, labels_for_legend, loc="best", fontsize=8)
        ax.set_title(title_base + " - Linear $I_D$ & $g_m$")
        fig.tight_layout(rect=[0, 0, 1, 0.95])
    elif live_plot_type == "log_currents":
        ax = fig.add_subplot(111)
        lines_for_legend, labels_for_legend = [], []
        if fwd_vg_plot.size > 0 and fwd_id_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
            fwd_id_abs = np.abs(fwd_id_plot); valid_fwd_id = (fwd_id_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
            if np.any(valid_fwd_id): l, = ax.plot(fwd_vg_plot[valid_fwd_id], fwd_id_abs[valid_fwd_id], color='blue', linestyle='-', marker='o', ms=3, label='$|I_D|$ (Fwd)'); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if enable_backward_plot and bwd_vg_plot.size > 0 and bwd_id_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_id_abs = np.abs(bwd_id_plot); valid_bwd_id = (bwd_id_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_bwd_id): l, = ax.plot(bwd_vg_plot[valid_bwd_id], bwd_id_abs[valid_bwd_id], color='deepskyblue', linestyle='-', marker='o', ms=3, label='$|I_D|$ (Bwd)', alpha=0.7); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if fwd_vg_plot.size > 0 and fwd_ig_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
            fwd_ig_abs = np.abs(fwd_ig_plot); valid_fwd_ig = (fwd_ig_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
            if np.any(valid_fwd_ig): l, = ax.plot(fwd_vg_plot[valid_fwd_ig], fwd_ig_abs[valid_fwd_ig], color='red', linestyle='--', marker='None', label='$|I_G|$ (Fwd)'); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if enable_backward_plot and bwd_vg_plot.size > 0 and bwd_ig_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_ig_abs = np.abs(bwd_ig_plot); valid_bwd_ig = (bwd_ig_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_bwd_ig): l, = ax.plot(bwd_vg_plot[valid_bwd_ig], bwd_ig_abs[valid_bwd_ig], color='lightcoral', linestyle='--', marker='None', label='$|I_G|$ (Bwd)', alpha=0.7); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if fwd_vg_plot.size > 0 and fwd_is_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
            fwd_is_abs = np.abs(fwd_is_plot); valid_fwd_is = (fwd_is_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
            if np.any(valid_fwd_is): l, = ax.plot(fwd_vg_plot[valid_fwd_is], fwd_is_abs[valid_fwd_is], color='green', linestyle='-', marker='o', ms=3, label='$|I_S|$ (Fwd)'); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if enable_backward_plot and bwd_vg_plot.size > 0 and bwd_is_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_is_abs = np.abs(bwd_is_plot); valid_bwd_is = (bwd_is_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_bwd_is): l, = ax.plot(bwd_vg_plot[valid_bwd_is], bwd_is_abs[valid_bwd_is], color='lightgreen', linestyle='-', marker='o', ms=3, label='$|I_S|$ (Bwd)', alpha=0.7); lines_for_legend.append(l); labels_for_legend.append(l.get_label())
        if Vth_fwd_plot is not None and not np.isnan(Vth_fwd_plot):
             ax.axvline(Vth_fwd_plot, color='k', linestyle=':', linewidth=1.2, label=f"$V_{{th}}$={Vth_fwd_plot:.2f}V (Fwd)")
             from matplotlib.lines import Line2D
             vth_line = Line2D([0], [0], color='k', linestyle=':', linewidth=1.2, label=f"$V_{{th}}$={Vth_fwd_plot:.2f}V (Fwd)")
             if not any(handle.get_label() == vth_line.get_label() for handle in lines_for_legend): lines_for_legend.append(vth_line); labels_for_legend.append(vth_line.get_label())
        ax.set_xlabel("$V_G$ (V)"); ax.set_ylabel("Log $|Current|$ (A)")
        ax.set_yscale('log'); ax.grid(True, which="both", alpha=0.3)
        if lines_for_legend : ax.legend(lines_for_legend, labels_for_legend, loc="best", fontsize=8)
        ax.set_title(title_base + " - Semilog $I_D, I_G, I_S$")
        fig.tight_layout(rect=[0, 0, 1, 0.95])
    elif live_plot_type == "gm_only":
        ax = fig.add_subplot(111)
        if fwd_vg_plot.size > 0 and gm_fwd_plot_actual.size == fwd_vg_plot.size and np.any(~np.isnan(gm_fwd_plot_actual)):
            ax.plot(fwd_vg_plot, gm_fwd_plot_actual, color='red', linestyle='--', marker='None', label='$g_m$ (Fwd)')
        ax.set_xlabel("$V_G$ (V)"); ax.set_ylabel("$g_m$ (S)")
        ax.set_yscale('linear'); ax.grid(True, alpha=0.4)
        if ax.lines: ax.legend(loc="best", fontsize=8)
        ax.set_title(title_base + " - Transconductance ($g_m$)")
        fig.tight_layout(rect=[0, 0, 1, 0.95])
    else: 
        _plot_gt_default_live(fig, plot_data_package) # Ensure this is defined
    if not fig.axes:
         fig_text = f"{measurement_name}\nNo valid data or unknown plot type selected"
         if plot_data_package.get('csv_file_path'): fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
         fig.text(0.5, 0.5, fig_text, ha='center', va='center', fontsize=12, transform=fig.transFigure)

def _plot_gt_default_live(fig, plot_data_package):
    # This is the 4-subplot function. Ensure its full definition is present.
    # (Content from previous complete gate_transfer_module.py)
    forward_data = plot_data_package.get('forward_data', {})
    backward_data = plot_data_package.get('backward_data', {})
    enable_backward_plot = plot_data_package.get('enable_backward_plot', False)
    gm_fwd_for_plot = plot_data_package.get('gm_fwd_calc', np.array([]))
    fwd_vg_len = len(forward_data.get('Vg_actual_for_data', []))
    if len(gm_fwd_for_plot) > fwd_vg_len and fwd_vg_len > 0:
        gm_fwd_plot_actual = gm_fwd_for_plot[:fwd_vg_len]
    else:
        gm_fwd_plot_actual = gm_fwd_for_plot
    Vth_fwd_plot = plot_data_package.get('Vth_fwd_calc')
    min_ss_fwd_plot = plot_data_package.get('min_ss_fwd_calc')
    min_index_ss_fwd_plot = plot_data_package.get('min_index_ss_fwd_calc')
    avg_sweep_rate_fwd = plot_data_package.get('avg_sweep_rate_fwd', 0)
    average_drain_bias_fwd = plot_data_package.get('average_drain_bias_fwd', np.nan)
    jd_unit_plot = plot_data_package.get('jd_unit_plot', 'A.U.')
    measurement_name = plot_data_package.get("measurement_type_name", "Gate Transfer")
    fwd_vg_plot = forward_data.get('Vg_actual_for_data', np.array([]))
    fwd_id_plot = forward_data.get('Id', np.array([]))
    fwd_ig_plot = forward_data.get('Ig', np.array([]))
    fwd_is_plot = forward_data.get('Is', np.array([]))
    ax1 = fig.add_subplot(2, 2, 1)
    has_fwd_id_data = fwd_vg_plot.size > 0 and fwd_id_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot))
    if has_fwd_id_data:
         ax1.plot(fwd_vg_plot, fwd_id_plot, marker='o', linestyle='-', ms=3, color='blue', label="Forward $I_D$")
    ax1.set_xlabel("$V_G$ (V)"); ax1.set_ylabel("$I_D$ (A)", color='blue')
    ax1.tick_params(axis='y', labelcolor='blue'); ax1.grid(True, alpha=0.4)
    ax1.set_yscale('linear')
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_id_plot = backward_data.get('Id', np.array([]))
        if bwd_vg_plot.size > 0 and bwd_id_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            ax1.plot(bwd_vg_plot, bwd_id_plot, marker='o', linestyle='-', ms=3, color='deepskyblue', alpha=0.7, label="Backward $I_D$")
    ax1_twin = ax1.twinx()
    if fwd_vg_plot.size > 0 and gm_fwd_plot_actual.size == fwd_vg_plot.size and np.any(~np.isnan(gm_fwd_plot_actual)):
        ax1_twin.plot(fwd_vg_plot, gm_fwd_plot_actual, marker='None', linestyle='--', color='red', label="$g_m$ (Fwd)")
    ax1_twin.set_ylabel("$g_m$ (S)", color='red'); ax1_twin.tick_params(axis='y', labelcolor='red')
    ax1_twin.set_yscale('linear')
    lines, labels = ax1.get_legend_handles_labels(); lines2, labels2 = ax1_twin.get_legend_handles_labels()
    if lines or lines2: ax1.legend(lines + lines2, labels + labels2, loc="best", fontsize=8)
    title_ax1 = f"$V_D \\approx$ {average_drain_bias_fwd:.2f} V"
    if avg_sweep_rate_fwd != 0 : title_ax1 += f", Sweep Rate: {abs(avg_sweep_rate_fwd):.2f} V/s"
    ax1.set_title(title_ax1)
    ax2 = fig.add_subplot(2, 2, 2)
    if has_fwd_id_data:
        fwd_id_abs = np.abs(fwd_id_plot)
        valid_log_fwd_id = (fwd_id_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_id):
            ax2.semilogy(fwd_vg_plot[valid_log_fwd_id], fwd_id_abs[valid_log_fwd_id], marker='o', ms=3, linestyle='-', color='blue', label="Forward $|I_D|$")
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_id_plot = backward_data.get('Id', np.array([]))
        if bwd_vg_plot.size > 0 and bwd_id_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_id_abs = np.abs(bwd_id_plot)
            valid_log_bwd_id = (bwd_id_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_id):
                ax2.semilogy(bwd_vg_plot[valid_log_bwd_id], bwd_id_abs[valid_log_bwd_id], marker='o', ms=3, linestyle='-', color='deepskyblue', alpha=0.7, label="Backward $|I_D|$")
    has_fwd_ig_data = fwd_vg_plot.size > 0 and fwd_ig_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot))
    if has_fwd_ig_data:
        fwd_ig_abs = np.abs(fwd_ig_plot)
        valid_log_fwd_ig = (fwd_ig_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_ig):
            ax2.semilogy(fwd_vg_plot[valid_log_fwd_ig], fwd_ig_abs[valid_log_fwd_ig], marker='None', linestyle='--', color='red', label="Forward $|I_G|$")
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_ig_plot = backward_data.get('Ig', np.array([]))
        if bwd_vg_plot.size > 0 and bwd_ig_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_ig_abs = np.abs(bwd_ig_plot)
            valid_log_bwd_ig = (bwd_ig_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_ig):
                ax2.semilogy(bwd_vg_plot[valid_log_bwd_ig], bwd_ig_abs[valid_log_bwd_ig], marker='None', linestyle='--', color='lightcoral', alpha=0.7, label="Backward $|I_G|$")
    has_fwd_is_data = fwd_vg_plot.size > 0 and fwd_is_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot))
    if has_fwd_is_data:
        fwd_is_abs = np.abs(fwd_is_plot)
        valid_log_fwd_is = (fwd_is_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_is):
            ax2.semilogy(fwd_vg_plot[valid_log_fwd_is], fwd_is_abs[valid_log_fwd_is], marker='o', ms=3, linestyle='-', color='green', label="Forward $|I_S|$")
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_is_plot = backward_data.get('Is', np.array([]))
        if bwd_vg_plot.size > 0 and bwd_is_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            bwd_is_abs = np.abs(bwd_is_plot)
            valid_log_bwd_is = (bwd_is_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_is):
                ax2.semilogy(bwd_vg_plot[valid_log_bwd_is], bwd_is_abs[valid_log_bwd_is], marker='o', ms=3, linestyle='-', color='lightgreen', alpha=0.7, label="Backward $|I_S|$")
    if Vth_fwd_plot is not None and not np.isnan(Vth_fwd_plot):
        ax2.axvline(Vth_fwd_plot, color='k', linestyle=':', linewidth=1.2, label=f"$V_{{th}}$={Vth_fwd_plot:.2f}V (Fwd)")
    if min_ss_fwd_plot is not None and not np.isnan(min_ss_fwd_plot) and \
       min_index_ss_fwd_plot is not None and not np.isnan(min_index_ss_fwd_plot) and \
       fwd_vg_plot.size > min_index_ss_fwd_plot and \
       forward_data.get('Id', np.array([])).size > min_index_ss_fwd_plot and \
       not np.isnan(forward_data.get('Id', np.array([]))[min_index_ss_fwd_plot]):
        id_at_min_ss = np.abs(forward_data.get('Id', np.array([]))[min_index_ss_fwd_plot])
        if id_at_min_ss > 1e-14 :
             ax2.scatter(fwd_vg_plot[min_index_ss_fwd_plot], id_at_min_ss, s=100, facecolors='none', edgecolors='magenta', lw=1.5, label=f"MinSS={min_ss_fwd_plot:.1f}mV/dec (Fwd)")
    ax2.set_xlabel("$V_G$ (V)"); ax2.set_ylabel("Current (A)")
    if ax2.lines: ax2.legend(loc="best", fontsize=8)
    ax2.grid(True, which="both", alpha=0.3); ax2.set_title("Semilog Currents"); ax2.set_yscale('log')
    ax3 = fig.add_subplot(2, 2, 3)
    fwd_jd_plot = forward_data.get('Jd', np.array([]))
    if fwd_vg_plot.size > 0 and fwd_jd_plot.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
        ax3.plot(fwd_vg_plot, fwd_jd_plot, marker='o', ms=3, linestyle='-', color='blue', label="Forward $J_D$")
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_jd_plot = backward_data.get('Jd', np.array([]))
        if bwd_vg_plot.size > 0 and bwd_jd_plot.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            ax3.plot(bwd_vg_plot, bwd_jd_plot, marker='o', ms=3, linestyle='-', color='deepskyblue', alpha=0.7, label="Backward $J_D$")
    ax3.set_xlabel("$V_G$ (V)"); ax3.set_ylabel(f"$J_D$ ({jd_unit_plot})"); ax3.grid(True, alpha=0.4)
    if ax3.lines: ax3.legend(loc="best", fontsize=8)
    ax3.set_title("Linear $J_D$"); ax3.set_yscale('linear')
    ax4 = fig.add_subplot(2, 2, 4)
    fwd_jd_plot_abs = np.abs(forward_data.get('Jd', np.array([])))
    fwd_jg_plot_abs = np.abs(forward_data.get('Jg', np.array([])))
    fwd_js_plot_abs = np.abs(forward_data.get('Js', np.array([])))
    if fwd_vg_plot.size > 0 and fwd_jd_plot_abs.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
        valid_log_fwd_jd = (fwd_jd_plot_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_jd): ax4.semilogy(fwd_vg_plot[valid_log_fwd_jd], fwd_jd_plot_abs[valid_log_fwd_jd], marker='o', ms=3, linestyle='-', color='blue', label="Forward $|J_D|$")
    if fwd_vg_plot.size > 0 and fwd_jg_plot_abs.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
        valid_log_fwd_jg = (fwd_jg_plot_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_jg): ax4.semilogy(fwd_vg_plot[valid_log_fwd_jg], fwd_jg_plot_abs[valid_log_fwd_jg], marker='None', linestyle='--', color='red', label="Forward $|J_G|$")
    if fwd_vg_plot.size > 0 and fwd_js_plot_abs.size == fwd_vg_plot.size and not np.all(np.isnan(fwd_vg_plot)):
        valid_log_fwd_js = (fwd_js_plot_abs > 1e-14) & ~np.isnan(fwd_vg_plot)
        if np.any(valid_log_fwd_js): ax4.semilogy(fwd_vg_plot[valid_log_fwd_js], fwd_js_plot_abs[valid_log_fwd_js], marker='o', ms=3, linestyle='-', color='green', label="Forward $|J_S|$")
    if enable_backward_plot:
        bwd_vg_plot = backward_data.get('Vg_actual_for_data', np.array([]))
        bwd_jd_plot_abs = np.abs(backward_data.get('Jd', np.array([])))
        bwd_jg_plot_abs = np.abs(backward_data.get('Jg', np.array([])))
        bwd_js_plot_abs = np.abs(backward_data.get('Js', np.array([])))
        if bwd_vg_plot.size > 0 and bwd_jd_plot_abs.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            valid_log_bwd_jd = (bwd_jd_plot_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_jd): ax4.semilogy(bwd_vg_plot[valid_log_bwd_jd], bwd_jd_plot_abs[valid_log_bwd_jd], marker='o', ms=3, linestyle='-', color='deepskyblue', alpha=0.7, label="Backward $|J_D|$")
        if bwd_vg_plot.size > 0 and bwd_jg_plot_abs.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            valid_log_bwd_jg = (bwd_jg_plot_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_jg): ax4.semilogy(bwd_vg_plot[valid_log_bwd_jg], bwd_jg_plot_abs[valid_log_bwd_jg], marker='None', linestyle='--', color='lightcoral', alpha=0.7, label="Backward $|J_G|$")
        if bwd_vg_plot.size > 0 and bwd_js_plot_abs.size == bwd_vg_plot.size and not np.all(np.isnan(bwd_vg_plot)):
            valid_log_bwd_js = (bwd_js_plot_abs > 1e-14) & ~np.isnan(bwd_vg_plot)
            if np.any(valid_log_bwd_js): ax4.semilogy(bwd_vg_plot[valid_log_bwd_js], bwd_js_plot_abs[valid_log_bwd_js], marker='o', ms=3, linestyle='-', color='lightgreen', alpha=0.7, label="Backward $|J_S|$")
    ax4.set_xlabel("$V_G$ (V)"); ax4.set_ylabel(f"Current density ({jd_unit_plot})")
    if ax4.lines: ax4.legend(loc="best", fontsize=8)
    ax4.grid(True, which="both", alpha=0.3); ax4.set_title("Semilog current density"); ax4.set_yscale('log')
    if not (ax1.lines or (hasattr(ax1_twin, 'lines') and ax1_twin.lines) or ax2.lines or ax3.lines or ax4.lines) :
         fig.clear()
         fig_text = f"{measurement_name}\nNo valid data to plot"
         if plot_data_package.get('csv_file_path'): fig_text += f"\nData file: {os.path.basename(plot_data_package['csv_file_path'])}"
         fig.text(0.5, 0.5, fig_text, ha='center', va='center', fontsize=12, transform=fig.transFigure)
    fig.suptitle(f'{measurement_name} Curve', fontsize=16, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.96])