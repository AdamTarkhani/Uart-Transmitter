// Code your design here
module UART_Transmitter(
  input i_tx_start,
  input [7:0] i_tx_data,
  input clk,
  input areset,
  output reg o_tx_done,
  output reg out_data);
  
  localparam BAUD_RT = 1000000;
  localparam CLK_FRQ = 10000000;
  localparam TICKS_PER_BIT = CLK_FRQ / BAUD_RT;
  
  reg [7:0] in_data;
  reg [1:0] state, next_state;
  reg [12:0] tick_counter;
  reg [3:0] bit_counter_data;
    
  localparam IDLE = 0, START = 1, DATA = 2, DONE = 3;
  
  always @(*) begin
    case (state)
      IDLE: next_state = (i_tx_start)? START: IDLE;
      START: next_state = (tick_counter == TICKS_PER_BIT - 1)? DATA: START;
      DATA: next_state = (bit_counter_data == 7 && tick_counter == TICKS_PER_BIT - 1)? DONE: DATA;
      DONE: 
        if (tick_counter == TICKS_PER_BIT - 1 && i_tx_start) begin
          next_state = START;
        end else if (tick_counter == TICKS_PER_BIT - 1 && !i_tx_start) begin
          next_state = IDLE;
        end else begin
          next_state = DONE;
        end
    endcase
  end
  
  always @(posedge clk or posedge areset) begin
    if (areset) begin
      state <= IDLE;
    end else begin
      state <= next_state;
      if ((state == IDLE || state == DONE) && i_tx_start) begin
        in_data <= i_tx_data;
      end
    end
  end
  
  always @(posedge clk or posedge areset) begin
    if (areset) begin
      tick_counter <= 0;
      bit_counter_data <= 0;
    end else begin
      if (state == START || state == DONE || state == DATA) begin
        if (tick_counter >= TICKS_PER_BIT - 1) begin
          tick_counter <= 0;
          
          if (state == DATA) begin
            if (bit_counter_data >= 7) begin
              bit_counter_data <= 0;
            end else begin
              bit_counter_data <= bit_counter_data + 1;
            end
          end
          
      	end else begin
          tick_counter <= tick_counter + 1; 
      	end
      end else begin
        tick_counter <= 0;
        bit_counter_data <= 0;
      end 
    end
  end
  
  always @(posedge clk or posedge areset) begin
    if (areset) begin
      out_data <= 1;
    end else begin
      case (state) 
      	START: out_data <= 0;
      	DONE: out_data <= 1;
        DATA: out_data <= in_data[bit_counter_data];
        IDLE: out_data <= 1;
      endcase
    end
  end
  
  always @(posedge clk or posedge areset) begin
    if (areset) begin
      o_tx_done <= 0;
    end else begin
      o_tx_done <= ((state == DONE) && (tick_counter == TICKS_PER_BIT - 2));
    end
  end
  
  initial begin
    $dumpfile("dump.vcd");
    $dumpvars(0, UART_Transmitter);
  end
  
endmodule
