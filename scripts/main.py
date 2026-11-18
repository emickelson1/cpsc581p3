import serial
import time
import enum
import queue
from pathlib import Path
from transcription import Transcriber
from profanity_filter import filter


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
read_msg_length: int = 8

read_msg: bytes = b''

# Store the time in the previous process frame.
# Used to get elapsed time between frames.
prev_time: float = time.process_time()


# The amount of time (in seconds) to decay 1 warning level.
warning_decay_time: float = 60

# The maximum number of strikes that will prompt the ECHOING state.
max_strike_count: int = 3

# The amount of time (in seconds) to calm down after being approached.
calming_down_time: float = 30

# The amount of time to echo what the device hears to cause disruption.
echoing_time: float = 300


# States for whether or not the warning or pleading audio clips
# should be played for any of the WARNING or APPROACHED states.
class AudioRequestState(enum.Enum):
    AUDIO_REQUESTED = 0
    AUDIO_PLAYING = 1
    AUDIO_FINISHED = 2

# States for the device to devise a response.
class DeviceState(enum.Enum):
    IDLE = 0
    WARNING = 1
    ECHOING = 2
    APPROACHED = 3

# A class containing static global data.
class DeviceData:
    # Current and Previous States of the device.
    current_state: DeviceState = DeviceState.IDLE
    prev_state: DeviceState = DeviceState.IDLE

    # Whether or not the audio for the current state
    # has been played or not.
    audio_request_state: AudioRequestState = AudioRequestState.AUDIO_REQUESTED

    # The number of strikes for profanities detected.
    warning_strike_count: int = 0

    # Arbitrary timer that can be used to keep track of
    # how long the device has stayed in a state for.
    state_timer: float = 0

    has_detected_politics: bool = False
    has_detected_profanity: bool = False
    pass



# Helper method to send data to the Arduino board
# when a state-deciding variable is changed
# to notify the Arduino board of the state change.
# The message is an integer representing the state as follows:
# IDLE, ECHOING, APPROACHED = State 0, 1, 2, respectively.
# WARNING = State 3, 4, ... depending on the number of strikes.
#           (number of strikes + 2)
#           (State 3 corresponds to 1 strike; 4 corresponds to 2 strikes; etc.)
def send_state_change_data() -> None:
    global data_to_send
    new_state: int
    match DeviceData.current_state:
        case DeviceState.IDLE:
            new_state = 0
            pass
        case DeviceState.ECHOING:
            new_state = 1
            pass
        case DeviceState.APPROACHED:
            new_state = 2
            pass
        case DeviceState.WARNING:
            new_state = 2 + DeviceData.warning_strike_count
            pass
    data_to_send = bytes(new_state)
    pass


# Plug method to implement.
def is_approached() -> bool:
    # To-do: Insert code to check if the device was approached.
    return False

def play_warning_audio() -> None:
    # To-do: Insert code to play warning audio based on strike count.
    # The warning audio should have a callback to set the DeviceData.audio_request_state appropriately.
    DeviceData.audio_request_state = AudioRequestState.AUDIO_PLAYING
    pass

def play_approached_audio() -> None:
    pass

def start_echoing() -> None:
    # To-do: Insert code to begin echoing audio in the room at a delay.
    # This echoing audio should play indefinitely until stop_echoing() is called.
    DeviceData.audio_request_state = AudioRequestState.AUDIO_PLAYING
    pass

def stop_echoing() -> None:
    # To-do: Insert code to stop echoing audio in the room (the process started by start_echoing()).
    DeviceData.audio_request_state = AudioRequestState.AUDIO_FINISHED
    pass




def process_state_idle(delta: float) -> None:
    approached: bool = is_approached()
    if approached:
        # Transition to APPROACHED state.
        DeviceData.prev_state = DeviceState.IDLE
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        
        send_state_change_data()
        return

    if DeviceData.has_detected_profanity or DeviceData.has_detected_politics:
        # Transition to WWARNING_1 state.
        DeviceData.prev_state = DeviceState.IDLE
        DeviceData.current_state = DeviceState.WARNING
        DeviceData.warning_strike_count += 1
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        
        send_state_change_data()
        return


