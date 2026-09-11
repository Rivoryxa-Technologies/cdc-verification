# cdc-verification

A clock-domain-crossing (CDC) verification example: a dual-clock asynchronous
FIFO with Gray-code pointers and two-flop synchronizers, checked across two
truly independent clocks with a self-checking cocotb testbench.

Runs on free, open-source simulators (Icarus Verilog or Verilator) via cocotb.

## Why CDC is its own problem

When data crosses between two unrelated clocks, a naive register can go
metastable, and different bits of a bus can settle in different cycles. The
result is bugs that single-clock simulation never sees and that show up only
occasionally in silicon. CDC verification is about proving the crossing
structures (synchronizers, Gray-coded pointers, handshakes) actually preserve
data and never lose or duplicate it.

## What is here

```
rtl/async_fifo.sv      dual-clock async FIFO: Gray pointers + 2-flop synchronizers
rtl/sync_2ff.sv        reusable N-flop synchronizer primitive
tb/test_async_fifo.py  cocotb testbench: two independent clocks, integrity check
Makefile               cocotb run flow
```

The FIFO uses the classic safe-CDC recipe:

- **Gray-code pointers** so only one bit changes per step, which means the
  pointer value crossing the clock boundary always samples to a legal value.
- **Two-flop synchronizers** on each pointer as it enters the opposite domain.
- **Full and empty** derived from the synchronized pointers, so neither side
  overruns the other.

## What the test proves

The testbench runs the write and read sides on **two independent clocks** at
different frequencies, with randomized backpressure on both, then checks that
every word comes out exactly once and in order, with no loss and no duplication.

Functional simulation does not model metastability itself (that is a physical
and formal concern); what it proves here is that the pointer, Gray-code, and
full/empty logic keep the data intact when the two clocks run asynchronously.

## Run it

```bash
pip install cocotb
sudo apt-get install iverilog   # or: brew install icarus-verilog
make
```

## Notes

An async FIFO is the workhorse CDC structure, but the same discipline
(synchronize, Gray-code, handshake, then verify integrity across real
asynchronous clocks) applies to control crossings and multi-bit buses. Want a
CDC sign-off, or lint plus formal review on a specific block? Reach out.

---
Maintained by [Rivoryxa Technologies](https://www.linkedin.com/company/rivoryxa-technologies/).
