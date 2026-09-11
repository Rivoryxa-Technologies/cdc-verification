// rtl/sync_2ff.sv
// Reusable N-flop synchronizer for a signal crossing into the `clk` domain.
// Use STAGES >= 2; extra flops reduce the odds that metastability propagates.
// Only use this on single-bit signals or on Gray-coded / otherwise
// single-bit-changing buses, never on arbitrary parallel data.
`timescale 1ns/1ps
module sync_2ff #(
  parameter int WIDTH  = 1,
  parameter int STAGES = 2
)(
  input  logic             clk,
  input  logic             rst_n,
  input  logic [WIDTH-1:0] d,
  output logic [WIDTH-1:0] q
);
  logic [WIDTH-1:0] sync [0:STAGES-1];
  integer i;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (i = 0; i < STAGES; i = i + 1)
        sync[i] <= '0;
    end else begin
      sync[0] <= d;
      for (i = 1; i < STAGES; i = i + 1)
        sync[i] <= sync[i-1];
    end
  end

  assign q = sync[STAGES-1];
endmodule
