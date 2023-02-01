# MIT License
#
# Copyright (c) 2023 Alex Ostrowski
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import gc
import array
import micropython
import framebuf
import machine
from rp2 import PIO, asm_pio
from micropython import const
from uctypes import addressof
from utime import sleep_ms


DMA_BASE = const(0x50000000)
DMA_SIZE_BYTE = const(0)
DMA_SIZE_8 = DMA_SIZE_BYTE
DMA_SIZE_32 = const(2)

DREQ_PIO0_TX2 = const(2)
DREQ_PIO1_TX2 = const(10)

PIO0_BASE = const(0x50200000)
PIO1_BASE = const(0x50300000)
PIO0_TX2 = const(PIO0_BASE + 0x018)
PIO1_TX2 = const(PIO1_BASE + 0x018)


#=============================================================================
# PIO programs
# based on https://vanhunteradams.com/Pico/VGA/VGA.html
# and on https://github.com/HughMaingauche/PICO-VGA-Micropython
#=============================================================================


@asm_pio(set_init=PIO.OUT_HIGH, autopull=True, pull_thresh=32)
def _pio_program_HSYNC():
    # PIO state machine program for HSYNC generation
    # frequency 25MHz
    wrap_target()
    # ACTIVE + FRONTPORCH
    mov(x, osr)
    label("hsyncactive")
    jmp(x_dec, "hsyncactive")
    # SYNC PULSE 1/25*96 = 3,84µs
    set(pins, 0)[31]  # hsync pulse (32 cycles)
    set(pins, 0)[31]  # hsync pulse (64 cycles)
    set(pins, 0)[31]  # hsync pulse (96 cycles)
    # BACKPORCH  1/25*(46+1) = 1.88µs
    set(pins, 1)[31]  # 32 cycles
    set(pins, 1)[13]  # 46 cycles
    irq(0)  # IRQ to signal end of line (47 cycles)
    wrap()


@asm_pio(sideset_init=(PIO.OUT_HIGH,), autopull=True, pull_thresh=32)
def _pio_program_VSYNC():
    # PIO state machine program for VSYNC generation
    # frequency 125MHz
    pull(block)
    wrap_target()
    # ACTIVE
    mov(x, osr)
    label("vsync-active")
    wait(1, irq, 0)
    irq(1)
    jmp(x_dec, "vsync-active")
    # FRONTPORCH
    set(y, 9)  # y register as counter
    label("vsync-frontporch")
    wait(1, irq, 0)  # Wait for hsync backporch
    jmp(y_dec, "vsync-frontporch")  # Remain in vsync-frontporch, decrementing counter
    # SYNC PULSE
    wait(1, irq, 0).side(0)  # Set vsync pin low and wait for one line (hsync pulse)
    wait(1, irq, 0)  # Wait for a second line
    # BACKPORCH
    set(y, 31)  # First part of back porch into y scratch register (and delays a cycle)
    label("vsync-backporch")
    wait(1, irq, 0).side(
        1
    )  # Set vsync pin high and wait for one line (hsync backporch)
    jmp(y_dec, "vsync-backporch")  # Remain in vsync-backporch, decrementing counter
    wait(1, irq, 0)
    wrap()


@asm_pio(
    out_init=(PIO.OUT_LOW,),
    sideset_init=(PIO.OUT_LOW,),
    autopull=True,
    pull_thresh=8,
)
def _pio_program_COLOR():
    # PIO state machine program for RGB generation
    # frequency 100,7MHz
    pull(block)  # pull from FIFO to OSR (only once)
    mov(y, osr)  # copy from OSR to y register
    wrap_target()
    mov(x, y).side(0)  # set colour pins to zero and init counter
    wait(1, irq, 1)  # wait for vsync active mode (starts 5 cycles after execution)
    label("active")
    out(pins, 1)
    nop()[1]
    jmp(x_dec, "active")  # stay active while _pio_program_HSYNC in active mode
    wrap()


#=============================================================================
# DMA channels configuration
#=============================================================================

