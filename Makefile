PORT=/dev/tty.usbmodem101
ifeq (,$(wildcard /dev/tty.usbmodem101))
	PORT=/dev/tty.usbmodem1101
endif

shell:
	mpremote connect $(PORT) repl

ls:
	mpremote connect $(PORT) ls

burn:
	mpremote connect $(PORT) fs cp ./*.py :

run-vga-driver: burn
	mpremote connect $(PORT) run vga_driver.py

run-example: burn
	mpremote connect $(PORT) run ./examples/simple/main.py

run:
	mpremote connect $(PORT) fs cp ./examples/hs_logo/qrlink.svgpath :
	mpremote connect $(PORT) fs cp ./examples/hs_logo/logo.py :
	mpremote connect $(PORT) fs cp ./examples/hs_logo/draw_svg_path.py :
	mpremote connect $(PORT) fs cp ./vga_driver.py :
	mpremote connect $(PORT) run ./examples/hs_logo/main.py

black:
	black ./*.py

REQUIREMENTS_INFO := $(shell mpremote connect $(PORT) fs ls ./lib/unittest/ | grep __init__.mpy > /dev/null; echo $$?)
test:
ifneq ($(REQUIREMENTS_INFO),0)
	mpremote connect $(PORT) mip install unittest
endif
	mpremote connect $(PORT) run test.py
