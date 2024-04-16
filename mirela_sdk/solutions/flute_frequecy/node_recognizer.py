import pyaudio
import numpy as np
import librosa
from time import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16


class NoteReconizer(Node):
    note_to_movement = {
        "C": 0,  # Land
        "D": 1,  # Sobe
        "E": 2,  # Desce
        "F": 3,  # Left
        "G": 4,  # Right
        "A": 5,  # Back
        "B": 6,  # Front
    }

    def __init__(self, chunk=1024 * 2, rate=44100) -> None:
        super().__init__("frequency_recognizer")
        self.chunk = chunk
        self.rate = rate
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self.audio_processing,
        )

        self.msg = Int16()

        self.action_pub = self.create_publisher(Int16, "/bebop/frequency_action", 10)

        self.hold_time = 0.4
        self.last_note = None
        self.last_note_time = None

    def audio_processing(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16)
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.rate)
        fft_data = np.abs(np.fft.rfft(data))
        dominant_freq = freqs[np.argmax(fft_data)]

        if dominant_freq > 0:
            note = librosa.hz_to_note(freqs[np.argmax(fft_data)])

            print(note)

            if note == self.last_note and self.last_note_time is not None:
                if time() - self.last_note_time >= self.hold_time:
                    movement = self.note_to_movement.get(note[0], -1)
                    print(
                        f"Movement: {movement} - Note: {note} - Time: {time() - self.last_note_time}"
                    )
                    if movement != -1:
                        self.msg.data = movement
                        self.action_pub.publish(self.msg)
            else:
                self.last_note_time = time()

            self.last_note = note

        return (in_data, pyaudio.paContinue)


def main(args=None):
    rclpy.init(args=args)
    node = NoteReconizer()
    rclpy.spin(node)


if __name__ == "__main__":
    main()
