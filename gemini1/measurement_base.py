# measurement_base.py
import abc
import os
from datetime import datetime
import numpy as np
import instrument_utils
import config_settings 

class MeasurementBase(abc.ABC):
    def __init__(self, measurement_type_name_short, plot_file_suffix=".png"):
        self.measurement_type_name_short = measurement_type_name_short
        self.measurement_type_name_full = "" 
        self.plot_file_suffix = plot_file_suffix
        self.processed_data = {}
        self.raw_data = {}
        self.consistent_len = 0
        self.buffer_read_count_final = 0
        self.csv_file_path = ""
        self.png_file_path = ""
        self.base_name_generated = ""
        self.jd_unit_plot = "A.U."
        self.timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

    def _generate_file_paths(self, config):
        output_dir = config['output_dir']
        base_file_name_user = config.get('file_name', "")
        self.csv_file_path, self.png_file_path, self.base_name_generated = \
            instrument_utils.generate_file_paths(
                output_dir, base_file_name_user, self.measurement_type_name_short,
                self.timestamp_str, plot_file_suffix=self.plot_file_suffix
            )

    @abc.abstractmethod
    def _get_tsp_script_path_key(self, config):
        pass

    @abc.abstractmethod
    def _get_default_tsp_script_path(self, config):
        pass

    @abc.abstractmethod
    def _prepare_tsp_parameters(self, config):
        pass

    def _load_and_run_tsp(self, inst, config, tsp_params):
        tsp_script_path_key = self._get_tsp_script_path_key(config)
        tsp_script_path = config.get(tsp_script_path_key)
        if not tsp_script_path or not os.path.exists(tsp_script_path):
            raise FileNotFoundError(
                f"TSP script path '{tsp_script_path}' for {self.measurement_type_name_full} is invalid or not found."
            )
        if not instrument_utils.load_tsp_script(inst, tsp_script_path, tsp_params):
            raise RuntimeError(
                f"Failed to load/run TSP script '{tsp_script_path}' for {self.measurement_type_name_full}."
            )

    @abc.abstractmethod
    def _get_primary_buffer_info(self, config):
        pass

    @abc.abstractmethod
    def _get_buffers_to_read_config(self, config, buffer_read_count):
        pass

    def _query_and_read_buffers(self, inst, config):
        primary_buffer_obj_str, expected_total_points = self._get_primary_buffer_info(config)
        self.buffer_read_count_final = instrument_utils.query_instrument_buffer_count(
            inst, primary_buffer_obj_str, expected_total_points, self.measurement_type_name_full
        )
        if self.buffer_read_count_final <= 0:
            print(f"  Warning ({self.measurement_type_name_full}): Final buffer read count is {self.buffer_read_count_final}. Data might be missing.")
        
        buffers_config = self._get_buffers_to_read_config(config, self.buffer_read_count_final)
        self.raw_data, retrieved_counts = instrument_utils.read_instrument_buffers(
            inst, buffers_config, default_read_count=self.buffer_read_count_final
        )
        priority_keys_for_len = self._get_priority_keys_for_consistent_length()
        self.consistent_len = instrument_utils.determine_consistent_length(
            self.raw_data, priority_keys=priority_keys_for_len, retrieved_counts=retrieved_counts
        )

    def _get_priority_keys_for_consistent_length(self):
        return None

    def _perform_common_data_processing(self, config):
        if self.consistent_len == 0 and self.buffer_read_count_final <= 0:
            temp_buffers_config = self._get_buffers_to_read_config(config, 0)
            self.processed_data = {key: np.array([]) for key in temp_buffers_config.keys()}
            common_calc_keys = ['Is', 'Jd', 'Jg', 'Js', 'Time', 'Vg_actual_for_data']
            for k in common_calc_keys:
                if k not in self.processed_data:
                    self.processed_data[k] = np.array([])
            return

        self.processed_data = instrument_utils.normalize_data_arrays(self.raw_data, self.consistent_len)
        self.processed_data = instrument_utils.calculate_source_current(self.processed_data)

        # Correctly prepare device_details for calculate_current_densities
        device_details_for_calc = {
            'device_type': config.get('device_type', 'unknown'),
            'channel_width': config.get('channel_width_um', 0.0), # Use key 'channel_width_um' from config
            'area': config.get('area_um2', 0.0)                 # Use key 'area_um2' from config
        }
        self.processed_data, self.jd_unit_plot = instrument_utils.calculate_current_densities(
            self.processed_data, device_details_for_calc
        )
        
        # Ensure 'Time' key exists in processed_data, even if all NaNs
        if 'Time' not in self.processed_data:
            if self.consistent_len > 0:
                self.processed_data['Time'] = np.full(self.consistent_len, np.nan)
            else:
                self.processed_data['Time'] = np.array([])


    @abc.abstractmethod
    def _perform_specific_data_processing(self, config):
        pass

    @abc.abstractmethod
    def _get_csv_header_info(self, config):
        pass

    def _get_base_metadata_comments(self, config):
        comments = f"# Measurement Type: {self.measurement_type_name_full}\n"
        comments += f"# Timestamp: {self.timestamp_str}\n"
        comments += f"# Device Type: {config.get('device_type', 'N/A')}\n"
        # Display the um values as they are typically input by user or are primary
        comments += f"# Channel Width (um): {config.get('channel_width_um', 'N/A')}\n"
        comments += f"# Area (um^2): {config.get('area_um2', 'N/A')}\n"
        comments += f"# Output File (CSV): {os.path.basename(self.csv_file_path)}\n"
        comments += f"# Output File (PNG): {os.path.basename(self.png_file_path)}\n"
        comments += f"# JD Unit Plot: {self.jd_unit_plot}\n"
        return comments

    @abc.abstractmethod
    def _get_specific_metadata_comments(self, config):
        pass

    def _save_to_csv(self, config):
        header_cols, header_str = self._get_csv_header_info(config)
        base_comments = self._get_base_metadata_comments(config)
        specific_comments = self._get_specific_metadata_comments(config)
        full_comments = base_comments + specific_comments
        if not instrument_utils.save_data_to_csv(
                self.csv_file_path, self.processed_data, header_cols, header_str, comments=full_comments.strip()
        ):
            raise RuntimeError(f"Failed to save data to CSV: {self.csv_file_path}")

    @abc.abstractmethod
    def _prepare_plot_data_package(self, config):
        pass

    def perform_measurement_flow(self, config, inst):
        self.measurement_type_name_full = config.get("measurement_type_name", f"Unknown ({self.measurement_type_name_short})")
        self._generate_file_paths(config)
        config['csv_file_path_generated'] = self.csv_file_path
        config['png_file_path_generated'] = self.png_file_path
        config['base_name_generated'] = self.base_name_generated

        tsp_script_path_key = self._get_tsp_script_path_key(config)
        default_tsp_path = self._get_default_tsp_script_path(config)
        final_tsp_script_path = config.get(tsp_script_path_key, default_tsp_path)
        if not os.path.exists(final_tsp_script_path):
            raise FileNotFoundError(f"TSP script not found at {final_tsp_script_path} for {self.measurement_type_name_full}")
        config[tsp_script_path_key] = final_tsp_script_path

        tsp_params = self._prepare_tsp_parameters(config)
        self._load_and_run_tsp(inst, config, tsp_params)
        self._query_and_read_buffers(inst, config)

        if self.consistent_len == 0:
            print(f"  Warning/Info ({self.measurement_type_name_full}): Consistent data length is 0. "
                  f"Buffer reported {self.buffer_read_count_final} points. "
                  "Processed data will be initialized as empty or with NaNs.")
            # Initialize processed_data with empty arrays for expected keys if consistent_len is 0
            # This helps prevent KeyErrors in specific_data_processing if it expects certain keys.
            temp_buffers_config = self._get_buffers_to_read_config(config, 0) # Get potential keys
            self.processed_data = {key: np.array([]) for key in temp_buffers_config.keys()}
            # Ensure other common keys that might be calculated or expected also exist
            common_calc_keys = ['Is', 'Jd', 'Jg', 'Js', 'Time', 'Vg_actual_for_data', 'gm', 'SS']
            for k in common_calc_keys:
                 if k not in self.processed_data: self.processed_data[k] = np.array([])
        
        self._perform_common_data_processing(config)
        self._perform_specific_data_processing(config)
        self._save_to_csv(config)
        plot_data_package = self._prepare_plot_data_package(config)
        return plot_data_package