@micropython.viper
def configure_DMAs(
    pio_id: int,
    dmachan_color_number: int,
    dmachan_activator_number: int,
    fbuf_length: int,
    fbuf_address: ptr32,
):
    # based on https://vanhunteradams.com/Pico/VGA/VGA.html#Using-DMA-to-communicate-pixel-data
    # and on https://github.com/HughMaingauche/PICO-VGA-Micropython

    DMA_CHAN_WIDTH = int(0x40)
    DMA_CHANNEL__READ_ADDR_REG__OFFSET = int(0x0)
    DMA_CHANNEL__WRITE_ADDR_REG__OFFSET = int(0x04)
    DMA_CHANNEL__TRANS_COUNT_REG__OFFSET = int(0x08)
    # Alias 2 for channel N CTRL register
    DMA_CHANNEL__AL2_CTRL__OFFSET = int(0x20)

    # configure color data DMA channel
    # (sends color data to color PIO state machine)
    DMA_CHANNEL_COLOR__OFFSET = int(DMA_BASE) + int(dmachan_color_number) * int(
        DMA_CHAN_WIDTH
    )
    DMA_CHANNEL_COLOR__READ_ADDR_REG = int(DMA_CHANNEL_COLOR__OFFSET) + int(
        DMA_CHANNEL__READ_ADDR_REG__OFFSET
    )
    DMA_CHANNEL_COLOR__WRITE_ADDR_REG = int(DMA_CHANNEL_COLOR__OFFSET) + int(
        DMA_CHANNEL__WRITE_ADDR_REG__OFFSET
    )
    DMA_CHANNEL_COLOR__TRANS_COUNT_REG = int(DMA_CHANNEL_COLOR__OFFSET) + int(
        DMA_CHANNEL__TRANS_COUNT_REG__OFFSET
    )
    DMA_CHANNEL_COLOR___AL2_CTRL_REG = int(DMA_CHANNEL_COLOR__OFFSET) + int(
        DMA_CHANNEL__AL2_CTRL__OFFSET
    )

    # (DREQ = peripheral data request)
    TREQ_SEL = int(DREQ_PIO0_TX2)
    if int(pio_id) == 1:
        TREQ_SEL = int(DREQ_PIO1_TX2)

    CHAIN_TO = int(dmachan_activator_number)
    DATA_SIZE = int(DMA_SIZE_8)
    DMA_CHANNEL_COLOR__CTRL_VALUE = (
        (0 << 31)  # AHB_ERROR=0
        | (0 << 30)  # READ_ERROR=0
        | (0 << 29)  # WRITE_ERROR=0
        | (0 << 24)  # BUSY=0
        | (0 << 23)  # SNIFF_EN=0
        | (0 << 22)  # BSWAP=0
        | (0 << 21)  # IRQ_QUIET=0
        | (TREQ_SEL << 15)  # TREQ_SEL = DREQ_PIO0_TX2 or DREQ_PIO1_TX2
        | (CHAIN_TO << 11)  # CHAIN_TO dmachan_activator_number
        | (0 << 10)  # RING_SEL=0
        | (0 << 6)  # RING_SIZE=0
        | (0 << 5)  # INCR_WRITE=0
        | (1 << 4)  # INCR_READ=0
        | (DATA_SIZE << 2)  # DATA_SIZE 8 bit
        | (1 << 1)  # HIGH_PRIORITY=0
        | (1 << 0)  # EN=0
    )

    ptr32(DMA_CHANNEL_COLOR__READ_ADDR_REG)[0] = 0x0
    ptr32(DMA_CHANNEL_COLOR__WRITE_ADDR_REG)[0] = uint(PIO0_TX2 if pio_id == 0 else PIO1_TX2)
    ptr32(DMA_CHANNEL_COLOR__TRANS_COUNT_REG)[0] = fbuf_length
    ptr32(DMA_CHANNEL_COLOR___AL2_CTRL_REG)[0] = DMA_CHANNEL_COLOR__CTRL_VALUE

    # configure activator data DMA channel
    # which allows to restart color DMA channel

    DMA_CHANNEL_ACTIVATOR__OFFSET = int(DMA_BASE) + int(dmachan_activator_number) * int(
        DMA_CHAN_WIDTH
    )
    DMA_CHANNEL_ACTIVATOR__READ_ADDR_REG = int(DMA_CHANNEL_ACTIVATOR__OFFSET) + int(
        DMA_CHANNEL__READ_ADDR_REG__OFFSET
    )
    DMA_CHANNEL_ACTIVATOR__WRITE_ADDR_REG = int(DMA_CHANNEL_ACTIVATOR__OFFSET) + int(
        DMA_CHANNEL__WRITE_ADDR_REG__OFFSET
    )
    DMA_CHANNEL_ACTIVATOR__TRANS_COUNT_REG = int(DMA_CHANNEL_ACTIVATOR__OFFSET) + int(
        DMA_CHANNEL__TRANS_COUNT_REG__OFFSET
    )
    DMA_CHANNEL_ACTIVATOR__AL2_CTRL_REG = int(DMA_CHANNEL_ACTIVATOR__OFFSET) + int(
        DMA_CHANNEL__AL2_CTRL__OFFSET
    )

    DMA_CHANNEL_ACTIVATOR__CTRL_VALUE = (
        (0 << 31)  # AHB_ERROR=0
        | (0 << 30)  # READ_ERROR=0
        | (0 << 29)  # WRITE_ERROR=0
        | (0 << 24)  # BUSY=0
        | (0 << 23)  # SNIFF_EN=0
        | (0 << 22)  # BSWAP=0
        | (0 << 21)  # IRQ_QUIET=0
        | (0x3F << 15)  # TREQ_SEL = 0x3f
        | (int(dmachan_activator_number) << 11)  # CHAIN_TO self
        | (0 << 10)  # RING_SEL=0
        | (0 << 6)  # RING_SIZE=0
        | (0 << 5)  # INCR_WRITE=0
        | (0 << 4)  # INCR_READ=0
        | (int(DMA_SIZE_32) << 2)  # DATA_SIZE 32 bit
        | (1 << 1)  # HIGH_PRIORITY=0
        | (1 << 0)  # EN=0
    )

    ptr32(DMA_CHANNEL_ACTIVATOR__READ_ADDR_REG)[0] = uint(fbuf_address)
    ptr32(DMA_CHANNEL_ACTIVATOR__WRITE_ADDR_REG)[0] = int(DMA_CHANNEL_COLOR__OFFSET) + 0x3C
    ptr32(DMA_CHANNEL_ACTIVATOR__TRANS_COUNT_REG)[0] = 1
    ptr32(DMA_CHANNEL_ACTIVATOR__AL2_CTRL_REG)[0] = DMA_CHANNEL_ACTIVATOR__CTRL_VALUE

    return

