# config_settings.py
import os
import sys # Import sys for stderr

# --- TSP Script Path Configuration ---
try:
    _CONFIG_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    TSP_SCRIPT_BASE_PATH = os.path.join(_CONFIG_FILE_DIR, "tsp_scripts")
    if not os.path.isdir(TSP_SCRIPT_BASE_PATH):
        print(f"Warning: Relative TSP script path based on __file__ not found: {TSP_SCRIPT_BASE_PATH}", file=sys.stderr)
        TSP_SCRIPT_BASE_PATH = os.path.join(os.getcwd(), "tsp_scripts")
        if not os.path.isdir(TSP_SCRIPT_BASE_PATH):
            print(f"Warning: Relative TSP script path based on CWD not found: {TSP_SCRIPT_BASE_PATH}", file=sys.stderr)
            print("Critical Error: TSP script directory could not be determined. Please ensure 'tsp_scripts' directory exists relative to the application or current working directory.", file=sys.stderr)
            TSP_SCRIPT_BASE_PATH = "" # Set to empty string
        else:
            print(f"Info: Using TSP script path based on CWD: {TSP_SCRIPT_BASE_PATH}")
    else:
        print(f"Info: Using TSP script path based on __file__: {TSP_SCRIPT_BASE_PATH}")
except NameError: # Should ideally not happen if __file__ is defined
    print("Warning: Could not determine script directory via __file__. Trying CWD for TSP_SCRIPT_BASE_PATH.", file=sys.stderr)
    TSP_SCRIPT_BASE_PATH = os.path.join(os.getcwd(), "tsp_scripts")
    if not os.path.isdir(TSP_SCRIPT_BASE_PATH):
        print(f"Warning: Relative TSP script path based on CWD not found: {TSP_SCRIPT_BASE_PATH}", file=sys.stderr)
        print("Critical Error: TSP script directory could not be determined. Please ensure 'tsp_scripts' directory exists relative to the application or current working directory.", file=sys.stderr)
        TSP_SCRIPT_BASE_PATH = "" # Set to empty string
    else:
        print(f"Info: Using TSP script path based on CWD: {TSP_SCRIPT_BASE_PATH}")

# Define DEFAULT_TSP_* paths using the determined TSP_SCRIPT_BASE_PATH
# If TSP_SCRIPT_BASE_PATH is "", os.path.join will correctly create paths relative to CWD at the point of use (e.g. "GateSweep.tsp"),
# which will likely not exist if the 'tsp_scripts' folder isn't in CWD, leading to FileNotFoundError later as intended.
DEFAULT_TSP_GATE_TRANSFER = os.path.join(TSP_SCRIPT_BASE_PATH, "GateSweep.tsp")
DEFAULT_TSP_OUTPUT_CHAR = os.path.join(TSP_SCRIPT_BASE_PATH, "IDVD.tsp")
DEFAULT_TSP_BREAKDOWN = os.path.join(TSP_SCRIPT_BASE_PATH, "BV.tsp")
DEFAULT_TSP_DIODE = os.path.join(TSP_SCRIPT_BASE_PATH, "diode.tsp")
DEFAULT_TSP_STRESS = os.path.join(TSP_SCRIPT_BASE_PATH, "Stress.tsp")

# --- Default Instrument Settings ---
DEFAULT_GPIB_ADDRESS = 'GPIB0::30::INSTR' # 请根据您的实际GPIB地址修改
DEFAULT_TIMEOUT = 3000000
DIODE_TIMEOUT = 30000
STRESS_TIMEOUT = 3600000 # Example: 1 hour for potentially long stress tests

