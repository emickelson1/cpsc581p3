import serial
import time


# Depends on the port you plug the Arduino into.
port_name: str = ""

# Should be the same as the baud rate configured by the Arduino code.
baud_rate: int = 19200

# Amount of time to wait before starting the next iteration of the update loop.
sleep_time: float = 0.05


# The buffer containing messages to send to the arduino circuit.
# The length of each message should be the same as the value specified in the code for the Arduino board.
data_to_send: bytes = b''

# Length of messages sent from the Arduino board.
read_msg_length: int = 10


def process() -> None:
    # Per-Frame processing logic here.
    pass


with serial.Serial(port_name, baud_rate, timeout=0) as serial_port:
    while True:
        process()

        # Read data.
        #s = serial_port.read(read_msg_length)
        # Write data, if any.
        if len(data_to_send) > 0:
            # Write the data and pop it out from the list.
            data_to_send = data_to_send[serial_port.write(data_to_send):]
            pass
        
        time.sleep(sleep_time)
        pass
    pass