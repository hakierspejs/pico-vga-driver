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

examplerun: burn
	mpremote connect $(PORT) run example.py

run: burn
	mpremote connect $(PORT) run vga_driver.py

black:
	black ./*.py

REQUIREMENTS_INFO := $(shell mpremote connect $(PORT) fs ls ./lib/unittest/ | grep __init__.mpy > /dev/null; echo $$?)
test:
ifneq ($(REQUIREMENTS_INFO),0)
	mpremote connect $(PORT) mip install unittest
endif
	mpremote connect $(PORT) run test.py
