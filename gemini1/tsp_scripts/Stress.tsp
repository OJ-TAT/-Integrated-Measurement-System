-- Stress.tsp
-- Description: Applies a constant DC voltage stress and logs data.
--              SMU A: Drain
--              Node[2].SMU A: Gate
--              Node[2].SMU B: Source (typically 0V)

-- Parameters to be replaced by Python:
-- {{VD_stress_val}}      : Drain voltage for stress (V)
-- {{VG_stress_val}}      : Gate voltage for stress (V)
-- {{VS_stress_val}}      : Source voltage for stress (V, typically 0)
-- {{stress_duration_val}}: Duration of the stress (s)
-- {{stress_measure_interval_val}}: Measurement interval during stress (s)
-- {{initial_settling_delay}}: Initial delay after applying stress voltages (s) -- New
-- {{IlimitDrain_stress}} : Drain current limit during stress (A)
-- {{IlimitGate_stress}}  : Gate current limit during stress (A)
-- {{IlimitSource_stress}}: Source current limit during stress (A)
-- {{Drain_nplc_stress}}  : Drain NPLC during stress
-- {{Gate_nplc_stress}}   : Gate NPLC during stress
-- {{Source_nplc_stress}} : Source NPLC during stress


tsplink.reset()
reset() -- Reset the instrument to default states

-- Configure SMU A (Drain) on the main instrument (e.g., 2657A or a 26xxB)
smua.reset()
smua.source.func = smua.OUTPUT_DCVOLTS
smua.source.levelv = 0 -- Initial safe level
smua.source.limiti = {{IlimitDrain_stress}}
smua.source.autorangev = smua.AUTORANGE_ON
smua.measure.autozero = smua.AUTOZERO_ONCE
smua.measure.autorangei = smua.AUTORANGE_ON
smua.measure.nplc = {{Drain_nplc_stress}}
smua.measure.delay = 0 -- Use explicit delay or timer
smua.nvbuffer1.clear() -- For current readings
smua.nvbuffer1.appendmode = 1
smua.nvbuffer1.collecttimestamps = 1 -- Primary timestamp source
smua.nvbuffer1.fillmode = smua.FILL_ONCE
smua.nvbuffer2.clear() -- For voltage readings
smua.nvbuffer2.appendmode = 1
smua.nvbuffer2.collecttimestamps = 0 -- Timestamps from buffer1 are primary
smua.nvbuffer2.fillmode = smua.FILL_ONCE

-- Configure Node[2].SMU A (Gate) on the 2636B
node[2].smua.reset()
node[2].smua.source.func = node[2].smua.OUTPUT_DCVOLTS
node[2].smua.source.levelv = 0 -- Initial safe level
node[2].smua.source.limiti = {{IlimitGate_stress}}
node[2].smua.source.autorangev = node[2].smua.AUTORANGE_ON
node[2].smua.measure.autozero = node[2].smua.AUTOZERO_ONCE
node[2].smua.measure.autorangei = node[2].smua.AUTORANGE_ON
node[2].smua.measure.nplc = {{Gate_nplc_stress}}
node[2].smua.measure.delay = 0
node[2].smua.nvbuffer1.clear() -- Gate current
node[2].smua.nvbuffer1.appendmode = 1
node[2].smua.nvbuffer1.collecttimestamps = 0
node[2].smua.nvbuffer1.fillmode = node[2].smua.FILL_ONCE
node[2].smua.nvbuffer2.clear() -- Gate voltage
node[2].smua.nvbuffer2.appendmode = 1
node[2].smua.nvbuffer2.collecttimestamps = 0
node[2].smua.nvbuffer2.fillmode = node[2].smua.FILL_ONCE

