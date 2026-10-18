# UART Transmitter

An 8N1 UART transmitter written in SystemVerilog, with a cocotb verification environment.
The README has two parts: [the RTL](#part-1-the-rtl) and [the verification](#part-2-verification).

All simulation was done on EDA Playground (cocotb + Icarus Verilog); the files were transferred here from there.

---

## Part 1: The RTL

### What it is and what it is for

A UART (Universal Asynchronous Receiver/Transmitter) sends bytes one bit at a time over a single wire, with no
shared clock. It is the simplest and most common serial link between chips and boards: debug consoles, GPS
modules, Bluetooth modules, and microcontroller-to-microcontroller links all use it. This module is the transmit
half: it takes a byte on parallel inputs and shifts it out on one line, framed so a receiver can recover it.

### The protocol

Both ends agree on a baud rate ahead of time, since there is no clock wire. This design uses 8N1 framing
(8 data bits, no parity, 1 stop bit):

```
idle (high) | START (low) | D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | STOP (high) | idle (high)
```

- The line idles high.
- A low **start bit** tells the receiver a frame is beginning, and gives it a falling edge to time from.
- The **8 data bits** follow, least significant bit first.
- A high **stop bit** ends the frame and returns the line to idle.
- Every bit lasts the same number of clock cycles, set by the baud rate.

### Interface

| Port | Direction | Meaning |
|---|---|---|
| `clk` | in | System clock |
| `areset` | in | Asynchronous reset, active high |
| `i_tx_start` | in | Pulse high for one clock to send the byte on `i_tx_data` |
| `i_tx_data[7:0]` | in | The byte to send |
| `out_data` | out | Serial output line (idles high) |
| `o_tx_done` | out | One-cycle pulse when the frame is finishing |

### How it works

Timing comes from two local parameters, `CLK_FRQ` (10 MHz) and `BAUD_RT` (1 Mbaud), which give
`TICKS_PER_BIT = 10` clock cycles per bit. A four-state machine drives the line:

| State | What happens |
|---|---|
| `IDLE` | Line high. Waits for `i_tx_start`. |
| `START` | Drives the start bit low for one bit time. |
| `DATA` | Drives the 8 data bits, one bit time each, least significant first. |
| `DONE` | Drives the stop bit high. At the end of it, a new `i_tx_start` goes straight to `START`, otherwise back to `IDLE`. |

A tick counter counts clocks within a bit, and a bit counter counts which data bit is being sent.

### Protections and design decisions

- **Asynchronous reset** puts the state machine in `IDLE` and the line high.
- **Data is latched** when the start request is accepted, so `i_tx_data` can change afterward without
  corrupting the frame in progress.
- **Start requests while busy are ignored.** A start pulse during `START` or `DATA` does not disturb the frame.
- **Back-to-back frames.** A start request at the end of the stop bit begins the next frame immediately,
  without returning to idle first.
- **Line idles high** after reset and between frames.
- **`o_tx_done`** is a registered one-cycle pulse near the end of the stop bit.

### Future plans

- Make the baud rate and clock frequency module parameters instead of local ones, so they can be set where the
  module is instantiated.
- Add a UART receiver to pair with it.
- Optional parity and a configurable number of stop bits.

---

## Part 2: Verification

### Setup

A cocotb testbench (Python) with a driver, monitor and scoreboard. Simulator: Icarus Verilog 12 with
cocotb 2.1 (`-g2012`).

| Piece | What it does |
|---|---|
| `UartTxDriver` | Loads a byte on `i_tx_data` and pulses `i_tx_start` for one clock. Can wait for `o_tx_done` or return straight away. |
| `UartTxMonitor` | Watches `out_data` only. Finds the falling edge of the start bit, samples every bit in the middle of its bit time, checks the start bit is 0 and the stop bit is 1, and rebuilds the byte. |
| `UartTxScoreboard` | Compares the list of bytes that were sent against the list the monitor rebuilt, and reports the index and both values in hex on a mismatch. |

All of it is in `testbench.py`, which is the file `make` runs. The RTL is in `rtl/uart_transmitter.sv`.

### Running it

    make        # runs testbench.py (5 tests) against rtl/uart_transmitter.sv

You need Python 3.9+, cocotb 2.1, Icarus Verilog and make.

### What is covered (all 5 tests pass)

- **Single byte:** a random byte is sent, rebuilt from the line, and compared.
- **Random bytes:** two random bytes sent one after another.
- **Back to back:** a second byte sent after the first frame has finished.
- **Start while busy ignored:** a second start pulse partway through a frame must not change or add a frame.
- **Edge values:** `0x00` and `0xFF`.

### Still to be checked

- **Reset in the middle of a frame:** the line should return high and the state machine to idle.
- **`o_tx_done` checks:** the tests wait for the pulse but do not yet check its width or its position in the frame.
- **True back-to-back frames:** a start request held at the end of the stop bit, so the next frame follows with no idle gap.
- **Data stability:** changing `i_tx_data` during a frame must not affect the frame.
- **Longer random runs:** many bytes with random gaps.
- **Other baud rates and clock frequencies:** the testbench constants must be kept in sync by hand with the RTL's local parameters.
