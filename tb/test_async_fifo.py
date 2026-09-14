# tb/test_async_fifo.py
# cocotb testbench for the dual-clock async FIFO. The write and read sides run
# on two independent clocks; the test checks that every word crosses the CDC
# boundary exactly once and in order.
import random
import os

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


@cocotb.test(timeout_time=100, timeout_unit="us")
async def test_async_fifo(dut):
    """Push N words through the async FIFO across two independent clocks and
    check they come out exactly once, in order, with no loss or duplication."""
    # two unrelated clocks
    cocotb.start_soon(Clock(dut.wclk, int(os.environ.get("WRITE_NS", "10")), unit="ns").start())
    cocotb.start_soon(Clock(dut.rclk, int(os.environ.get("READ_NS", "13")), unit="ns").start())

    await reset(dut)

    random.seed(20260915)
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


@cocotb.test(timeout_time=100, timeout_unit="us")
async def test_full_empty_reset_ordering(dut):
    """Rejected full writes must not corrupt queued words; reset flushes both sides."""
    import os
    from cocotb.triggers import Timer
    wp = int(os.environ.get("WRITE_NS", "10"))
    rp = int(os.environ.get("READ_NS", "13"))
    cocotb.start_soon(Clock(dut.wclk, wp, unit="ns").start())
    cocotb.start_soon(Clock(dut.rclk, rp, unit="ns").start())
    await reset(dut)
    depth = 16  # this regression exercises the default ASIZE=4 configuration

    async def push(value, accepted=True):
        await FallingEdge(dut.wclk)
        assert bool(int(dut.wfull.value)) != accepted, "unexpected full flag"
        dut.wdata.value = value
        dut.winc.value = 1
        await RisingEdge(dut.wclk)
        await FallingEdge(dut.wclk)
        dut.winc.value = 0

    async def pop(expected):
        for _ in range(12):
            await FallingEdge(dut.rclk)
            if not int(dut.rempty.value):
                break
        else:
            assert False, "FIFO did not become readable within 12 read cycles"
        actual = int(dut.rdata.value)
        assert actual == expected, f"ORDER_MISMATCH: expected {expected}, got {actual}"
        dut.rinc.value = 1
        await RisingEdge(dut.rclk)
        await FallingEdge(dut.rclk)
        dut.rinc.value = 0

    # Fill, try rejected writes while full, then read the original contents.
    for value in range(depth):
        await push(value)
    for value in (201, 202, 203):
        await push(value, accepted=False)
    for value in range(depth):
        await pop(value)
    assert int(dut.rempty.value) == 1, "FIFO must be empty after draining"
    # Reads while empty must not advance the pointer.
    dut.rinc.value = 1
    for _ in range(4):
        await FallingEdge(dut.rclk)
    dut.rinc.value = 0
    for _ in range(6):
        await FallingEdge(dut.wclk)
    # Repeat across pointer wrap, with values different from the first batch.
    for value in range(32, 48):
        await push(value)
    for value in range(32, 48):
        await pop(value)
    for _ in range(6):
        await FallingEdge(dut.wclk)
    for value in (80, 81, 82):
        await push(value)
    # Coordinated reset deliberately discards queued data. Independent reset is not supported.
    dut.wrst_n.value = 0
    dut.rrst_n.value = 0
    await Timer(max(wp, rp) * 6, unit="ns")
    await FallingEdge(dut.wclk)
    dut.wrst_n.value = 1
    await FallingEdge(dut.rclk)
    dut.rrst_n.value = 1
    await Timer(max(wp, rp) * 6, unit="ns")
    assert int(dut.rempty.value) == 1
    assert int(dut.wfull.value) == 0
    for value in (101, 102, 103):
        await push(value)
    for value in (101, 102, 103):
        await pop(value)
    assert int(dut.rempty.value) == 1
    dut._log.info("COVER: full rejection, empty rejection, pointer wrap, queued reset, ordering; clocks=%d/%d ns", wp, rp)