# --- Buffer Definitions (confirm if Stress.tsp uses these consistently or needs new ones) ---
# These are general and should be fine if Stress.tsp uses the same SMU mapping for D, G, S
SMUA_NVBUFFER1 = "smua.nvbuffer1" # Typically Drain Current
SMUA_NVBUFFER2 = "smua.nvbuffer2" # Typically Drain Voltage
DRAIN_SMU_VOLTAGE_READINGS_BUFFER_PATH = f"{SMUA_NVBUFFER2}.readings"
DRAIN_SMU_CURRENT_READINGS_BUFFER_PATH = f"{SMUA_NVBUFFER1}.readings"
DRAIN_SMU_TIMESTAMP_BUFFER_PATH = f"{SMUA_NVBUFFER1}.timestamps" # Stress TSP uses this as primary

NODE2_SMUA_NVBUFFER1 = "node[2].smua.nvbuffer1" # Typically Gate Current
NODE2_SMUA_NVBUFFER2 = "node[2].smua.nvbuffer2" # Typically Gate Voltage
GATE_SMU_TIMESTAMP_BUFFER_PATH = f"{NODE2_SMUA_NVBUFFER1}.timestamps" # Secondary, if needed
GATE_SMU_VOLTAGE_SOURCEVALUES_BUFFER_PATH = f"{NODE2_SMUA_NVBUFFER2}.sourcevalues"
GATE_SMU_VOLTAGE_READINGS_BUFFER_PATH = f"{NODE2_SMUA_NVBUFFER2}.readings"
GATE_SMU_CURRENT_READINGS_BUFFER_PATH = f"{NODE2_SMUA_NVBUFFER1}.readings"

NODE2_SMUB_NVBUFFER1 = "node[2].smub.nvbuffer1" # Typically Source Current
NODE2_SMUB_NVBUFFER2 = "node[2].smub.nvbuffer2" # Typically Source Voltage
SOURCE_SMU_IS_BUFFER_READINGS_PATH = f"{NODE2_SMUB_NVBUFFER1}.readings"
SOURCE_SMU_VS_BUFFER_READINGS_PATH = f"{NODE2_SMUB_NVBUFFER2}.readings" # For Vs_read

# Diode specific (retained for completeness, Stress.tsp uses DGS mapping)
ANODE_TIMESTAMP_BUFFER_PATH = f"{SMUA_NVBUFFER1}.timestamps"
ANODE_VOLTAGE_SET_BUFFER_PATH = f"{SMUA_NVBUFFER2}.sourcevalues"
ANODE_VOLTAGE_READ_BUFFER_PATH = f"{SMUA_NVBUFFER2}.readings"
ANODE_CURRENT_READ_BUFFER_PATH = f"{SMUA_NVBUFFER1}.readings"
CATHODE_CURRENT_READ_BUFFER_PATH = f"{NODE2_SMUA_NVBUFFER1}.readings"


# --- Config Keys ---
CONFIG_KEY_TSP_GATE_TRANSFER = "TSP_SCRIPT_PATH_GATE_TRANSFER"
CONFIG_KEY_TSP_OUTPUT = "TSP_SCRIPT_PATH_OUTPUT"
CONFIG_KEY_TSP_BREAKDOWN = "TSP_SCRIPT_PATH_BREAKDOWN"
CONFIG_KEY_TSP_DIODE = "TSP_SCRIPT_PATH_DIODE"
CONFIG_KEY_TSP_STRESS = "TSP_SCRIPT_PATH_STRESS" # New Stress config key
CONFIG_KEY_GPIB_ADDRESS = "GPIB_ADDRESS"
CONFIG_KEY_TIMEOUT = "TIMEOUT"

# --- Default GUI Settings ---
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "TSP_Python_Measurements_Output")

# --- Default Settling Delays ---
DEFAULT_SETTLING_DELAY_S = "0.1" # General default

# Gate Transfer Defaults
GT_DEFAULT_ILIMIT_DRAIN = "0.1"
GT_DEFAULT_ILIMIT_GATE = "0.01"
GT_DEFAULT_DRAIN_NPLC = "1"
GT_DEFAULT_GATE_NPLC = "1"
GT_DEFAULT_VG_START = "-1.0"
GT_DEFAULT_VG_STOP = "2.0"
GT_DEFAULT_VG_STEP = "0.1"
GT_DEFAULT_VD = "1"
GT_DEFAULT_SETTLING_DELAY = DEFAULT_SETTLING_DELAY_S
GT_DEFAULT_ENABLE_BACKWARD = True # Added for gui_utils checkbox reset

