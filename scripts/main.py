import serial
import time
import enum
import queue
from pathlib import Path
from transcription import Transcriber
from profanity_filter import filter

import sounddevice as sd
import soundfile as sf


# Depends on the port you plug the Arduino into.
port_name: str = input("Arduino connection Serial Port name: ")

# Should be the same as the baud rate configured by the Arduino code.
baud_rate: int = 19200

# Amount of time to wait before starting the next iteration of the update loop.
sleep_time: float = 0.05


# The buffer containing messages to send to the Arduino circuit.
# The length of each message should be the same as the value specified in the code for the Arduino board.
data_to_send: bytes = b''

# Length of messages sent from the Arduino circuit.
read_msg_length: int = 1

# Buffer containing the partial message being read.
partial_msg: bytes = b''

# Buffer containing the latest full message read from the Arduino circuit since the last process frame.
# If the Arduino circuit has sent multiple full messages since the last read,
# this will only store the latest full message.
read_msg: bytes = b''

# Store the time in the previous process frame.
# Used to get elapsed time between frames.
prev_time: float = time.time()


# The amount of time (in seconds) to decay 1 warning level.
warning_decay_time: float = 10

# The maximum number of strikes that will prompt the ECHOING state.
max_strike_count: int = 3

# The amount of time (in seconds) to calm down after being approached.
calming_down_time: float = 10


# The distance (in metres) from the ultrasonic sensor to the nearest object
# that will prompt the device to transition into the APPROACHED state.
# approached_distance_threshold: float = 0.1


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
    PUNISHMENT = 2
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

    is_approached: bool = False

    is_paused: bool = False
    pass


def get_sound_path(sound: str) -> str:
    return str(Path(__file__).resolve().parent.parent / "resources" / "sounds" / sound)

profanity_audio_filepath:  str = get_sound_path("profanity.mp3")
politics_audio_filepath:   str = get_sound_path("politics.mp3")
approached_audio_filepath: str = get_sound_path("approached.mp3")
punishment_audio_filepath: str = get_sound_path("punishment.mp3")


# Global static class wrapper for playing audio from files and stopping them.
# Code from: https://github.com/spatialaudio/python-sounddevice/blob/master/examples/play_file.py
class DeviceAudioFilePlayer:
    data: sf.AudioData

    current_frame = 0

    @staticmethod
    def callback(outdata, frames, time, status) -> None:
        if status:
            print(status)
            pass
        chunksize = min(len(DeviceAudioFilePlayer.data) - DeviceAudioFilePlayer.current_frame, frames)
        outdata[:chunksize] = DeviceAudioFilePlayer.data[
            DeviceAudioFilePlayer.current_frame:DeviceAudioFilePlayer.current_frame + chunksize
        ]
        if chunksize < frames:
            outdata[chunksize:] = 0
            raise sd.CallbackStop()
        DeviceAudioFilePlayer.current_frame += chunksize
        pass

    @staticmethod
    def onfinished_callback() -> None:
        if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
            DeviceData.audio_request_state = AudioRequestState.AUDIO_FINISHED
            pass
        pass

    stream: sd.OutputStream

    @staticmethod
    def play(audio_filepath) -> None:
        DeviceAudioFilePlayer.data, samplerate = sf.read(audio_filepath, always_2d=True)
        DeviceAudioFilePlayer.stream = sd.OutputStream(
            samplerate=samplerate, channels=DeviceAudioFilePlayer.data.shape[1],
            callback=DeviceAudioFilePlayer.callback,
            finished_callback=DeviceAudioFilePlayer.onfinished_callback
        )
        DeviceAudioFilePlayer.current_frame = 0
        DeviceAudioFilePlayer.stream.start()
        pass

    @staticmethod
    def stop() -> None:
        DeviceAudioFilePlayer.stream.stop()
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
        case DeviceState.PUNISHMENT:
            new_state = 1
            pass
        case DeviceState.APPROACHED:
            new_state = 2
            pass
        case DeviceState.WARNING:
            new_state = 2 + DeviceData.warning_strike_count
            pass
    # Send the state number as a single byte.
    # Assert that the new_state is representable as a single byte.
    assert(0 <= new_state <= 255)
    data_to_send = int.to_bytes(new_state)
    pass


