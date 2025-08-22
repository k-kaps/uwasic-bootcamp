# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

async def find_avg_freq(dut, output, port):
    if output == 0x00:
        signal = dut.uo_out
    elif output == 0x01:
        signal = dut.uio_out
    else:
        dut._log.error("output can be on 0x00 or 0x01") 
        return
     
    count = 0
    frequency_sum = 0

    while count < 3:
        while signal.value == port:
            await RisingEdge(dut.clk)
    
        while signal.value != port:
            await RisingEdge(dut.clk)
        
        time1 = cocotb.utils.get_sim_time(units="ns")

        while signal.value == port:
            await RisingEdge(dut.clk)

        while signal.value != port:
            await RisingEdge(dut.clk)

        time2 = cocotb.utils.get_sim_time(units="ns")

        dut._log.info(f"Rising Edge 1 at {time1}")
        dut._log.info(f"Rising Edge 2 at {time2}")

        time_diff = (time2 - time1)
        frequency = 10**9 * 1/time_diff
        
        dut._log.info(f"Frequency for run {count}: {frequency}")

        frequency_sum += frequency
        count+=1
    
    frequency_avg = frequency_sum/3

    return frequency_avg
 
@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # Write your test here
    dut._log.info("Start PWM Frequency Test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # set duty cycle to 50%
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)

    # for uo_out
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x01)
    assert dut.uo_out.value == 0x01, f"Expected {0x01}, got {dut.uo_out.value}"
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x01)
    frequency = await find_avg_freq(dut, 0x00, 0x01)
    assert 2970 <= frequency <= 3030, f"Expected frequency to be 2970 to 3030, got {frequency}"

    # reset uo out reg and uo pwm reg
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)

    # set duty cycle to 75%
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xC0)

    # for uio_out
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0x04)
    assert dut.uio_out.value == 0x04, f"Expected {0x04}, got {dut.uio_out.value}"
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x04)
    frequency = await find_avg_freq(dut, 0x01, 0x04)
    assert 2970 <= frequency <= 3030, f"Expected frequency to be 2970 to 3030, got {frequency}"

    # reset uo out reg and uo pwm reg
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)

    dut._log.info("PWM Frequency test completed successfully")


async def find_duty_cycle(dut, output, port):
    # Write your test here
    PERIOD = 10**9 * 1/2970 # in ns

    if output == 0x00:
        signal = dut.uo_out
    elif output == 0x01:
        signal = dut.uio_out
    else:
        dut._log.error("output can be on 0x00 or 0x01") 
        return
    
    time_in_loop = 0
    start = cocotb.utils.get_sim_time(units="ns")
    while (signal.value == port):
        time_in_loop = cocotb.utils.get_sim_time(units="ns") - start
        if time_in_loop > PERIOD:
            return 1.0
        await RisingEdge(dut.clk)
    
    time_low_start = cocotb.utils.get_sim_time(units="ns")

    time_in_loop = 0
    start = cocotb.utils.get_sim_time(units="ns")
    while (signal.value != port):
        time_in_loop = cocotb.utils.get_sim_time(units="ns") - start
        if time_in_loop > PERIOD:
            return 0.0
        await RisingEdge(dut.clk)

    time_low_end = cocotb.utils.get_sim_time(units="ns")

    while signal.value == port:
        await RisingEdge(dut.clk)
    
    time_high_end = cocotb.utils.get_sim_time(units="ns")

    time_high = time_high_end - time_low_end
    time_low = time_low_end - time_low_start

    duty_cycle = time_high/(time_high + time_low)
    return duty_cycle

@cocotb.test()
async def test_pwm_duty(dut):
    # Write your test here
    dut._log.info("Start PWM Duty Cycle Test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # test 50% duty cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)
    
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x02)
    assert dut.uo_out.value == 0x02, f"Expected {0x02}, got {dut.uo_out.value}"
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x02)

    duty_cycle = await find_duty_cycle(dut, 0x00, 0x02)
    assert duty_cycle == 0.5, f"Expected 50% duty cycle"

    # reset
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)

    # test 100% duty cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)
    
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0x01)
    assert dut.uio_out.value == 0x01, f"Expected {0x01}, got {dut.uo_out.value}"
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x01)

    duty_cycle = await find_duty_cycle(dut, 0x01, 0x01)
    assert duty_cycle == 0.0, f"Expected 0% duty cycle"

    # reset
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x00)

    # test 0% duty cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)
    
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x01)
    assert dut.uo_out.value == 0x01, f"Expected {0x01}, got {dut.uo_out.value}"
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x01)

    duty_cycle = await find_duty_cycle(dut, 0x00, 0x01)
    assert duty_cycle == 1.0, f"Expected 100% duty cycle"

    # reset
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)

    dut._log.info("PWM Duty Cycle test completed successfully")
