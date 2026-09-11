// rtl/async_fifo.sv
// Dual-clock asynchronous FIFO with Gray-code pointers and two-flop
// synchronizers on each pointer crossing. Classic safe-CDC structure
// (Clifford Cummings, SNUG 2002 style).
`timescale 1ns/1ps
module async_fifo #(
  parameter int DSIZE = 8,
  parameter int ASIZE = 4            // depth = 2**ASIZE
)(
  // write clock domain
  input  logic             wclk,
  input  logic             wrst_n,
  input  logic             winc,
  input  logic [DSIZE-1:0] wdata,
  output logic             wfull,
  // read clock domain
  input  logic             rclk,
  input  logic             rrst_n,
  input  logic             rinc,
  output logic [DSIZE-1:0] rdata,
  output logic             rempty
);
  localparam int DEPTH = 1 << ASIZE;

  // dual-port memory (no reset)
  logic [DSIZE-1:0] mem [0:DEPTH-1];

  // write-domain pointers and the read pointer synchronized into it
  logic [ASIZE:0] wbin, wgray, wbinnext, wgraynext;
  logic [ASIZE:0] rptr_wq1, rptr_wq2;

  // read-domain pointers and the write pointer synchronized into it
  logic [ASIZE:0] rbin, rgray, rbinnext, rgraynext;
  logic [ASIZE:0] wptr_rq1, wptr_rq2;

  // ------------------------------------------------ write pointer and full
  assign wbinnext  = wbin + (winc & ~wfull);
  assign wgraynext = (wbinnext >> 1) ^ wbinnext;

  always_ff @(posedge wclk or negedge wrst_n) begin
    if (!wrst_n) begin
      wbin  <= '0;
      wgray <= '0;
    end else begin
      wbin  <= wbinnext;
      wgray <= wgraynext;
    end
  end

  // full: next write-gray equals read-gray with the top two bits inverted
  wire wfull_val =
    (wgraynext == {~rptr_wq2[ASIZE:ASIZE-1], rptr_wq2[ASIZE-2:0]});

  always_ff @(posedge wclk or negedge wrst_n) begin
    if (!wrst_n) wfull <= 1'b0;
    else         wfull <= wfull_val;
  end

  always_ff @(posedge wclk) begin
    if (winc && !wfull) mem[wbin[ASIZE-1:0]] <= wdata;
  end

  // ------------------------------------------------ read pointer and empty
  assign rbinnext  = rbin + (rinc & ~rempty);
  assign rgraynext = (rbinnext >> 1) ^ rbinnext;

  always_ff @(posedge rclk or negedge rrst_n) begin
    if (!rrst_n) begin
      rbin  <= '0;
      rgray <= '0;
    end else begin
      rbin  <= rbinnext;
      rgray <= rgraynext;
    end
  end

  wire rempty_val = (rgraynext == wptr_rq2);

  always_ff @(posedge rclk or negedge rrst_n) begin
    if (!rrst_n) rempty <= 1'b1;
    else         rempty <= rempty_val;
  end

  assign rdata = mem[rbin[ASIZE-1:0]];

  // ------------------------------------------------ two-flop synchronizers
  // write-gray pointer into the read clock domain
  always_ff @(posedge rclk or negedge rrst_n) begin
    if (!rrst_n) {wptr_rq2, wptr_rq1} <= '0;
    else         {wptr_rq2, wptr_rq1} <= {wptr_rq1, wgray};
  end

  // read-gray pointer into the write clock domain
  always_ff @(posedge wclk or negedge wrst_n) begin
    if (!wrst_n) {rptr_wq2, rptr_wq1} <= '0;
    else         {rptr_wq2, rptr_wq1} <= {rptr_wq1, rgray};
  end
endmodule