# Output Characteristics Defaults
OC_DEFAULT_ILIMIT_DRAIN = "0.1"
OC_DEFAULT_ILIMIT_GATE = "0.01"
OC_DEFAULT_DRAIN_NPLC = "1"
OC_DEFAULT_GATE_NPLC = "1"
OC_DEFAULT_VG_START = "-1.0"
OC_DEFAULT_VG_STOP = "2.0"
OC_DEFAULT_VG_STEP = "3" # This is number of segments for Vg
OC_DEFAULT_VD_START = "0.0"
OC_DEFAULT_VD_STOP = "5.0"
OC_DEFAULT_VD_STEP = "0.2"
OC_DEFAULT_SETTLING_DELAY = DEFAULT_SETTLING_DELAY_S

# Breakdown Defaults
BD_DEFAULT_ILIMIT_DRAIN = "0.01"
BD_DEFAULT_ILIMIT_GATE = "0.001"
BD_DEFAULT_DRAIN_NPLC = "1"
BD_DEFAULT_GATE_NPLC = "1"
BD_DEFAULT_VG = "-1.0"
BD_DEFAULT_VD_START = "0"
BD_DEFAULT_VD_STOP = "100"
BD_DEFAULT_VD_STEP = "1"
BD_DEFAULT_SETTLING_DELAY = DEFAULT_SETTLING_DELAY_S

# Diode Defaults
DIODE_DEFAULT_ILIMIT_ANODE = "0.1"
DIODE_DEFAULT_ILIMIT_CATHODE = "0.1"
DIODE_DEFAULT_ANODE_NPLC = "1"
DIODE_DEFAULT_CATHODE_NPLC = "1"
DIODE_DEFAULT_VANODE_START = "0"
DIODE_DEFAULT_VANODE_STOP = "3"
DIODE_DEFAULT_VANODE_STEP = "0.1"
DIODE_DEFAULT_SETTLING_DELAY = DEFAULT_SETTLING_DELAY_S
DIODE_DEFAULT_ENABLE_BACKWARD = True # Added for gui_utils checkbox reset

# Stress Test Defaults (New Section)
STRESS_DEFAULT_VD_STRESS = "5.0"       # (V)
STRESS_DEFAULT_VG_STRESS = "2.0"       # (V)
STRESS_DEFAULT_VS_STRESS = "0.0"       # (V) - Source voltage, typically 0
STRESS_DEFAULT_DURATION = "60"         # (s) - Stress duration
STRESS_DEFAULT_MEASURE_INTERVAL = "1"  # (s) - Measurement interval during stress
STRESS_DEFAULT_INITIAL_SETTLING_DELAY = "0.1" # (s) - Initial delay before stress loop starts
STRESS_DEFAULT_ILIMIT_DRAIN = "0.1"    # (A)
STRESS_DEFAULT_ILIMIT_GATE = "0.01"   # (A)
STRESS_DEFAULT_ILIMIT_SOURCE = "0.1"   # (A) - Current limit for the source SMU
STRESS_DEFAULT_DRAIN_NPLC = "1"
STRESS_DEFAULT_GATE_NPLC = "1"
STRESS_DEFAULT_SOURCE_NPLC = "1"       # NPLC for the source SMU

# Device Parameter Defaults (Common)
DEVICE_DEFAULT_CHANNEL_WIDTH_UM = "100.0"
DEVICE_DEFAULT_AREA_UM2 = "10000.0"

# Mobility related defaults (used in gui_utils.reset_params_to_default if passed as StringVar)
GT_DEFAULT_CHANNEL_LENGTH_UM = "10.0" # Example default
GT_DEFAULT_C_OX_NF_CM2 = "34.5"      # Example default (for 100nm SiO2)
