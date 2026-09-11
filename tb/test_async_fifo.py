# tb/test_async_fifo.py
# cocotb testbench for the dual-clock async FIFO. The write and read sides run
# on two independent clocks; the test checks that every word crosses the CDC
# boundary exactly once and in order.
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

N = 256                  # words to push through
DSIZE = 8
MASK = (1 << DSIZE) - 1


async def reset(dut):
    dut.winc.value = 0
    dut.rinc.value = 0
    dut.wdata.value = 0
    dut.wrst_n.value = 0
    dut.rrst_n.value = 0
    for _ in range(5):
        await RisingEdge(dut.wclk)
    dut.wrst_n.value = 1
    dut.rrst_n.value = 1
    await RisingEdge(dut.wclk)


@cocotb.test()
async def test_async_fifo(dut):
    """Push N words through the async FIFO across two independent clocks and
    check they come out exactly once, in order, with no loss or duplication."""
    # two unrelated clocks
    cocotb.start_soon(Clock(dut.wclk, 10, units="ns").start())
    cocotb.start_soon(Clock(dut.rclk, 13, units="ns").start())

    await reset(dut)

    sent = []
    received = []

    async def writer():
        i = 0
        while i < N:
            await FallingEdge(dut.wclk)
            if dut.wfull.value == 0 and random.random() < 0.7:
                dut.wdata.value = i & MASK
                dut.winc.value = 1
                sent.append(i & MASK)
                i += 1
            else:
                dut.winc.value = 0
        await FallingEdge(dut.wclk)
        dut.winc.value = 0

    async def reader():
        while len(received) < N:
            await FallingEdge(dut.rclk)
            if dut.rempty.value == 0 and random.random() < 0.7:
                received.append(int(dut.rdata.value) & MASK)
                dut.rinc.value = 1
            else:
                dut.rinc.value = 0
        await FallingEdge(dut.rclk)
        dut.rinc.value = 0

    w = cocotb.start_soon(writer())
    r = cocotb.start_soon(reader())
    await w
    await r

    expected = [i & MASK for i in range(N)]
    assert sent == expected, "writer did not present the expected sequence"
    assert received == sent, (
        "data mismatch across the CDC FIFO\n"
        f"  sent[:8]={sent[:8]}\n  recv[:8]={received[:8]}\n"
        f"  lengths: sent={len(sent)} recv={len(received)}"
    )
    dut._log.info("PASS: %d words crossed the CDC FIFO intact", N)
