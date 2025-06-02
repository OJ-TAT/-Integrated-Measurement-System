-- GateSweep.tsp
Vs = 0
tsplink.reset()
reset()
-- 2657A (Drain)
smua.reset()
smua.source.func = smua.OUTPUT_DCVOLTS
smua.source.levelv = 0
smua.source.limiti = {{IlimitDrain}}
smua.source.autorangev = smua.AUTORANGE_ON
smua.measure.autozero = smua.AUTOZERO_ONCE
smua.measure.autorangei = smua.AUTORANGE_ON
smua.measure.nplc = {{Drain_nplc}}
smua.measure.delay = 0 -- Instrument's internal measure delay, not the settling delay
smua.nvbuffer1.clear()
smua.nvbuffer1.appendmode = 1
smua.nvbuffer1.collecttimestamps = 1
smua.nvbuffer1.collectsourcevalues = 1
smua.nvbuffer1.fillmode = smua.FILL_ONCE
smua.nvbuffer2.clear()
smua.nvbuffer2.appendmode = 1
smua.nvbuffer2.collecttimestamps = 1
smua.nvbuffer2.collectsourcevalues = 1
smua.nvbuffer2.fillmode = smua.FILL_ONCE


-- 2636B (Gate)
node[2].smua.reset()
node[2].smua.source.func = node[2].smua.OUTPUT_DCVOLTS
node[2].smua.source.levelv = 0
node[2].smua.source.limiti = {{IlimitGate}}
node[2].smua.source.autorangev = node[2].smua.AUTORANGE_ON
node[2].smua.measure.autozero = node[2].smua.AUTOZERO_ONCE
node[2].smua.measure.autorangei = node[2].smua.AUTORANGE_ON
node[2].smua.measure.nplc = {{Gate_nplc}}
node[2].smua.measure.delay = 0 -- Instrument's internal measure delay
node[2].smua.nvbuffer1.clear()
node[2].smua.nvbuffer1.appendmode = 1
node[2].smua.nvbuffer1.collecttimestamps = 1
node[2].smua.nvbuffer1.collectsourcevalues = 1
node[2].smua.nvbuffer1.fillmode = node[2].smua.FILL_ONCE
node[2].smua.nvbuffer2.clear()
node[2].smua.nvbuffer2.appendmode = 1
node[2].smua.nvbuffer2.collecttimestamps = 1
node[2].smua.nvbuffer2.collectsourcevalues = 1
node[2].smua.nvbuffer2.fillmode = node[2].smua.FILL_ONCE


-- 2636B (Source)
node[2].smub.reset()
node[2].smub.source.func = node[2].smub.OUTPUT_DCVOLTS
node[2].smub.source.levelv = 0
node[2].smub.source.limiti = {{IlimitDrain}} -- Assuming same limit as Drain for Source, adjust if needed
node[2].smub.source.autorangev = node[2].smub.AUTORANGE_ON
node[2].smub.measure.autozero = node[2].smub.AUTOZERO_ONCE
node[2].smub.measure.autorangei = node[2].smub.AUTORANGE_ON
node[2].smub.measure.nplc = {{Drain_nplc}} -- Assuming same NPLC as Drain for Source
node[2].smub.measure.delay = 0 -- Instrument's internal measure delay
node[2].smub.nvbuffer1.clear()
node[2].smub.nvbuffer1.appendmode = 1
node[2].smub.nvbuffer1.collecttimestamps = 1 -- Still collect timestamps for buffer1
node[2].smub.nvbuffer1.collectsourcevalues = 1 -- Still collect source values for buffer1
node[2].smub.nvbuffer1.fillmode = node[2].smub.FILL_ONCE
-- node[2].smub.nvbuffer2 is not explicitly used by measure.i, but clearing it is good practice
node[2].smub.nvbuffer2.clear()
node[2].smub.nvbuffer2.fillmode = node[2].smub.FILL_ONCE


-- Clear buffers before sweep
smua.nvbuffer1.clear()
smua.nvbuffer2.clear()
node[2].smua.nvbuffer1.clear()
node[2].smua.nvbuffer2.clear()
node[2].smub.nvbuffer1.clear()
node[2].smub.nvbuffer2.clear()
timer.reset()

-- Apply fixed bias
smua.source.levelv = {{Vd}}
node[2].smub.source.levelv = Vs
smua.source.output = 1

-- Sweep Gate voltage and measure
node[2].smub.source.output = 1
node[2].smua.source.output = 1
display.smua.measure.func = 0
node[2].display.smua.measure.func = 0
node[2].display.smub.measure.func = 0

N_st =  (-(({{Vg_start}})-({{Vg_stop}}))/({{step}}))+1
settling_delay_val = {{settling_delay}} -- Store in a local variable

if {{enable_backward}} == 1 then

	for i = 1, N_st do
    	Vg = {{Vg_start}} + ((i - 1) * {{step}})
    	node[2].smua.source.levelv = Vg

    	delay(settling_delay_val) -- Use local variable for delay

    	-- Drain current & voltage
    	smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)

    	-- Gate current & voltage
    	node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)

    	--Source current
    	node[2].smub.measure.i(node[2].smub.nvbuffer1) -- Use measure.i
		
        DrainTestCmpl = smua.source.compliance
		GateTestCmpl = node[2].smua.source.compliance
        SourceTestCmpl = node[2].smub.source.compliance 
		
        if DrainTestCmpl == true or GateTestCmpl == true or SourceTestCmpl == true then
			break
		end

	end

	for i = 1, N_st do
    	Vg = {{Vg_stop}} - ((i - 1) * {{step}})
    	node[2].smua.source.levelv = Vg

    	delay(settling_delay_val) -- Use local variable for delay

    	-- Drain current & voltage
    	smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)

    	-- Gate current & voltage
    	node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)

    	-- Source current 
    	node[2].smub.measure.i(node[2].smub.nvbuffer1) -- CHANGED to measure.i for consistency
		
        DrainTestCmpl = smua.source.compliance
		GateTestCmpl = node[2].smua.source.compliance
        SourceTestCmpl = node[2].smub.source.compliance 
		
        if DrainTestCmpl == true or GateTestCmpl == true or SourceTestCmpl == true then
			break
		end
	end
else
    for i = 1, N_st do
        Vg = {{Vg_start}} + ((i - 1) * {{step}})
        node[2].smua.source.levelv = Vg

        delay(settling_delay_val) -- Use local variable for delay

        -- Drain current & voltage
        smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)

        -- Gate current & voltage
        node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2)

         --Source current
        node[2].smub.measure.i(node[2].smub.nvbuffer1) -- Use measure.i
		
        DrainTestCmpl = smua.source.compliance
		GateTestCmpl = node[2].smua.source.compliance
        SourceTestCmpl = node[2].smub.source.compliance 

		if DrainTestCmpl == true or GateTestCmpl == true or SourceTestCmpl == true then
			break
		end
    end
end

	smua.source.levelv = 0
	node[2].smua.source.levelv = 0
 	node[2].smub.source.levelv = 0
	smua.source.output = 0
	node[2].smua.source.output = 0
    node[2].smub.source.output = 0

