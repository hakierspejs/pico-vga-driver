import array
import gc


COMMAND_CLOSE = b"z"
COMMAND_CLOSE_ABS = b"Z"
COMMAND_MOVE = b"m"
COMMAND_MOVE_ABS = b"M"
COMMAND_LINETO = b"l"
COMMAND_LINETO_ABS = b"L"
COMMANDS = (
    COMMAND_CLOSE,
    COMMAND_CLOSE_ABS,
    COMMAND_MOVE,
    COMMAND_MOVE_ABS,
    COMMAND_LINETO,
    COMMAND_LINETO_ABS,
)


def _convert_command_args(command_args):
    result = []
    prev_x = 0
    prev_y = 0
    for i, value in enumerate(command_args):
        if i % 2 == 0:
            result.append(prev_x + value)
            prev_x = prev_x + value
        else:
            result.append(prev_y + value)
            prev_y = prev_y + value
    return result


def draw(svgpathfile, fbuf, color, offset_x=0, offset_y=0):
    command = b""
    int_buf = b""
    command_args = [0] * 100
    position = [0, 0]
    position_counter = 0
    command_args_counter = 0

    with open(svgpathfile, "rb") as infile:
        while True:
            byte_s = infile.read(1)
            if not byte_s:
                break
            if byte_s in COMMANDS:
                if byte_s == COMMAND_CLOSE or byte_s == COMMAND_CLOSE_ABS:
                    if command == COMMAND_LINETO:
                        command_args = _convert_command_args(command_args)
                    fbuf.poly(
                        position[0] + offset_x,
                        position[1] + offset_y,
                        array.array("h", command_args),
                        color,
                        True,
                    )
                    position_counter = 0
                    command_args_counter = 0
                    gc.collect()
                command = byte_s
                continue

            if byte_s == b"," or byte_s == b" ":
                if int_buf != b"":
                    value = int(int_buf)
                    int_buf = b""
                    if command == COMMAND_MOVE_ABS:
                        position[position_counter] = value
                        position_counter += 1
                    if command == COMMAND_LINETO:
                        command_args[command_args_counter] = value
                        command_args_counter += 1
                    if command == COMMAND_LINETO_ABS:
                        command_args[command_args_counter] = value
                        command_args_counter += 1
                continue
            int_buf += byte_s
    return