def process_warning_state(delta: float) -> None:
    approached: bool = is_approached()
    if approached:
        # Transition to APPROACHED state.
        DeviceData.prev_state = DeviceState.WARNING
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        return

    # Play warning audio.
    match DeviceData.audio_request_state:
        case AudioRequestState.AUDIO_REQUESTED:
            play_warning_audio()
            # No profanity detection or decay while audio is playing.
            return
        case AudioRequestState.AUDIO_PLAYING:
            # No profanity detection or decay while audio is playing.
            return

    if DeviceData.has_detected_profanity or DeviceData.has_detected_politics:
        # Increase strike count and reset decay timer.
        DeviceData.warning_strike_count += 1
        DeviceData.state_timer = 0
        # If enough strikes have been accumulated, switch to ECHOING state.
        if DeviceData.warning_strike_count > max_strike_count:
            DeviceData.prev_state = DeviceState.WARNING
            DeviceData.current_state = DeviceState.ECHOING
            # Request echoing audio.
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            # Reset strike count.
            DeviceData.warning_strike_count = 0
            pass
        else:
            # Request audio for the next warning.
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            pass

        send_state_change_data()
        return
    else:
        DeviceData.state_timer += delta
        if DeviceData.state_timer >= warning_decay_time:
            DeviceData.state_timer = 0
            DeviceData.warning_strike_count -= 1
            if DeviceData.warning_strike_count <= 0:
                DeviceData.warning_strike_count = 0
                DeviceData.prev_state = DeviceState.WARNING
                DeviceData.current_state = DeviceState.IDLE
                pass

            send_state_change_data()
            pass
        return


def process_echoing_state(delta: float) -> None:
    approached: bool = is_approached()
    if approached:
        # Transition to APPROACHED state.
        DeviceData.prev_state = DeviceState.ECHOING
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        
        send_state_change_data()
        return

    if DeviceData.audio_request_state == AudioRequestState.AUDIO_REQUESTED:
        start_echoing()
        pass

    # Keep echoing until the time is up.
    if DeviceData.state_timer >= echoing_time:
        # Stop and transition back to IDLE state.
        stop_echoing()
        DeviceData.prev_state = DeviceState.ECHOING
        DeviceData.current_state = DeviceState.IDLE
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        
        send_state_change_data()
        pass
    else:
        DeviceData.state_timer += delta
        pass
    pass


def process_approached_state(delta: float) -> None:
    match DeviceData.audio_request_state:
        case AudioRequestState.AUDIO_REQUESTED:
            play_approached_audio()
            # No calming down while audio is playing.
            return
        case AudioRequestState.AUDIO_PLAYING:
            # No calming down while audio is playing.
            return

    approached: bool = is_approached()
    if approached:
        # Play the audio again and restart the calming down timer.
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0
        send_state_change_data()
        return

    # Keep echoing until the time is up.
    if DeviceData.state_timer >= calming_down_time:
        # Transition back to the previous state.
        DeviceData.current_state = DeviceData.prev_state
        DeviceData.prev_state = DeviceState.APPROACHED

        # If the device went back to the ECHOING state, tell it to start echoing again.
        if DeviceData.current_state == DeviceState.ECHOING:
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            pass
        DeviceData.state_timer = 0
        
        send_state_change_data()
        pass
    else:
        DeviceData.state_timer += delta
        pass
    pass


def process(delta: float) -> None:
    # Per-Frame processing logic here.
    match DeviceData.current_state:
        case DeviceState.IDLE:
            process_state_idle(delta)
            pass
        case DeviceState.WARNING:
            process_warning_state(delta)
            pass
        case DeviceState.ECHOING:
            process_echoing_state(delta)
            pass
        case DeviceState.APPROACHED:
            process_approached_state(delta)
            pass
    pass


model = Path(__file__).resolve().parent.parent / "model"
transcriber = Transcriber(model)
transcriber.start()

with serial.Serial(port_name, baud_rate, timeout=None) as serial_port:
    while True:
        current_time: float = time.process_time()
        delta: float = max(current_time - prev_time, 0)
        prev_time = current_time

        # Reset flags.
        DeviceData.has_detected_profanity = False
        DeviceData.has_detected_politics = False
        
        # Query transcriber for new complete sentences.
        try:
            # Get a single line from the transcriber.
            kind, text = transcriber.events.get_nowait()
            if kind == 'partial': pass      # wait for complete sentence
            else:
                # Run the profanity/political filter on it.
                filtered, reason = filter(text)
                if filtered and reason == "profanity":
                    DeviceData.has_detected_profanity = True
                    pass
                if filtered and reason == "politics":
                    DeviceData.has_detected_politics = True
                    pass
                pass
            pass
        except queue.Empty: pass

        # Read data. Block until the entire message is read.
        # This means that the Arduino board should send data every frame.
        read_msg = b''
        read_msg = serial_port.read(read_msg_length)

        process(delta)

        # Write data, if any.
        if len(data_to_send) > 0:
            # Write the data and pop it out from the list.
            data_to_send = data_to_send[serial_port.write(data_to_send):]
            pass

        # Wait for a given amount of time to match
        # the frame duration of the process with that of the Arduino board.
        time.sleep(sleep_time)
        pass

transcriber.stop()