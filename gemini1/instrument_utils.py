# instrument_utils.py
import pyvisa
import numpy as np
import os
from contextlib import contextmanager
import sys
from datetime import datetime
import functools # For functools.wraps
import traceback # For full traceback in error dict

# --- Error Handling Decorator ---
def handle_measurement_errors(func):
    """
    A decorator to handle common exceptions for run_measurement functions.
    It expects the decorated function to take a 'config' dictionary as its first argument
    and for 'config' to potentially have 'measurement_type_name'.
    """
    @functools.wraps(func)
    def wrapper(config, *args, **kwargs):
        measurement_type_name = config.get("measurement_type_name", "Unknown Measurement")
        try:
            return func(config, *args, **kwargs)
        except pyvisa.errors.VisaIOError as ve:
            err_msg = f"VISA I/O Error ({measurement_type_name}): {ve}"
            return {"status": "error", "message": err_msg, "measurement_type_name": measurement_type_name, "traceback": traceback.format_exc()}
        except FileNotFoundError as fe:
            err_msg = f"File Not Found Error ({measurement_type_name}): {fe}"
            return {"status": "error", "message": err_msg, "measurement_type_name": measurement_type_name, "traceback": traceback.format_exc()}
        except RuntimeError as re_err:
            err_msg = f"Runtime Error ({measurement_type_name}): {re_err}"
            return {"status": "error", "message": err_msg, "measurement_type_name": measurement_type_name, "traceback": traceback.format_exc()}
        except ValueError as vale:
            err_msg = f"Value Error ({measurement_type_name}): {vale}"
            return {"status": "error", "message": err_msg, "measurement_type_name": measurement_type_name, "traceback": traceback.format_exc()}
        except Exception as e:
            err_msg = f"Unexpected error during {measurement_type_name}: {e}"
            tb_str = traceback.format_exc()
            return {"status": "error", "message": err_msg, "traceback": tb_str, "measurement_type_name": measurement_type_name}
    return wrapper

def query_buffer(inst, buffer_name, num_readings):
    """检查并查询缓冲区数据"""
    try:
        num_readings_int = int(num_readings)
        if num_readings_int <= 0:
            # print(f"  Query_buffer: num_readings is {num_readings_int} for {buffer_name}. Will try to read all if possible by TSP printbuffer.")
            pass
        cmd = f'printbuffer(1, {num_readings_int}, {buffer_name})'
        return inst.query(cmd).strip()
    except pyvisa.errors.VisaIOError as e:
        # print(f"查询缓冲区 {buffer_name} 时发生VISA错误: {str(e)}", file=sys.stderr)
        raise  # Re-raise the VisaIOError
    except Exception as e:
        # print(f"查询缓冲区 {buffer_name} 时发生一般错误: {str(e)}", file=sys.stderr)
        raise RuntimeError(f"查询缓冲区 {buffer_name} 时发生一般错误: {str(e)}") from e

def safe_float_convert(data_str):
    """安全地将字符串转换为浮点数数组"""
    try:
        return np.array([float(x) for x in data_str.split(',') if x.strip()])
    except ValueError as ve:
        # print(f"  Safe_float_convert: ValueError converting data string: '{data_str[:50]}...'", file=sys.stderr)
        raise  # Re-raise the ValueError

def load_tsp_script(inst, script_path, tsp_params):
    """加载TSP脚本并运行，替换占位符。"""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            tsp_script_template = f.read()

        tsp_script = tsp_script_template
        for key, value in tsp_params.items():
            placeholder = "{{" + key + "}}"
            tsp_script = tsp_script.replace(placeholder, str(value))

        inst.write("loadscript")
        inst.write(tsp_script)
        inst.write("endscript")
        inst.write("script.run()")
        # print(f"  TSP script '{os.path.basename(script_path)}' loaded and run.")
        return True
    except FileNotFoundError as fe:
        # print(f"TSP脚本加载失败: 在 {script_path} 未找到文件", file=sys.stderr)
        raise  # Re-raise the FileNotFoundError
    except pyvisa.errors.VisaIOError as ve:
        # print(f"在 {script_path} 的TSP脚本加载/运行期间发生VISA错误: {str(e)}", file=sys.stderr)
        raise  # Re-raise the VisaIOError
    except Exception as e:
        # print(f"在 {script_path} 的TSP脚本加载/运行期间发生一般错误: {str(e)}", file=sys.stderr)
        raise RuntimeError(f"在 {script_path} 的TSP脚本加载/运行期间发生一般错误: {str(e)}") from e