-- Configure Node[2].SMU B (Source) on the 2636B
node[2].smub.reset()
node[2].smub.source.func = node[2].smub.OUTPUT_DCVOLTS
node[2].smub.source.levelv = 0 -- Initial safe level
node[2].smub.source.limiti = {{IlimitSource_stress}}
node[2].smub.source.autorangev = node[2].smub.AUTORANGE_ON
node[2].smub.measure.autozero = node[2].smub.AUTOZERO_ONCE
node[2].smub.measure.autorangei = node[2].smub.AUTORANGE_ON
node[2].smub.measure.nplc = {{Source_nplc_stress}}
node[2].smub.measure.delay = 0
node[2].smub.nvbuffer1.clear() -- Source current
node[2].smub.nvbuffer1.appendmode = 1
node[2].smub.nvbuffer1.collecttimestamps = 0
node[2].smub.nvbuffer1.fillmode = node[2].smub.FILL_ONCE
node[2].smub.nvbuffer2.clear() -- Source voltage
node[2].smub.nvbuffer2.appendmode = 1
node[2].smub.nvbuffer2.collecttimestamps = 0
node[2].smub.nvbuffer2.fillmode = node[2].smub.FILL_ONCE

-- Clear all buffers again just before use (belt and suspenders)
smua.nvbuffer1.clear() 
smua.nvbuffer2.clear()
node[2].smua.nvbuffer1.clear()
node[2].smua.nvbuffer2.clear()
node[2].smub.nvbuffer1.clear()
node[2].smub.nvbuffer2.clear()

-- Apply stress voltages
smua.source.levelv = {{VD_stress_val}}
node[2].smua.source.levelv = {{VG_stress_val}}
node[2].smub.source.levelv = {{VS_stress_val}}

-- Turn on outputs
smua.source.output = smua.OUTPUT_ON
node[2].smua.source.output = node[2].smua.OUTPUT_ON
node[2].smub.source.output = node[2].smub.OUTPUT_ON -- Ensure Source SMU is ON

-- Display settings (optional, for instrument front panel)
display.smua.measure.func = display.MEASURE_DCAMPS -- Display Drain current
node[2].display.smua.measure.func = display.MEASURE_DCAMPS -- Display Gate current
node[2].display.smub.measure.func = display.MEASURE_DCAMPS -- Display Source current

-- Initial settling delay (New)
if {{initial_settling_delay}} > 0 then
    delay({{initial_settling_delay}})
end

-- Start measurement loop
timer.reset() -- Reset timer for stress duration
local current_time = 0
local stress_duration = {{stress_duration_val}}
local measure_interval = {{stress_measure_interval_val}}

-- Measure initial point at t=0 (or very close to it, after initial settling)
smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)
node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)
node[2].smub.measure.iv(node[2].smub.nvbuffer1, node[2].smub.nvbuffer2) -- Measure source V/I

-- Loop for the rest of the stress duration
while current_time < stress_duration do
    if measure_interval > 0 then
        delay(measure_interval)
    end
    current_time = timer.measure.t()
    if current_time >= stress_duration then -- Check if delay pushed us over
        -- Take one last measurement exactly at or after stress_duration if interval allows
        if stress_duration > 0 then -- Avoid double measurement if duration was 0
             smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)
             node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)
             node[2].smub.measure.iv(node[2].smub.nvbuffer1, node[2].smub.nvbuffer2)
        end
        break
    end

    smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)
    node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)
    node[2].smub.measure.iv(node[2].smub.nvbuffer1, node[2].smub.nvbuffer2) -- Measure source V/I

    -- Optional: Add compliance check here if needed
    -- if smua.source.compliance or node[2].smua.source.compliance or node[2].smub.source.compliance then
    --     print("Compliance reached during stress.")
    --     break -- Or handle as needed
    -- end
end

-- Turn off outputs and set to safe levels
smua.source.output = smua.OUTPUT_OFF
node[2].smua.source.output = node[2].smua.OUTPUT_OFF
node[2].smub.source.output = node[2].smub.OUTPUT_OFF

smua.source.levelv = 0
node[2].smua.source.levelv = 0
node[2].smub.source.levelv = 0

-- End of script