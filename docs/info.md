<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

The project consists of a PWM peripheral, and a SPI interface (to control the PWM module).

The `ui_in` signal (consisting of `nCS`, `COPI`, and `SCLK`) is fed into the SPI inteface, which synchronizes these signals into the system clock domain, and stores the data encoded in the `COPI` signal into the specified registers (from `0x00` to `0x04`).

These registers control the PWM peripheral to enable/disable the output on different wires and to set the duty cycle of the PWM output.

## How to test

The tests are written in the `uwasic-bootcamp/test/test.py` file.

## External hardware

No external hardware was used.
