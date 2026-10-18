import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, ClockCycles

# ---------------------------------------------------------------------------
# Config -- keep this in sync BY HAND with your module's localparams
# ---------------------------------------------------------------------------
CLK_FREQ_HZ = 10000000
BAUD_RATE   = 1000000


CLKS_PER_BIT = CLK_FREQ_HZ//BAUD_RATE


# ---------------------------------------------------------------------------
# Clock / reset helpers (mechanics -- provided)
# ---------------------------------------------------------------------------
async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 1_000_000_000 // CLK_FREQ_HZ, units="ns").start())


async def reset_dut(dut):
    dut.areset.value = 1
    dut.i_tx_start.value = 0
    dut.i_tx_data.value = 0
    await ClockCycles(dut.clk, 5)
    dut.areset.value = 0
    await RisingEdge(dut.clk)


# ---------------------------------------------------------------------------
# Driver -- drives i_tx_start / i_tx_data
# ---------------------------------------------------------------------------
class UartTxDriver:
    def __init__(self, dut):
        self.dut = dut

    async def send_byte(self, data: int, wait_for_done: bool = True):
        """Load a byte and pulse i_tx_start for exactly one clock cycle.
        If wait_for_done, block until o_tx_done pulses before returning
        (pass False deliberately for back-to-back / start-while-busy tests)."""
        dut = self.dut

        await RisingEdge(dut.clk)
        dut.i_tx_data.value = data
        dut.i_tx_start.value = 1
        await RisingEdge(dut.clk)
        dut.i_tx_start.value = 0

        if wait_for_done:
            await RisingEdge(dut.o_tx_done)

# ---------------------------------------------------------------------------
# Monitor -- passively watches out_data and reconstructs bytes
# ---------------------------------------------------------------------------
class UartTxMonitor:
    def __init__(self, dut):
        self.dut = dut
        self.received_bytes = []

    async def _wait_for_start_bit(self):
        """Line idles high; start bit is the falling edge on out_data."""
        await FallingEdge(self.dut.out_data)

    async def monitor_one_frame(self):
        """Wait for one full UART frame on out_data, return the decoded byte."""
        await self._wait_for_start_bit()
        byte  = 0
        dut = self.dut

        await ClockCycles(dut.clk, CLKS_PER_BIT // 2)

        assert dut.out_data.value == 0, f"Failed, start bit not 0"

        for i in  range(8):
            await ClockCycles(dut.clk, CLKS_PER_BIT)
            if dut.out_data.value == 1:
                byte += 2 ** i

        await ClockCycles(dut.clk, CLKS_PER_BIT)
        assert dut.out_data.value == 1, f"Failed, stop bit not 1"

        decoded_byte = byte
        return decoded_byte

    async def start_listening(self, n_frames: int):
        for _ in range(n_frames):
            byte = await self.monitor_one_frame()
            self.received_bytes.append(byte)


# ---------------------------------------------------------------------------
# Scoreboard -- compares expected vs. observed
# ---------------------------------------------------------------------------
class UartTxScoreboard:
    def __init__(self):
        self.expected = []
        self.actual = []
        self.errors = 0

    def add_expected(self, byte: int):
        self.expected.append(byte)

    def add_actual(self, byte: int):
        self.actual.append(byte)

    def check(self):
        """TODO: compare expected vs actual, produce a clear pass/fail with
        a useful message (index, expected vs got, in hex)."""
        if len(self.expected) == len(self.actual):
            for i in range(len(self.expected)):
                assert self.expected[i] == self.actual[i], f"Failed at index {i}, expected {self.expected[i]:x} vs actual {self.actual[i]:x}"
        else:
            assert False, f"Failed, expected number of byte vs actual number of byte different len, {len(self.expected)} vs {len(self.actual)}"



# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_single_byte(dut):
    await start_clock(dut)
    await reset_dut(dut)

    driver = UartTxDriver(dut)
    monitor = UartTxMonitor(dut)
    scoreboard = UartTxScoreboard()

    cocotb.start_soon(monitor.start_listening(1))

    data = random.randint(0, 255)
    await driver.send_byte(data, True)
    scoreboard.add_expected(data)
    scoreboard.add_actual(monitor.received_bytes[0])
    scoreboard.check()

@cocotb.test()
async def test_random_bytes(dut):
    await start_clock(dut)
    await reset_dut(dut)

    driver = UartTxDriver(dut)
    monitor = UartTxMonitor(dut)
    scoreboard = UartTxScoreboard()

    cocotb.start_soon(monitor.start_listening(2))

    for i in range(2):
        data = random.randint(0, 255)
        await driver.send_byte(data, True)
        scoreboard.add_expected(data)
        scoreboard.add_actual(monitor.received_bytes[i])

    scoreboard.check()


@cocotb.test()
async def test_back_to_back(dut):
    
    await start_clock(dut)
    await reset_dut(dut)

    driver = UartTxDriver(dut)
    monitor = UartTxMonitor(dut)
    scoreboard = UartTxScoreboard()

    cocotb.start_soon(monitor.start_listening(2))

    data1 = random.randint(0, 255)
    data2 = random.randint(0, 255)
    await driver.send_byte(data1, False)
    await ClockCycles(dut.clk, CLKS_PER_BIT*10 - 1)
    await driver.send_byte(data2,True)


    scoreboard.add_expected(data1)
    scoreboard.add_expected(data2)
    scoreboard.add_actual(monitor.received_bytes[0])
    scoreboard.add_actual(monitor.received_bytes[1])

    scoreboard.check()

@cocotb.test()
async def test_start_while_busy_ignored(dut):
    await start_clock(dut)
    await reset_dut(dut)

    driver = UartTxDriver(dut)
    monitor = UartTxMonitor(dut)
    scoreboard = UartTxScoreboard()

    cocotb.start_soon(monitor.start_listening(1))

    data1 = 233
    data2 = 100
    await driver.send_byte(data1, False)
    await ClockCycles(dut.clk, CLKS_PER_BIT*3)
    await driver.send_byte(data2, False)
    await RisingEdge(dut.o_tx_done)
    scoreboard.add_expected(data1)
    scoreboard.add_actual(monitor.received_bytes[0])
    scoreboard.check()


@cocotb.test()
async def test_edge_values(dut):
    await start_clock(dut)
    await reset_dut(dut)

    driver = UartTxDriver(dut)
    monitor = UartTxMonitor(dut)
    scoreboard = UartTxScoreboard()

    cocotb.start_soon(monitor.start_listening(2))

    data = 0
    await driver.send_byte(data, True)
    scoreboard.add_expected(data)
    scoreboard.add_actual(monitor.received_bytes[0])

    data = 255
    await driver.send_byte(data, True)
    scoreboard.add_expected(data)
    scoreboard.add_actual(monitor.received_bytes[1])

    scoreboard.check()
    
if __name__ == "__main__":
    import os
    
    makefile_content = """
SIM = icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = design.sv
TOPLEVEL = UART_Transmitter
MODULE = testbench
include $(shell cocotb-config --makefiles)/Makefile.sim
"""
    with open("Makefile", "w") as f:
        f.write(makefile_content.strip())
        
    os.system("make")