# Plug method to implement.
def process_arduino_state_update() -> None:
    if len(read_msg) > 0:
        msg: int = int.from_bytes(read_msg)
        DeviceData.is_approached =  bool(msg & 0x0F)
        DeviceData.is_paused =  bool(msg & 0xF0)
        pass
    pass

def play_warning_audio() -> None:
    # Play audio based on the number of warning strikes recorded.
    DeviceData.audio_request_state = AudioRequestState.AUDIO_PLAYING
    if DeviceData.has_detected_profanity:
        print("Profanity Warning Played.")
        DeviceAudioFilePlayer.play(profanity_audio_filepath)
        pass
    else:
        print("Political Content Warning Played.")
        DeviceAudioFilePlayer.play(politics_audio_filepath)
        pass
    

def stop_warning_audio() -> None:
    # Pre-maturely stop the warning audio, if needed.
    DeviceAudioFilePlayer.stop()
    pass


def play_approached_audio() -> None:
    # Play approached audio.
    DeviceData.audio_request_state = AudioRequestState.AUDIO_PLAYING
    DeviceAudioFilePlayer.play(approached_audio_filepath)
    pass

def play_punishment_audio() -> None:
    # Play punishment audio.
    DeviceData.audio_request_state = AudioRequestState.AUDIO_PLAYING
    DeviceAudioFilePlayer.play(punishment_audio_filepath)
    pass

def stop_punishment_audio() -> None:
    # Pre-maturely stop the warning audio, if needed.
    DeviceAudioFilePlayer.stop()
    pass




def process_state_idle(delta: float) -> None:
    if DeviceData.is_approached:
        # Transition to APPROACHED state.
        DeviceData.prev_state = DeviceState.IDLE
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0

        play_approached_audio()
        
        send_state_change_data()
        return

    if DeviceData.has_detected_profanity or DeviceData.has_detected_politics:
        # Transition to WWARNING_1 state.
        DeviceData.prev_state = DeviceState.IDLE
        DeviceData.current_state = DeviceState.WARNING
        DeviceData.warning_strike_count += 1
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0

        play_warning_audio()
        
        send_state_change_data()
        return
    pass


def process_warning_state(delta: float) -> None:
    if DeviceData.is_approached:
        # Transition to APPROACHED state.
        if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
            # Pre-maturely stop the currently playing warning audio.
            stop_warning_audio()
            pass
        DeviceData.prev_state = DeviceState.WARNING
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0

        play_approached_audio()
        
        send_state_change_data()
        return

    # No profanity detection or decay while audio is playing.
    if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
        return

    if DeviceData.has_detected_profanity or DeviceData.has_detected_politics:
        # Increase strike count and reset decay timer.
        DeviceData.warning_strike_count += 1
        DeviceData.state_timer = 0
        # If enough strikes have been accumulated, switch to ECHOING state.
        if DeviceData.warning_strike_count > max_strike_count:
            DeviceData.prev_state = DeviceState.WARNING
            DeviceData.current_state = DeviceState.PUNISHMENT
            # Request echoing audio.
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            # Reset strike count.
            DeviceData.warning_strike_count = 0

            play_punishment_audio()
            pass
        else:
            # Request audio for the next warning.
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            play_warning_audio()
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


def process_punishment_state(delta: float) -> None:
    if DeviceData.is_approached:
        # Transition to APPROACHED state.
        if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
            # Pre-maturely stop the currently playing punishment audio.
            stop_punishment_audio()
            pass
        DeviceData.prev_state = DeviceState.PUNISHMENT
        DeviceData.current_state = DeviceState.APPROACHED
        DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
        DeviceData.state_timer = 0

        play_approached_audio()
        
        send_state_change_data()
        return

    # No profanity detection or decay while audio is playing.
    if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
        return

    # Transition to the IDLE state.
    # If the device got interrupted, transition back to the IDLE state
    # without replaying the audio.
    DeviceData.prev_state = DeviceState.PUNISHMENT
    DeviceData.current_state = DeviceState.IDLE
    DeviceData.state_timer = 0

    send_state_change_data()
    pass