@contextmanager
def visa_instrument(gpib_address, timeout, measurement_type_name="测量"):
    rm = None
    inst = None
    try:
        # print(f"  Connecting to VISA instrument: {gpib_address} for {measurement_type_name}...")
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(gpib_address)
        inst.timeout = timeout
        # print(f"  Successfully connected. Timeout: {timeout/1000}s.")
        yield inst
    except pyvisa.errors.VisaIOError as ve:
        error_message = f"连接时 {measurement_type_name} 发生VISA I/O错误: {str(ve)}。请检查GPIB地址、连接和仪器电源。"
        raise RuntimeError(error_message) from ve
    except Exception as e:
        error_message = f"{measurement_type_name} 连接期间发生意外错误: {str(e)}"
        raise RuntimeError(error_message) from e
    finally:
        # print(f"  Closing VISA instrument connection for {measurement_type_name} ({gpib_address})...")
        if inst is not None:
            try:
                inst.close()
            except Exception as e_close:
                print(f"为 {measurement_type_name} ({gpib_address}) 关闭仪器时出错: {str(e_close)}", file=sys.stderr)
        if rm is not None:
            try:
                # rm.close() # Typically not needed for individual resource closure
                pass
            except Exception as e_rm_close:
                print(f"为 {measurement_type_name} 关闭资源管理器时出错: {str(e_rm_close)}", file=sys.stderr)
        # print(f"  VISA instrument connection closed for {measurement_type_name}.")

def generate_file_paths(output_dir, base_file_name_user, measurement_suffix, timestamp_str, plot_file_suffix=".png"):
    cleaned_base_name_user = base_file_name_user.strip().replace(' ', '_') if base_file_name_user and base_file_name_user.strip() else ""
    if cleaned_base_name_user:
        base_name_generated = f"{cleaned_base_name_user}_{measurement_suffix}_{timestamp_str}"
    else:
        base_name_generated = f"{measurement_suffix}_{timestamp_str}"
    os.makedirs(output_dir, exist_ok=True)
    csv_file_path = os.path.join(output_dir, f"{base_name_generated}.csv")
    png_file_path = os.path.join(output_dir, f"{base_name_generated}{plot_file_suffix}")
    return csv_file_path, png_file_path, base_name_generated

def query_instrument_buffer_count(inst, primary_buffer_object_str, expected_count, measurement_type_name=""):
    buffer_read_count_final = expected_count
    context_msg = f"({measurement_type_name}, 缓冲区: {primary_buffer_object_str})" if measurement_type_name else f"(缓冲区: {primary_buffer_object_str})"
    try:
        actual_n_str = inst.query(f'print({primary_buffer_object_str}.n)').strip()
        if actual_n_str.lower() == 'nil':
            # print(f"  仪器报告主缓冲区大小为 'nil' {context_msg}。使用计算值: {expected_count}")
            pass
        else:
            reported_n = int(float(actual_n_str))
            if reported_n > 0:
                buffer_read_count_final = reported_n
    except Exception: # Catch all for query issues
        # print(f"  查询主缓冲区大小时出错 {context_msg}。使用计算值: {expected_count}", file=sys.stderr)
        pass # Keep expected_count
    if buffer_read_count_final <= 0 and expected_count > 0:
        buffer_read_count_final = expected_count
    return buffer_read_count_final

def read_instrument_buffers(inst, buffers_to_read_config, default_read_count=0):
    raw_data = {}
    actual_points_retrieved_counts = []
    for name, (buffer_cmd_path, expected_count_for_buffer) in buffers_to_read_config.items():
        current_read_count = default_read_count
        if expected_count_for_buffer > 0: # If a specific count is expected for this buffer
            current_read_count = expected_count_for_buffer
        raw_str = query_buffer(inst, buffer_cmd_path, current_read_count)
        converted_data = safe_float_convert(raw_str)
        raw_data[name] = converted_data
        actual_points_retrieved_counts.append(len(converted_data))
    return raw_data, actual_points_retrieved_counts

