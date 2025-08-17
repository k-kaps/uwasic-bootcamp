/* The inputs to the SPI Peripheral are:
* ui_in:
* 	- ui_in[2] : nCS (Chip Select)
* 	- ui_in[1] : COPI
* 	- ui_in[0] : sCLK
*  And the outputs are:
*	- en_reg_out_7_0  : register 0x00
*	- en_reg_out_15_8 : register 0x01
*	- en_reg_pwm_7_0  : register 0x02
*	- en_reg_pwm_15_8 : register 0x03
*	- pwm_duty_cycle  : register 0x04 
*/

module spi_peripheral (
	input wire [2:0] ui_in,
	input 	   clk,
	input	   rst_n,
	output reg [7:0] en_reg_out_7_0,
	output reg [7:0] en_reg_out_15_8,
	output reg [7:0] en_reg_pwm_7_0,
	output reg [7:0] en_reg_pwm_15_8,
	output reg [7:0] pwm_duty_cycle
);

// First thing to do is to find a falling edge on the nCS signal (ui_in[2])
reg [2:0] nCS_sync;
reg [2:0] COPI_sync;
reg [2:0] SCLK_sync;
always @(posedge clk or negedge rst_n) begin
	if (!rst_n) begin
		// reset all the registers
		nCS_sync <= 3'b111;
		COPI_sync <= 3'b0;
		SCLK_sync <= 3'b0;
	end
	else begin
		// sample the nCS signal
		nCS_sync[0] <= ui_in[2];
		nCS_sync[1] <= nCS_sync[0];
		nCS_sync[2] <= nCS_sync[1];
		
		// sample the COPI signal
		COPI_sync[0] <= ui_in[1];
		COPI_sync[1] <= COPI_sync[0];
		COPI_sync[2] <= COPI_sync[1];
		
		// sample the SCLK signal
		SCLK_sync[0] <= ui_in[0];
		SCLK_sync[1] <= SCLK_sync[0];
		SCLK_sync[2] <= SCLK_sync[1];
	end
end

wire nCS_fe = nCS_sync[2] & ~nCS_sync[1];
wire nCS_re = ~nCS_sync[2] & nCS_sync[1];
wire SCLK_re = ~SCLK_sync[2] & SCLK_sync[1];

reg data_received;
reg transaction;
reg [4:0] num_bits;
reg [15:0] transaction_reg;
reg [6:0] addr;
reg [7:0] data;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        num_bits <= 5'b0;
        data_received <= 0;
        transaction <= 0;
		addr <= 7'b0;
        data <= 8'b0;
    end
	else begin
		if (transaction) begin
			if (~data_received && SCLK_re) begin
				transaction_reg <= {transaction_reg[14:0], COPI_sync[1]};
				num_bits <= num_bits + 1;
			end
			if (num_bits == 16) begin
				addr <= transaction_reg[14:8];
				data <= transaction_reg[7:0];
				data_received <= 1;
				$display("transaction %h", transaction_reg);
				$display("addr %h", addr);
				$display("data %h", data);
			end
		end

		if (nCS_fe) begin
			// transaction started
			transaction <= 1;
			data_received <= 0;
		end
		else if (nCS_re) begin
			// transaction ended
			transaction <= 0;
			num_bits <= 0;
		end
	end
end

always @(posedge clk or negedge rst_n) begin
	if (!rst_n) begin
		en_reg_out_7_0 <= 8'h00;
        en_reg_out_15_8 <= 8'h00;
        en_reg_pwm_7_0 <= 8'h00;
        en_reg_pwm_15_8 <= 8'h00;
        pwm_duty_cycle <= 8'h00;
	end
	else begin
		if (~transaction && data_received) begin
			if (addr == 7'h0) begin
				en_reg_out_7_0 <= data;
			end
			else if (addr == 7'h1) begin
				en_reg_out_15_8 <= data;
			end
			else if (addr == 7'h2) begin
				en_reg_pwm_7_0 <= data;
			end
			else if (addr == 7'h3) begin
				en_reg_pwm_15_8 <= data;
			end
			else if (addr == 7'h4) begin
				pwm_duty_cycle <= data;
			end
		end
	end
end

wire _unused = &{COPI_sync[2], transaction_reg[15]};

endmodule