def process_approached_state(delta: float) -> None:
    # No calming down while audio is playing.
    if DeviceData.audio_request_state == AudioRequestState.AUDIO_PLAYING:
        return

    if DeviceData.is_approached:
        # If the device was approached again
        # after it has been left alone for a bit to calm down.
        if DeviceData.state_timer > 0:
            # Play the audio again and restart the calming down timer.
            DeviceData.audio_request_state = AudioRequestState.AUDIO_REQUESTED
            DeviceData.state_timer = 0

            play_approached_audio()
            send_state_change_data()
            pass
        # Otherwise, simply do nothing and wait until it is left alone.
        return

    # Keep echoing until the time is up.
    if DeviceData.state_timer >= calming_down_time:
        # Transition back to the previous state.
        if DeviceData.prev_state == DeviceState.PUNISHMENT:
            DeviceData.current_state = DeviceState.IDLE
            pass
        else:
            DeviceData.current_state = DeviceData.prev_state
            pass
        DeviceData.prev_state = DeviceState.APPROACHED
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
        case DeviceState.PUNISHMENT:
            process_punishment_state(delta)
            pass
        case DeviceState.APPROACHED:
            process_approached_state(delta)
            pass
    pass


model = Path(__file__).resolve().parent.parent / "model"
transcriber = Transcriber(model)
transcriber.start()

# The loop runs as often as possible, and never halts to wait for messages from the Arduino circuit.
# The loop blocks until the data_to_send message is fully sent to the Arduino circuit.
with serial.Serial(port_name, baud_rate, timeout=0, write_timeout=None) as serial_port:
    # Send the distance threshold to the Arduino circuit.
    # serial_port.write((str(approached_distance_threshold) + '\n').encode("utf-8"))
    print("Connection Established; Distance Threshold Sent.")
    while True:
        current_time: float = time.time()
        delta: float = max(current_time - prev_time, 0)
        prev_time = current_time

        # Reset flags.
        DeviceData.has_detected_profanity = False
        DeviceData.has_detected_politics = False
        
        # Query transcriber for new complete sentences.
        try:
            # Get a single line from the transcriber.
            kind, text = transcriber.events.get_nowait()

            # Only do processing on the text if the device is not paused.
            # Wait for a complete sentence.
            if not DeviceData.is_paused and kind == "partial":
                # Run the profanity/political filter on it.
                filtered, reason = filter(text)
                if filtered:
                    transcriber.clear()
                    if reason == "profanity":
                        DeviceData.has_detected_profanity = True
                        print("Profanity Detected.")
                        pass
                    else:
                        DeviceData.has_detected_politics = True
                        print("Political Content Detected.")
                        pass
                pass
            pass
        except queue.Empty: pass

        # Read data.
        # Reset the latest read message (read_msg).
        read_msg = b''
        # Only read if there is data.
        if serial_port.in_waiting > 0:
            # Read all messages sent by the Arduino circuit.
            # Store the latest full message into read_msg.
            has_full_msg: bool = serial_port.in_waiting >= read_msg_length - len(partial_msg)
            partial_msg += serial_port.read_all()
            if has_full_msg:
                # The offset of the final message is the number of full messages - 1,
                # altogether multiplied by the length of full messages.
                latest_full_msg_offset: int = (
                    len(partial_msg) // read_msg_length - 1
                ) * read_msg_length
                # Splice the full message.
                read_msg = partial_msg[
                    latest_full_msg_offset :
                    latest_full_msg_offset + read_msg_length
                ]
                # Splice the remainder.
                partial_msg = partial_msg[latest_full_msg_offset + read_msg_length:]
                pass
            # Update the is_approached and is_paused flags
            # based on message from the Arduino board.
            process_arduino_state_update()
            pass

        data_to_send = b''
        if not DeviceData.is_paused:
            process(delta)
            pass

        # Write data, if any.
        if len(data_to_send) > 0:
            serial_port.write(data_to_send)
            pass

        # Wait for a given amount of time to match
        # the frame duration of the process with that of the Arduino board.
        time.sleep(sleep_time)
        pass

transcriber.stop()