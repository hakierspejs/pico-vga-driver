import micropython
import utime
from vga_driver import TinyVgaDriver
from logo import PATH_H, PATH_S, PATH_L, PATH_D, PATH_Z
from draw_svg_path import draw as drawsvg


def draw_logo(vga, fbuf, offset_x=120, offset_y=40):
    padding = 10
    logo_size = 388
    small_square_size = 121
    margin = 6
    ell_margin = 8
    radius = 52
    ell_r = radius
    fbuf.rect(offset_x, offset_y, logo_size, logo_size, vga.COLOR_BLACK, True)
    for j in range(3):
        for i in range(3):
            fbuf.rect(
                margin + i * (small_square_size + margin) + offset_x,
                margin + j * (small_square_size + margin) + offset_y,
                small_square_size,
                small_square_size,
                vga.COLOR_RED,
                True,
            )
            if j == 2 or (i == 1 and j == 0) or (i == 2 and j == 1):
                fbuf.ellipse(
                    margin
                    + ell_margin
                    + i * (small_square_size + margin)
                    + ell_r
                    + offset_x,
                    margin
                    + ell_margin
                    + j * (small_square_size + margin)
                    + ell_r
                    + offset_y,
                    ell_r,
                    ell_r,
                    vga.COLOR_BLACK,
                    True,
                )
    letters = (
        (1, 0, PATH_H),
        (2, 1, PATH_S),
        (0, 2, PATH_L),
        (1, 2, PATH_D),
        (2, 2, PATH_Z),
    )
    for i, j, letter in letters:
        fbuf.poly(
            margin
            + ell_margin
            + i * (small_square_size + margin)
            + radius // 2
            + offset_x
            + 1,
            margin
            + ell_margin
            + j * (small_square_size + margin)
            + radius // 2
            + offset_y,
            letter,
            vga.COLOR_RED,
            True,
        )


def main():
    vga = TinyVgaDriver()
    fbuf = vga.start_synchronisation()

    try:
        fbuf.fill(vga.COLOR_RED)

        offset_x = 120
        offset_y = 40

        print(micropython.mem_info())
        fbuf.text("Hackerspace Lodz - pico-vga-driver", 180, 16, vga.COLOR_BLACK)
        draw_logo(vga, fbuf, offset_x, offset_y)
        print(micropython.mem_info())
        drawsvg(
            "qrlink.svgpath",
            fbuf,
            vga.COLOR_BLACK,
            offset_x + 121 + 6 + 6 + 2,
            offset_y + 121 + 6 + 6 + 2,
        )
        print(micropython.mem_info())

        utime.sleep_ms(600 * 1000)

    except Exception as e:
        print(e)
        raise
    finally:
        vga.stop_synchronisation()


if __name__ == "__main__":
    main()