def determine_consistent_length(raw_data_dict, priority_keys=None, retrieved_counts=None):
    if priority_keys:
        for key in priority_keys:
            if key in raw_data_dict and isinstance(raw_data_dict[key], np.ndarray) and len(raw_data_dict[key]) > 0:
                return len(raw_data_dict[key])
    if retrieved_counts:
        non_empty_counts = [c for c in retrieved_counts if c > 0]
        if non_empty_counts:
            return max(non_empty_counts) # Fallback to max retrieved if priority keys fail
    max_len = 0
    for arr in raw_data_dict.values():
        if isinstance(arr, np.ndarray) and len(arr) > max_len:
            max_len = len(arr)
    return max_len

def normalize_data_arrays(raw_data_dict, consistent_length):
    processed_data = {}
    if consistent_length == 0:
        for name in raw_data_dict.keys():
            processed_data[name] = np.array([])
        return processed_data

    for name, arr in raw_data_dict.items():
        if not isinstance(arr, np.ndarray):
            processed_data[name] = np.full(consistent_length, np.nan)
            continue
        if len(arr) == consistent_length:
            processed_data[name] = arr
        elif len(arr) > consistent_length:
            processed_data[name] = arr[:consistent_length]
        else:
            padded_arr = np.full(consistent_length, np.nan)
            if len(arr) > 0 : padded_arr[:len(arr)] = arr
            processed_data[name] = padded_arr
    return processed_data

def calculate_source_current(processed_data,
                             id_key='Id', ig_key='Ig',
                             is_buffer_key='Is_buffer', is_out_key='Is'):
    """
    Calculates source current (Is).
    Prioritizes directly measured Is_buffer if it exists and has data.
    Otherwise, calculates Is = -(Id + Ig).
    """
    ref_len_for_calc = 0
    id_data_for_len_check = processed_data.get(id_key)
    ig_data_for_len_check = processed_data.get(ig_key)

    if isinstance(id_data_for_len_check, np.ndarray) and id_data_for_len_check.size > 0:
        ref_len_for_calc = id_data_for_len_check.size
    elif isinstance(ig_data_for_len_check, np.ndarray) and ig_data_for_len_check.size > 0:
        ref_len_for_calc = ig_data_for_len_check.size

    is_buffer_data = processed_data.get(is_buffer_key)
    use_is_buffer_directly = False

    if isinstance(is_buffer_data, np.ndarray) and is_buffer_data.size > 0:
        use_is_buffer_directly = True
    else:
        pass # Is_buffer not suitable or not found, will attempt to calculate Is

    if use_is_buffer_directly:
        processed_data[is_out_key] = is_buffer_data
    else:
        id_data = processed_data.get(id_key)
        ig_data = processed_data.get(ig_key)

        valid_id_for_calc = isinstance(id_data, np.ndarray) and (ref_len_for_calc == 0 or id_data.size == ref_len_for_calc)
        valid_ig_for_calc = isinstance(ig_data, np.ndarray) and (ref_len_for_calc == 0 or ig_data.size == ref_len_for_calc)

        if ref_len_for_calc == 0:
            if valid_id_for_calc and id_data.size > 0: ref_len_for_calc = id_data.size
            elif valid_ig_for_calc and ig_data.size > 0: ref_len_for_calc = ig_data.size

        valid_id_for_calc = isinstance(id_data, np.ndarray) and id_data.size == ref_len_for_calc
        valid_ig_for_calc = isinstance(ig_data, np.ndarray) and ig_data.size == ref_len_for_calc

        if valid_id_for_calc and valid_ig_for_calc and ref_len_for_calc > 0:
            processed_data[is_out_key] = -(id_data + ig_data)
        else:
            processed_data[is_out_key] = np.full(ref_len_for_calc if ref_len_for_calc > 0 else 0, np.nan)

    if is_out_key not in processed_data or not isinstance(processed_data[is_out_key], np.ndarray):
        processed_data[is_out_key] = np.array([])

    return processed_data


