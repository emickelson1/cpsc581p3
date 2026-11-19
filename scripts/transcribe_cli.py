import sys
import shutil
from pathlib import Path
import profanity_filter

from transcription import Transcriber

def print_in_place(string: str):
    print(f"\r\033[K{string}", end="", flush=True)  # \r returns to column 0, \033[K erases line
    return
    
model = Path(__file__).resolve().parent.parent / "model"
transcriber = Transcriber(model)
transcriber.start()
print("Listening... (say \"Stop\" to end)")

try:
    while True:
        kind, text = transcriber.events.get()
        # if kind == "final": continue
        # print_in_place(text)
        # f, r = profanity_filter.filter(text)
        # if f:
        #     print("Flagged. Clearing partial")
        #     transcriber.clear()
        
        filtered, reason = profanity_filter.filter(text)
        if kind == "partial":
            if not filtered:
                print_in_place(f"[ ... ] {text}")
            else:
                print_in_place(f"[final] {text} (FILTERED! Reason: {reason})\n")
                transcriber.clear()
                
        if kind == "final":
            if not filtered: 
                print_in_place(f"[final] {text}\n")
            else:
                print_in_place(f"[final] {text} (FILTERED! Reason: {reason})\n")
            
        # Stop if the user says "stop"
        if text == "stop":
            print("\nStopping...")
            transcriber.stop()
            break
except KeyboardInterrupt:
    transcriber.stop()