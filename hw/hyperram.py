# This file is Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Gregory Davill <greg.davill@gmail.com>
# License: BSD

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.clock import *
from migen.genlib.cdc import MultiReg


def delayf_pins():
    return Record([("loadn", 1),("move", 1),("direction", 1)])

# HyperRAM -----------------------------------------------------------------------------------------

class HyperRAM(Module):
    """HyperRAM

    Provides a standard HyperRAM core that works at 1:1 system clock speeds
    - PHY is device dependent for DDR IO primitives
      - ECP5 (done)
    - 90 deg phase shifted clock required from PLL
    - Burst R/W supported if bus is ready
    - Latency indepedent reads (RWDS strobing)

    This core favors performance over portability

    """
    def __init__(self, pads):
        self.pads = pads
        self.bus  = bus = wishbone.Interface(adr_width=22)


        self.dly_io = delayf_pins()
        self.dly_clk = delayf_pins()

        # # #
        clk         = Signal()
        cs         = Signal()
        ca         = Signal(48)
        sr_in      = Signal(64)
        sr_out         = Signal(64)
        sr_rwds_in    = Signal(8)
        sr_rwds_out    = Signal(8)

        timeout_counter = Signal(6)

        self.submodules.phy = phy = HyperBusPHY(pads)

        self.comb += [
            phy.dly_io.eq(self.dly_io),
            phy.dly_clk.eq(self.dly_clk),
        ]
    
        # Drive rst_n, from internal signals ---------------------------------------------
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1)
            
        self.comb += [
            phy.cs.eq(~cs),
            phy.clk_enable.eq(clk)
        ]
        
        # Data Out Shift Register (for write) -------------------------------------------------
        self.sync += [
            sr_out.eq(Cat(Signal(32), sr_out[:32])),
            sr_in.eq(Cat(phy.dq.i, sr_in[:32])),
            sr_rwds_in.eq(Cat(phy.rwds.i, sr_rwds_in[:4])),
            sr_rwds_out.eq(Cat(phy.rwds.i, sr_rwds_out[:4])),
        ]

        self.comb += [
            bus.dat_r.eq(Cat(phy.dq.i[-16:], sr_in[:16])), # To Wishbone
            phy.dq.o.eq(sr_out[-32:]),  # To HyperRAM
            phy.rwds.o.eq(sr_rwds_out[-4:]) # To HyperRAM
        ]

        # Command generation -----------------------------------------------------------------------
        self.comb += [
            ca[47].eq(~self.bus.we),          # R/W#
            ca[45].eq(1),                     # Burst Type (Linear)
            ca[16:35].eq(self.bus.adr[2:21]), # Row & Upper Column Address
            ca[1:3].eq(self.bus.adr[0:2]),    # Lower Column Address
            ca[0].eq(0),                      # Lower Column Address
        ]

        #self.counter = counter = Signal(8)
        #counter_rst = Signal()

        # Sequencer --------------------------------------------------------------------------------
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        

        fsm.act("IDLE", If(bus.cyc & bus.stb, NextValue(cs, 1), NextState("CA-SEND")))
        fsm.act("CA-SEND", NextValue(clk, 1), NextValue(phy.dq.oe, 1), NextValue(sr_out,Cat(Signal(16),ca)), NextState("CA-WAIT"))
        fsm.act("CA-WAIT", NextValue(timeout_counter, 0),NextState("LATENCY-WAIT"))
        fsm.act("LATENCY-WAIT", NextValue(phy.dq.oe, 0), NextState("LATENCY-WAIT0"))
        fsm.act("LATENCY-WAIT0", NextState("LATENCY-WAIT1"))
        fsm.act("LATENCY-WAIT1", NextState("LATENCY-WAIT2"))
        fsm.act("LATENCY-WAIT2", NextState("LATENCY-WAIT3"))
        fsm.act("LATENCY-WAIT3", NextValue(phy.dq.oe, self.bus.we), NextValue(phy.rwds.oe,self.bus.we), NextState("READ-WRITE"))
        fsm.act("READ-WRITE", NextState("READ-ACK"),
                If(self.bus.we,
                    NextValue(phy.dq.oe,1),                 # Write Cycle
                    NextValue(sr_out[:32],0),
                    NextValue(sr_out[32:],self.bus.dat_w),
                    NextValue(sr_rwds_out[:4],0),
                    NextValue(sr_rwds_out[4:],~bus.sel[0:4]),
                    bus.ack.eq(1), # Get next byte
                    NextState("CLK-OFF"),
                    If(bus.cti == 0b010,
                        NextState("READ-WRITE"),
                )))
        
        
        fsm.act("READ-ACK", 
            NextValue(timeout_counter, timeout_counter + 1),
            If(phy.rwds.i[3], 
                NextValue(timeout_counter, 0),
                bus.ack.eq(1),
                If(bus.cti != 0b010,
                    NextValue(clk, 0), NextState("CLEANUP"))),
            If(~self.bus.cyc | (timeout_counter > 20),
                NextState("CLK-OFF")
            ))
        
        fsm.act("CLK-OFF", NextValue(clk, 0), NextState("CLEANUP"))
        fsm.act("CLEANUP", NextValue(cs, 0), NextValue(phy.rwds.oe, 0), NextValue(phy.dq.oe, 0), NextState("HOLD-WAIT"))
        fsm.act("HOLD-WAIT", NextValue(sr_out, 0), NextValue(sr_rwds_out, 0), NextState("HOLD-WAIT0"))
        fsm.act("HOLD-WAIT0", NextState("HOLD-WAIT1"))
        fsm.act("HOLD-WAIT1", NextState("HOLD-WAIT2"))
        fsm.act("HOLD-WAIT2", NextState("HOLD-WAIT3"))
        fsm.act("HOLD-WAIT3", NextState("HOLD-WAIT4"))
        fsm.act("HOLD-WAIT4", NextState("HOLD-WAIT5"))
        fsm.act("HOLD-WAIT5", NextState("HOLD-WAIT6"))
        fsm.act("HOLD-WAIT6", NextState("HOLD-WAIT7"))
        fsm.act("HOLD-WAIT7", NextState("HOLD-WAIT8"))
        fsm.act("HOLD-WAIT8", NextState("HOLD-WAIT9"))
        fsm.act("HOLD-WAIT9", NextState("HOLD-WAITA"))
        fsm.act("HOLD-WAITA", NextState("HOLD-WAITB"))
        fsm.act("HOLD-WAITB", NextState("HOLD-WAITC"))
        fsm.act("HOLD-WAITC", NextState("HOLD-WAITD"))
        fsm.act("HOLD-WAITD", NextState("HOLD-WAITE"))
        fsm.act("HOLD-WAITE", NextState("IDLE"))

        self.dbg = [
            bus,
            sr_out,
            sr_in,
            sr_rwds_in,
            sr_rwds_out,
            cs,
            clk,
            phy.dq.i,
            phy.dq.o,
            phy.dq.oe,
            phy.rwds.i,
            phy.rwds.o,
            phy.rwds.oe,
        ]