def calculate_current_densities(processed_data, device_config,
                                current_keys=('Id', 'Ig', 'Is'),
                                density_keys=('Jd', 'Jg', 'Js')):
    device_type = device_config.get('device_type', 'unknown')
    try: channel_width_um = float(device_config.get('channel_width', 0))
    except (ValueError, TypeError): channel_width_um = 0
    try: area_um2 = float(device_config.get('area', 0))
    except (ValueError, TypeError): area_um2 = 0

    J_coeff = 0
    jd_unit_plot = 'A.U.'

    if device_type == "lateral":
        jd_unit_plot = 'mA/mm'
        if channel_width_um > 0:
            channel_width_mm = channel_width_um * 1e-3
            J_coeff = 1e3 / channel_width_mm
    elif device_type == "vertical":
        jd_unit_plot = 'A/cm^2'
        if area_um2 > 0:
            area_cm2 = area_um2 * 1e-8
            J_coeff = 1 / area_cm2

    ref_len = 0
    for key in current_keys:
        if key in processed_data and isinstance(processed_data[key], np.ndarray) and processed_data[key].size > 0:
            ref_len = len(processed_data[key])
            break
    if ref_len == 0 and 'Id' in processed_data and isinstance(processed_data['Id'], np.ndarray):
        ref_len = len(processed_data['Id'])


    for i, current_key in enumerate(current_keys):
        density_key = density_keys[i]
        current_array = processed_data.get(current_key)

        if isinstance(current_array, np.ndarray) and current_array.size == ref_len and ref_len > 0 :
            if J_coeff != 0:
                processed_data[density_key] = current_array * J_coeff
            else:
                processed_data[density_key] = np.where(np.isnan(current_array), np.nan, 0.0)
        else:
            processed_data[density_key] = np.full(ref_len if ref_len > 0 else 0, np.nan)
    return processed_data, jd_unit_plot

def save_data_to_csv(file_path, data_dict, column_keys, header_string, comments=""):
    try:
        if not column_keys:
            return False
        expected_len = -1
        first_valid_key_found = False
        for key in column_keys:
            arr = data_dict.get(key)
            if isinstance(arr, np.ndarray) and arr.ndim == 1:
                if not first_valid_key_found:
                    expected_len = len(arr)
                    first_valid_key_found = True
        if not first_valid_key_found and expected_len == -1:
            with open(file_path, 'w', encoding='utf-8') as f:
                if comments:
                    f.write(comments)
                    if not comments.endswith('\n'): f.write('\n')
                f.write(header_string + '\n')
            return True

        save_data_arrays = []
        for key in column_keys:
            arr = data_dict.get(key)
            if isinstance(arr, np.ndarray) and arr.ndim == 1:
                if len(arr) == expected_len:
                    save_data_arrays.append(arr)
                else:
                    normalized_arr = np.full(expected_len, np.nan)
                    common_length_to_copy = min(len(arr), expected_len)
                    if common_length_to_copy > 0 : normalized_arr[:common_length_to_copy] = arr[:common_length_to_copy]
                    save_data_arrays.append(normalized_arr)
            elif key in data_dict :
                 save_data_arrays.append(np.full(expected_len, np.nan))
            else:
                save_data_arrays.append(np.full(expected_len, np.nan))

        if not save_data_arrays:
            with open(file_path, 'w', encoding='utf-8') as f:
                if comments:
                    f.write(comments)
                    if not comments.endswith('\n'): f.write('\n')
                f.write(header_string + '\n')
            return True

        save_data_np = np.column_stack(save_data_arrays) if expected_len > 0 else np.array([]).reshape(0, len(save_data_arrays))

        with open(file_path, 'w', encoding='utf-8') as f:
            if comments:
                f.write(comments)
                if not comments.endswith('\n'): f.write('\n')
            np.savetxt(f, save_data_np, delimiter=",", header=header_string, comments="", fmt='%.9e')
        return True
    except Exception as e:
        print(f"  保存数据到CSV {file_path} 时出错: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False

def get_plot_suffix_for_measurement(measurement_type_name_short):
    if measurement_type_name_short == "Breakdown":
        return "_linear_log.png"
    return ".png"

def get_short_measurement_type(filename):
    if "GateTransfer" in filename: return "GateTransfer"
    if "Output" in filename: return "Output"
    if "Breakdown" in filename: return "Breakdown"
    if "Diode" in filename: return "Diode"
    if "Stress" in filename: return "Stress" # Added for stress
    return None
