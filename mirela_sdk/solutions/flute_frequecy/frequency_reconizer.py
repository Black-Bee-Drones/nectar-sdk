import pyaudio
import numpy as np
import soundfile as sf

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16


class FrequencyReconizer(Node):
    frequency_bands = {
        1: (518, 551),   # Land
        2: (595, 629),   # Sobe
        3: (655, 700),   # Desce
        4: (705, 750),   # Left
        5: (790, 830),   # Right
        6: (890, 930),  # Back
        7: (980, 1030)   # Front
    }

    def __init__(self, chunk=1024*2, rate=44100)->None:
        super().__init__("frequency_recognizer")
        self.chunk = chunk
        self.rate = rate
        self.audio_path = "tone.wav"
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=self.rate,
                                  input=True,
                                  frames_per_buffer=self.chunk,
                                  stream_callback=self.audio_processing)
        
        self.msg = Int16()

        self.action_pub = self.create_publisher(Int16, "/bebop/frequency_action", 10)

        self.possibilities = [0] * 8 
        self.counter = 0
    
    def range(self, frequency):
        for i, (start, end) in self.frequency_bands.items():
            if start <= frequency <= end:
                return i
        return 0 #if the frequency is not in any known range

    
    def audio_processing(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16) 

        if self.counter <= 10:
            fft_data = abs(np.fft.fft(data).real)**2
            which = fft_data[1:].argmax() + 1

            if which < len(fft_data) - 1:
                y0, y1, y2 = np.log(fft_data[which - 1:which + 2])
                x1 = (y2 - y0) * .5 / (2 * y1 - y2 - y0)
                the_freq = (which + x1) * self.rate / self.chunk
                range_index = self.range(the_freq)
                if range_index != -1:
                    self.possibilities[range_index] += 1
            else:
                the_freq = which * self.rate / self.chunk
                range_index = self.range(the_freq)
                if range_index != -1:
                    self.possibilities[range_index] += 1

            self.counter += 1
        else:
            self.msg.data = -1 if int(np.argmax(self.possibilities)) == 0 else int(np.argmax(self.possibilities))
            self.action_pub.publish(self.msg)
            print(self.msg.data)
            self.possibilities = [0]*8
            self.counter = 0

        return (in_data, pyaudio.paContinue)


    def audio_file_processing(self):
        possibilities = [0]*8  # Initialize the list of possibilities with 0

        # Load the audio file
        data, samplerate = sf.read(self.audio_path)

        # Check if the audio has only one channel, if not, take the first channel
        if len(data.shape) > 1:
            data = data[:, 0]

        # Divide the audio into chunks
        chunk_size = self.chunk
        num_chunks = len(data) // chunk_size

        # Process each chunk
        for i in range(num_chunks):
            chunk = data[i * chunk_size: (i + 1) * chunk_size]

            # Compute the Fourier Fast Transformation
            fft_data = abs(np.fft.fft(chunk).real)**2

            # Find index of max value/dominant frequency
            which = fft_data[1:].argmax() + 1
            if which != len(fft_data) - 1:
                y0, y1, y2 = np.log(fft_data[which - 1:which + 2:])
                x1 = (y2 - y0) * .5 / (2 * y1 - y2 - y0)
                # Find the frequency and update possibilities
                the_freq = (which + x1) * samplerate / chunk_size
                range_index = self.range(the_freq)
                possibilities[range_index] += 1
            else:
                the_freq = which * samplerate / chunk_size
                range_index = self.range(the_freq)
                possibilities[range_index] += 1

        print(np.argmax(possibilities))

    def create_audio(self):
        # Configurações do áudio
        duration = 5  # duração em segundos
        sample_rate = 44100  # taxa de amostragem (Hz)
        frequency = 1030  # frequência do tom (Hz)

        # Criação do array de tempo
        t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)

        # Gera o tom de áudio
        audio_data = 0.5 * np.sin(2 * np.pi * frequency * t)

        # Salva o áudio em um arquivo WAV
        sf.write("tone.wav", audio_data, sample_rate)

def main(args=None):
    rclpy.init(args=args)
    node = FrequencyReconizer()
    rclpy.spin(node)

if __name__ == "__main__":
    main()
