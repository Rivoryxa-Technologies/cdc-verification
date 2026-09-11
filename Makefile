# cocotb + Icarus Verilog flow for the async FIFO CDC testbench.
# Usage: make            (run with Icarus)
#        make SIM=verilator
TOPLEVEL_LANG = verilog
SIM ?= icarus

VERILOG_SOURCES = $(PWD)/rtl/async_fifo.sv $(PWD)/rtl/sync_2ff.sv
TOPLEVEL = async_fifo
MODULE = test_async_fifo

export PYTHONPATH := $(PWD)/tb:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