class HyperBusPHY(Module):

    def add_tristate(self, pad):
        t = TSTriple(len(pad))
        self.specials += t.get_tristate(pad)
        return t



    def __init__(self, pads):
        def io_bus(n):
            return Record([("oe", 1),("i", n),("o", n)])
        
        # # #
        self.clk_enable = Signal()
        self.cs = Signal()
        self.dq = io_bus(32)
        self.rwds = io_bus(4)


        ## IO Delay shifting 
        self.dly_io = delayf_pins()
        self.dly_clk = delayf_pins()

        dq        = self.add_tristate(pads.dq) if not hasattr(pads.dq, "oe") else pads.dq
        rwds      = self.add_tristate(pads.rwds) if not hasattr(pads.rwds, "oe") else pads.rwds


        # Shift non DDR signals to match the FF's inside DDR modules.
        self.specials += MultiReg(self.cs, pads.cs_n, n=3)

        self.specials += MultiReg(self.rwds.oe, rwds.oe, n=3)
        self.specials += MultiReg(self.dq.oe, dq.oe, n=3)
        
        # mask off clock when no CS
        clk_en = Signal()
        self.comb += clk_en.eq(self.clk_enable & ~self.cs)

        #clk_out
        #for clk in [pads.clk_p, pads.clk_n]:
        clkp = Signal()
        clkn = Signal()
        self.specials += [
            Instance("ODDRX2F",
                i_D1=clk_en,
                i_D0=0,
                i_D3=clk_en,
                i_D2=0,
                i_SCLK=ClockSignal("hr_90"),
                i_ECLK=ClockSignal("hr2x_90"),
                i_RST=ResetSignal("hr"),
                o_Q=clkp),
            Instance("DELAYF",
                    p_DEL_MODE="USER_DEFINED",
                    p_DEL_VALUE=0, # 2ns (25ps per tap)
                    i_A=clkp,
                    i_LOADN=self.dly_clk.loadn,
                    i_MOVE=self.dly_clk.move,
                    i_DIRECTION=self.dly_clk.direction,
                    o_Z=pads.clk_p)
        ]
        
        self.specials += [
            Instance("ODDRX2F",
                i_D1=~clk_en,
                i_D0=1,
                i_D3=~clk_en,
                i_D2=1,
                i_SCLK=ClockSignal("hr_90"),
                i_ECLK=ClockSignal("hr2x_90"),
                i_RST=ResetSignal("hr"),
                o_Q=clkn),
            Instance("DELAYF",
                    p_DEL_MODE="USER_DEFINED",
                    p_DEL_VALUE=0, # 2ns (25ps per tap)
                    i_A=clkn,
                    i_LOADN=self.dly_clk.loadn,
                    i_MOVE=self.dly_clk.move,
                    i_DIRECTION=self.dly_clk.direction,
                    o_Z=pads.clk_n)
        ]

        # DQ_out
        for i in range(8):
            self.specials += [
                Instance("ODDRX2F",
                    i_D3=self.dq.o[i],
                    i_D2=self.dq.o[8+i],
                    i_D1=self.dq.o[16+i],
                    i_D0=self.dq.o[24+i],
                    i_SCLK=ClockSignal("hr"),
                    i_ECLK=ClockSignal("hr2x"),
                    i_RST=ResetSignal("hr"),
                    o_Q=dq.o[i]
                )
            ]
    

        # DQ_in
        for i in range(8):
            dq_in = Signal()
            self.specials += [
                Instance("IDDRX2F",
                    i_D=dq_in,
                    i_SCLK=ClockSignal("hr"),
                    i_ECLK=ClockSignal("hr2x"),
                    i_RST= ResetSignal("hr"),
                    o_Q3=self.dq.i[i],
                    o_Q2=self.dq.i[i+8],
                    o_Q1=self.dq.i[i+16],
                    o_Q0=self.dq.i[i+24]
                ),
                Instance("DELAYF",
                    p_DEL_MODE="USER_DEFINED",
                    p_DEL_VALUE=0, # 2ns (25ps per tap)
                    i_A=dq.i[i],
                    i_LOADN=self.dly_io.loadn,
                    i_MOVE=self.dly_io.move,
                    i_DIRECTION=self.dly_io.direction,
                    o_Z=dq_in)
            ]
        
        # RWDS_out
        self.specials += [
            Instance("ODDRX2F",
                i_D3=self.rwds.o[0],
                i_D2=self.rwds.o[1],
                i_D1=self.rwds.o[2],
                i_D0=self.rwds.o[3],
                i_SCLK=ClockSignal("hr"),
                i_ECLK=ClockSignal("hr2x"),
                i_RST=ResetSignal("hr"),
                o_Q=rwds.o
            )
        ]

        # RWDS_in
        rwds_in = Signal()
        self.specials += [
            Instance("IDDRX2F",
                i_D=rwds_in,
                i_SCLK=ClockSignal("hr"),
                i_ECLK=ClockSignal("hr2x"),
                i_RST= ResetSignal("hr"),
                o_Q3=self.rwds.i[0],
                o_Q2=self.rwds.i[1],
                o_Q1=self.rwds.i[2],
                o_Q0=self.rwds.i[3]
            ),
            Instance("DELAYF",
                    p_DEL_MODE="USER_DEFINED",
                    p_DEL_VALUE=0, # 2ns (25ps per tap)
                    i_A=rwds.i,
                    i_LOADN=self.dly_io.loadn,
                    i_MOVE=self.dly_io.move,
                    i_DIRECTION=self.dly_io.direction,
                    o_Z=rwds_in)
        ]
