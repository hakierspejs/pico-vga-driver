# Pi Pico and Pico W VGA driver

### Description

It's a single-color tiny VGA driver for Pi Pico and Pico W which uses 37.4KB memory for pixels storage.
Based on principles described on the https://vanhunteradams.com/Pico/VGA/VGA.html page.
Inspired by the repo https://github.com/HughMaingauche/PICO-VGA-Micropython

![](https://hssi.hs-ldz.pl/640x/http://server/img/1736459728345.jpeg)

### Running locally
By default, it uses GPIO-0 for the RED channel, GPIO-4 for H-SYNC, and GPIO-5 for V-SYNC.
You may redefine GPIO pins on the VGA driver initialization.
For H-SYNC and V-SYNC channels you have to use 47 ohm resistors and for color channels 300 ohm.

BLUE and GREEN channels are connected to the GND as other VGA pins (5,6,7,8,9,10):
![](https://hssn.hs-ldz.pl/pinout/vga.jpg)
If you prefer another font color (GREEN or BLUE), you need to connect necessary colour-channel to COLOR GPIO output (by default - GPIO-0). 
All unnecessary colour channels should be connected to the GND.

To test it locally you have to connect the VGA cable to GPIO pins via resistors,
than install [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) tool and now you may use make command to run the example:

```bash
git clone https://github.com/hakierspejs/pico-vga-driver.git
cd pico-vga-driver
make run
```

The default example draws Hackerspace Łódź logo with QR link. 


Example of usage:
```python
import gc
import utime
import micropython

from vga_driver import TinyVgaDriver


def main():
    vga = TinyVgaDriver()
    print(micropython.mem_info())
    vga.start_synchronisation()
    print(micropython.mem_info())

    for i in range(4):
        vga.fbuf.fill(vga.COLOR_BLACK)
        utime.sleep_ms(1000)
        vga.fbuf.fill(vga.COLOR_RED)
        utime.sleep_ms(1000)
        gc.collect()

    utime.sleep_ms(10000)
    vga.stop_synchronisation()
    gc.collect()


if __name__ == "__main__":
```
More examples you may find in the [examples folder](https://github.com/hakierspejs/pico-vga-driver/blob/master/examples/).

---
Feel free to contribute
