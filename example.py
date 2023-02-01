import gc
import utime
import micropython

from vga_driver import TinyVgaDriver


def main():
    vga = TinyVgaDriver(debug=True)
    print(micropython.mem_info())
    vga.start_synchronisation()
    print(micropython.mem_info())

    for i in range(4):
        vga.fbuf.fill(vga.COLOR_RED)
        utime.sleep_ms(500)
        print(i)
        vga.fbuf.fill(vga.COLOR_BLACK)
        utime.sleep_ms(500)

    utime.sleep_ms(10000)
    vga.stop_synchronisation()


if __name__ == "__main__":
    main()