# @micropython.viper
# def show_dma_state():
#     print('DMA_control_word channel0 dmachan_activator_number 0x50000000', hex(ptr32(0x50000000)[0]))
#     print('DMA_control_word channel0 dmachan_activator_number 0x50000004', hex(ptr32(0x50000004)[0]))
#     print('DMA_control_word channel0 dmachan_activator_number 0x50000008', hex(ptr32(0x50000008)[0]))
#     print('DMA_control_word channel0 dmachan_activator_number 0x50000010', hex(ptr32(0x50000010)[0]))
#     print('DMA_control_word channel1 dmachan_color_number: 0x50000040', hex(ptr32(0x50000040)[0]))
#     print('DMA_control_word channel1 dmachan_color_number: 0x50000044', hex(ptr32(0x50000044)[0]))
#     print('DMA_control_word channel1 dmachan_color_number: 0x50000048', hex(ptr32(0x50000048)[0]))
#     print('DMA_control_word channel1 dmachan_color_number: 0x50000060', hex(ptr32(0x50000060)[0]))


def _printstate(msg):
    print("!" * 20)
    print(msg)
    print(micropython.mem_info())


class TinyVgaDriver:
    # 1 bit per pixel
    COLOR_RED = 0b1
    COLOR_BLACK = 0b0

    def __init__(
        self,
        debug=False,
        dmachan_color_number=11,
        dmachan_activator_number=10,
        gpio_pin_hsync=4,
        gpio_pin_vsync=5,
        gpio_pin_color=0,
        pio_id=None,
    ):
        self.resolution_horisontal = 640  # px
        self.resolution_vertical = 480  # px
        self._pixels_buffer_len = int(
            self.resolution_horisontal * self.resolution_vertical / 8  # bits
        )
        self._pixels_buffer = None
        self.fbuf = None
        self._state_machine_hsync = None
        self._state_machine_vsync = None
        self._state_machine_color = None
        self._pio_id = pio_id

        self.dmachan_color_number = dmachan_color_number
        self.dmachan_activator_number = dmachan_activator_number
        self.debug = debug

        self.gpio_pin_hsync = gpio_pin_hsync
        self.gpio_pin_vsync = gpio_pin_vsync
        self.gpio_pin_color = gpio_pin_color

    def _configure_DMA(self, pixels_buffer_pointer):
        crutch_array = array.array("L", [pixels_buffer_pointer])
        configure_DMAs(
            self._pio_id,
            self.dmachan_color_number,
            self.dmachan_activator_number,
            int(self._pixels_buffer_len),
            addressof(crutch_array),
        )
        # show_dma_state()
        return

    def _choose_available_pio(self):
        if self._pio_id is None:
            if self.debug:
                print("choose PIO:")
                print("=" * 10)
                for pio_id in range(2):
                    print(
                        "pio:",
                        pio_id,
                        not any(
                            [PIO(pio_id).state_machine(j).active() for j in range(4)]
                        ),
                    )
                print("=" * 10)
            for pio_id in range(2):
                available = not any(
                    [PIO(pio_id).state_machine(j).active() for j in range(4)]
                )
                if available:
                    self._pio_id = pio_id
                    break
            if self._pio_id is None:
                self._pio_id = 0
                # raise RuntimeError('All programmable I/O interfaces are in use. Unable to configure PIO')

        if self.debug:
            print("selected PIO:", self._pio_id)

    def _init_PIO_state_machines(self):
        # prepare and upload PIO (programmable I/O) state machines
        self._choose_available_pio()
        PIO(self._pio_id).remove_program()

        self._state_machine_hsync = PIO(self._pio_id).state_machine(
            0, _pio_program_HSYNC, freq=25175000, set_base=machine.Pin(self.gpio_pin_hsync)
        )

        self._state_machine_vsync = PIO(self._pio_id).state_machine(
            1, _pio_program_VSYNC, freq=125000000, sideset_base=machine.Pin(self.gpio_pin_vsync)
        )

        self._state_machine_color = PIO(self._pio_id).state_machine(
            2,
            _pio_program_COLOR,
            freq=100700000,
            out_base=machine.Pin(self.gpio_pin_color),
            sideset_base=machine.Pin(self.gpio_pin_color),
        )

    @micropython.viper
    def exec_pio_sm(self):
        if int(self._pio_id) == 0:
            ptr32(PIO0_BASE)[0] |= 0b111
        else:
            ptr32(PIO1_BASE)[0] |= 0b111

    @micropython.viper
    def exec_dma_channel(self, channel_number: int):
        # https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf 2.5.7 DMA List of Registers
        # DMA: MULTI_CHAN_TRIGGER Register Offset: 0x430
        DMA_MULTI_CHAN_TRIGGER_REG_OFFSET = int(0x430)
        DMA_MULTI_CHAN_TRIGGER_REG_ADDR = int(DMA_BASE) + DMA_MULTI_CHAN_TRIGGER_REG_OFFSET
        ptr32(DMA_MULTI_CHAN_TRIGGER_REG_ADDR)[0] |= 0b1 << channel_number

    @micropython.viper
    def stop_dma_channel(self):
        # https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf 2.5.7 DMA List of Registers
        # DMA: CHAN_ABORT Register Offset: 0x444
        DMA_CHAN_ABORT_REG_OFFSET = int(0x444)
        DMA_CHAN_ABORT_REG_ADDR = int(DMA_BASE) + DMA_CHAN_ABORT_REG_OFFSET

        ptr32(DMA_CHAN_ABORT_REG_ADDR)[0]  |= (
            (0b1 << int(self.dmachan_color_number))
            | (0b1 << int(self.dmachan_activator_number))
        )

    def start_synchronisation(self):
        self._pixels_buffer = bytearray(self._pixels_buffer_len)
        self.fbuf = framebuf.FrameBuffer(
            self._pixels_buffer,
            self.resolution_horisontal,
            self.resolution_vertical,
            framebuf.MONO_HLSB,
        )

        # https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf Chapter 3. PIO
        self._init_PIO_state_machines()

        # https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf Chapter 2.; 2.5 DMA
        self._configure_DMA(
            addressof(self._pixels_buffer),
        )

        self._state_machine_hsync.put(
            int(self.resolution_horisontal) + 15
        )  # H active + H Front porch
        self._state_machine_vsync.put(int(self.resolution_vertical) - 1)
        self._state_machine_color.put(int(self.resolution_horisontal) - 1)

        self.exec_dma_channel(self.dmachan_activator_number)
        self.exec_pio_sm()

        gc.collect()
        return self.fbuf

    def stop_synchronisation(self):
        if self.debug:
            _printstate("stop_synchronisation")

        self.stop_dma_channel()

        self._state_machine_color.active(0)
        self._state_machine_vsync.active(0)
        self._state_machine_hsync.active(0)

        PIO(self._pio_id).remove_program()

        self._pixels_buffer = None
        self.fbuf = None
        gc.collect()

        if self.debug:
            _printstate("stop_synchronisation")


if __name__ == "__main__":
    vga = TinyVgaDriver(debug=True)
    print(micropython.mem_info())
    vga.start_synchronisation()
    print(micropython.mem_info())

    for i in range(10):
        _printstate("black " + str(i))
        vga.fbuf.fill(vga.COLOR_BLACK)
        sleep_ms(100)
        vga.fbuf.fill(vga.COLOR_RED)
        sleep_ms(100)
        gc.collect()

    for i in range(10):
        _printstate("black " + str(i))
        vga.fbuf.fill(vga.COLOR_BLACK)
        sleep_ms(100)
        vga.fbuf.fill(vga.COLOR_RED)
        sleep_ms(100)
        gc.collect()

    sleep_ms(1000)
    vga.stop_synchronisation()

    print("finish")
    print(micropython.mem_info())

    sleep_ms(1000)
    machine.reset()
