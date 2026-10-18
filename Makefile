# Icarus Verilog. -g2012 because the RTL is SystemVerilog.
# Run the testbench:   make

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES = $(PWD)/rtl/uart_transmitter.sv
COMPILE_ARGS += -g2012
TOPLEVEL = UART_Transmitter
COCOTB_TEST_MODULES = testbench

include $(shell cocotb-config --makefiles)/Makefile.sim
