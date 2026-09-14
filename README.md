# Asynchronous FIFO functional verification

A public, deliberately seeded demonstration of bug reproduction and regression
coverage. This is not a client engagement or a production result. The design is
a small dual-clock FIFO; the checks are functional simulation, not CDC signoff.

## Problem and expected behavior

A write while `wfull` is asserted must be rejected without changing unread data.
A read while `rempty` is asserted must not advance the queue. Accepted words must
arrive once and in order. Coordinated reset of both domains flushes queued data,
and transfers must restart correctly afterward.

The original random 256-word test never writes while full. It therefore passes
on the deliberately broken variant below. A new directed test fills the FIFO,
attempts three rejected writes, drains and checks the original contents, repeats
across pointer wrap, attempts empty reads, and resets with words still queued.

## Deliberately introduced bug, root cause, and fix

`scripts/reproduce.py` creates a temporary RTL copy with this one-line mutation:

```systemverilog
// Deliberate bug: a rejected full write overwrites an unread memory location.
if (winc) mem[wbin[ASIZE-1:0]] <= wdata;

// Correct implementation, already present in rtl/async_fifo.sv:
if (winc && !wfull) mem[wbin[ASIZE-1:0]] <= wdata;
```

When full, the write pointer stops advancing. Without the memory-write guard,
new data still replaces an unread word at that pointer. The directed test fails
with `ORDER_MISMATCH`. Restoring the guard makes the same check pass. The mutant
exists only in the runner's temporary directory; production RTL is not patched
in place. This exercise demonstrates a previously untested scenario, not a newly
discovered defect in the committed FIFO.

## Reproduce

Install Python 3.12, make, and Icarus Verilog (`brew install icarus-verilog` on
macOS, or your Linux package manager). From a fresh clone:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/reproduce.py
```

The script uses a fresh build directory for every case and writes logs, JUnit
results and `summary.json` under `evidence/local/`. Override with `--out DIR`.
It requires exactly two tests: one expected directed failure on the mutant, then
zero failures on the correct design at 10/13, 17/10 and 7/19 ns write/read periods.
Missing result files, compile failures or timeouts cannot satisfy those checks.
The script exits nonzero if any expected result is absent. Each simulation has
a 100 us simulation-time bound and each make process group has a 90-second wall
limit. Ordinary `make` runs both tests on the correct design at 10/13 ns.

Use a matching Icarus compiler and runtime. In this audit the OSS CAD Suite vvp
wrapper overrode Python runtime paths and prevented cocotb from starting;
Homebrew Icarus worked. Do not reuse a compiled `sim_build` after switching
simulator versions. Such startup errors are blocked checks, not RTL failures.

## Measured evidence

`evidence/audit-2026-09-15/` contains actual logs, XML and commands. Environment:
Apple M4, 16 GiB RAM, macOS 26.6.2 arm64; Python 3.12.12, cocotb 2.1.0,
Icarus Verilog 13.0 (stable).

| Variant | Write/read periods, ns | Test result | Build + run seconds |
|---|---|---|---:|
| Deliberate overflow mutant | 10 / 13 | Original random test passes; directed test fails | 1.043 |
| Correct guarded write | 10 / 13 | 2 pass, 0 fail | 0.947 |
| Correct guarded write | 17 / 10 | 2 pass, 0 fail | 0.994 |
| Correct guarded write | 7 / 19 | 2 pass, 0 fail | 0.996 |

These are measured command runtimes, including build and simulator startup.
They are not engineering-effort estimates or promised client turnaround times.
Manual work included writing and reviewing the directed scenario, diagnosing the
Python/runtime mismatch, and inspecting the failing and passing evidence.
CI runs the same expected-failure and passing checks, with its own tool versions
recorded in uploaded artifacts.

## Limits

- Default 8-bit words and depth 16 only; no parameter sweep or exhaustive proof.
- Three clock-period pairs and one fixed random seed, not all phases or ratios.
- Coordinated reset while both sides are idle discards queued data. Independent
  one-sided reset and reset during a transfer are not verified.
- Digital simulation does not model electrical metastability or verify physical
  Gray-bus skew constraints. This does not replace structural CDC analysis.
- `sync_2ff.sv` is compiled but is not instantiated by this FIFO; these runs do
  not separately verify that reusable module.
- Coverage here is directed scenario checks and a log marker, not structural or
  exhaustive functional coverage.
