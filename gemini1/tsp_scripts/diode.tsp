
tsplink.reset()
reset()
-- 2657A (Drain)
smua.reset()
smua.source.func = smua.OUTPUT_DCVOLTS
smua.source.levelv = 0
smua.source.limiti = {{IlimitAnode}}
smua.source.autorangev = smua.AUTORANGE_ON
smua.measure.autozero = smua.AUTOZERO_ONCE
smua.measure.autorangei = smua.AUTORANGE_ON
smua.measure.nplc = {{Anode_nplc}}
smua.measure.delay = 0
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
node[2].smua.source.limiti = {{IlimitCathode}}
node[2].smua.source.autorangev = node[2].smua.AUTORANGE_ON
node[2].smua.measure.autozero = node[2].smua.AUTOZERO_ONCE
node[2].smua.measure.autorangei = node[2].smua.AUTORANGE_ON
node[2].smua.measure.nplc = {{Cathode_nplc}}
node[2].smua.measure.delay = 0
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

smua.nvbuffer1.clear()
smua.nvbuffer2.clear()
node[2].smua.nvbuffer1.clear()
node[2].smua.nvbuffer2.clear()
      


smua.source.levelv = {{Vanode_start}}
node[2].smua.source.levelv = 0


smua.source.output = 1
node[2].smua.source.output = 1


display.smua.measure.func = 0
node[2].display.smua.measure.func = 0


-- Main measurement loop

N_st =  (-(({{Vanode_start}})-({{Vanode_stop}}))/({{Vanode_step}}))+1

smua.source.output = 1
node[2].smua.source.output = 1

if {{enable_backward}} == 1 then
    for i = 1, N_st do
        Vanode = {{Vanode_start}} + (i-1)*{{Vanode_step}}
        smua.source.levelv = Vanode
        delay({{settling_delay}})  -- Add settling time parameter
    
        -- Measure anode voltage/current and cathode voltage/current
        smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)         -- Anode: I/V
        node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2) -- Cathode: I/V
    
        AnodeTestCmpl = smua.source.compliance
        CathodeTestCmpl = node[2].smua.source.compliance
	
		 if AnodeTestCmpl == true or CathodeTestCmpl == true then
			 break
		 end
    end

    for i = 1, N_st do
        Vanode = {{Vanode_stop}} - (i-1)*{{Vanode_step}}
        smua.source.levelv = Vanode
        delay({{settling_delay}})  -- Add settling time parameter
    
        -- Measure anode voltage/current and cathode voltage/current
        smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)         -- Anode: I/V
        node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2) -- Cathode: I/V
    
        -- Check for compliance
        if smua.source.compliance or node[2].smua.source.compliance then
            break
        end
    end

else
    for i = 1, N_st do
        Vanode = {{Vanode_start}} + (i-1)*{{Vanode_step}}
        smua.source.levelv = Vanode
        delay({{settling_delay}})  -- Add settling time parameter
    
        -- Measure anode voltage/current and cathode voltage/current
        smua.measure.iv(smua.nvbuffer1, smua.nvbuffer2)         -- Anode: I/V
        node[2].smua.measure.iv(node[2].smua.nvbuffer1, node[2].smua.nvbuffer2) -- Cathode: I/V
    
        -- Check for compliance
        if smua.source.compliance or node[2].smua.source.compliance then
            break
        end
    end
end

-- Safe shutdown
smua.source.levelv = 0
node[2].smua.source.levelv = 0
smua.source.output = 0
node[2].smua.source.output = 0