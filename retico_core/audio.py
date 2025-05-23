"""
Audio Module
============

This module defines basic incremental units and incremental modules to handle
audio input (via a standard microphone) and output.
"""

import io
import os
import threading
import queue
import time
import wave
import platform
import keyboard
import librosa
import pyaudio
import numpy as np
import soundfile as sf

import retico_core

CHANNELS = 1
"""Number of channels. For now, this is hard coded MONO. If there is interest to do
stereo or audio with even more channels, it has to be integrated into the modules."""

TIMEOUT = 0.01
"""Timeout in seconds used for the StreamingSpeakerModule."""


def show_audio_devices():
    """Shows all availbale audio input and output devices using pyAudio."""
    p = pyaudio.PyAudio()

    info = p.get_host_api_info_by_index(0)

    print("Output Devices:")
    for i in range(info["deviceCount"]):
        device = p.get_device_info_by_host_api_device_index(0, i)
        if device["maxOutputChannels"] > 0:
            print("  %s (%d)" % (device["name"], device["index"]))

    print("\nInput Devices:")
    for i in range(info["deviceCount"]):
        device = p.get_device_info_by_host_api_device_index(0, i)
        if device["maxInputChannels"] > 0:
            print("  %s (%d)" % (device["name"], device["index"]))


class AudioIU(retico_core.IncrementalUnit):
    """An audio incremental unit that receives raw audio data from a source.

    The audio contained should be monaural.

    Attributes:
        creator (AbstractModule): The module that created this IU
        previous_iu (IncrementalUnit): A link to the IU created before the
            current one.
        grounded_in (IncrementalUnit): A link to the IU this IU is based on.
        created_at (float): The UNIX timestamp of the moment the IU is created.
        raw_audio (bytes[]): The raw audio of this IU
        rate (int): The frame rate of this IU
        nframes (int): The number of frames of this IU
        sample_width (int): The bytes per sample of this IU
    """

    @staticmethod
    def type():
        return "Audio IU"

    def __init__(
        self,
        creator=None,
        iuid=0,
        previous_iu=None,
        grounded_in=None,
        rate=None,
        nframes=None,
        sample_width=None,
        raw_audio=None,
        **kwargs
    ):
        super().__init__(
            creator=creator,
            iuid=iuid,
            previous_iu=previous_iu,
            grounded_in=grounded_in,
            payload=raw_audio,
        )
        self.raw_audio = raw_audio
        self.rate = rate
        self.nframes = nframes
        self.sample_width = sample_width

    def set_audio(self, raw_audio, nframes, rate, sample_width):
        """Sets the audio content of the IU."""
        self.set_data(
            raw_audio=raw_audio,
            payload=raw_audio,
            nframes=int(nframes),
            rate=int(rate),
            sample_width=int(sample_width),
        )

    def audio_length(self):
        """Return the length of the audio IU in seconds.

        Returns:
            float: Length of the audio in this IU in seconds.
        """
        return float(self.nframes) / float(self.rate)


class SpeechIU(AudioIU):
    """A type of audio incremental unit that contains a larger amount of audio
    information and the information if the audio should be dispatched or not.

    This IU can be processed by an AudioDispatcherModule which converts this
    type of IU to AudioIU.
    """

    @staticmethod
    def type():
        return "Speech IU"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dispatch = False


class DispatchedAudioIU(AudioIU):
    """A type of audio incremental unit that is dispatched by an
    AudioDispatcherModule. It has the information of the percentual completion
    of the dispatched audio. This may be useful for a dialog manager that
    wants to track the status of the current dispatched audio.
    """

    @staticmethod
    def type():
        return "Dispatched Audio IU"

    def __init__(self, completion=None, is_dispatching=None, **kwargs):
        super().__init__(**kwargs)
        self.completion = completion
        self.is_dispatching = is_dispatching

    def set_dispatching(self, completion, is_dispatching):
        """Set the completion percentage and the is_dispatching flag.

        Args:
            completion (float): The degree of completion of the current
                utterance.
            is_dispatching (bool): Whether or not the dispatcher is currently
                dispatching
        """
        self.set_data(
            completion=completion,
            is_dispatching=is_dispatching,
        )


class MicrophoneModule(retico_core.AbstractProducingModule):
    """A module that produces IUs containing audio signals that are captured by
    a microphone."""

    @staticmethod
    def name():
        return "Microphone Module"

    @staticmethod
    def description():
        return "A prodicing module that records audio from microphone."

    @staticmethod
    def output_iu():
        return AudioIU

    def callback(self, in_data, frame_count, time_info, status):
        """The callback function that gets called by pyaudio.

        Args:
            in_data (bytes[]): The raw audio that is coming in from the
                microphone
            frame_count (int): The number of frames that are stored in in_data
        """
        self.audio_buffer.put(in_data)
        return (in_data, pyaudio.paContinue)

    def __init__(self, frame_length=0.02, rate=16000, sample_width=2, **kwargs):
        """
        Initialize the Microphone Module.

        Args:
            frame_length (float): The length of one frame (i.e., IU) in seconds
            rate (int): The frame rate of the recording
            sample_width (int): The width of a single sample of audio in bytes.
        """
        super().__init__(**kwargs)
        self.frame_length = frame_length
        self.chunk_size = round(rate * frame_length)
        self.rate = rate
        self.sample_width = sample_width

        self._p = pyaudio.PyAudio()

        self.audio_buffer = queue.Queue()
        self.stream = None

    def process_update(self, _):
        if not self.audio_buffer:
            return None
        try:
            sample = self.audio_buffer.get(timeout=1.0)
        except queue.Empty:
            return None
        output_iu = self.create_iu(
            raw_audio=sample,
            nframes=self.chunk_size,
            rate=self.rate,
            sample_width=self.sample_width,
        )
        return retico_core.UpdateMessage.from_iu(output_iu, retico_core.UpdateType.ADD)

    def setup(self, **kwargs):
        """Set up the microphone for recording."""
        super().setup(**kwargs)
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=CHANNELS,
            rate=self.rate,
            input=True,
            output=False,
            stream_callback=self.callback,
            frames_per_buffer=self.chunk_size,
            start=False,
        )

    def prepare_run(self):
        super().prepare_run()
        if self.stream:
            self.stream.start_stream()

    def shutdown(self):
        """Close the audio stream."""
        super().shutdown()
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.audio_buffer = queue.Queue()


class SpeakerModule(retico_core.AbstractConsumingModule):
    """A module that consumes AudioIUs of arbitrary size and outputs them to the
    speakers of the machine. When a new IU is incoming, the module blocks as
    long as the current IU is being played."""

    @staticmethod
    def name():
        return "Speaker Module"

    @staticmethod
    def description():
        return "A consuming module that plays audio from speakers."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return None

    def __init__(self, rate=44100, sample_width=2, use_speaker="both", device_index=None, **kwargs):
        super().__init__(**kwargs)
        self.rate = rate
        self.sample_width = sample_width
        self.use_speaker = use_speaker

        self._p = pyaudio.PyAudio()

        if device_index is None:
            device_index = self._p.get_default_output_device_info()["index"]
        self.device_index = device_index

        self.stream = None
        self.time = None

    def process_update(self, update_message):
        for iu, ut in update_message:
            if ut == retico_core.UpdateType.ADD:
                self.stream.write(bytes(iu.raw_audio))
        return None

    def setup(self, **kwargs):
        """Set up the speaker for outputting audio"""
        super().setup(**kwargs)
        p = self._p

        if platform.system() == "Darwin":
            if self.use_speaker == "left":
                stream_info = pyaudio.PaMacCoreStreamInfo(channel_map=(0, -1))
            elif self.use_speaker == "right":
                stream_info = pyaudio.PaMacCoreStreamInfo(channel_map=(-1, 0))
            else:
                stream_info = pyaudio.PaMacCoreStreamInfo(channel_map=(0, 0))
        else:
            stream_info = None

        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=CHANNELS,
            rate=self.rate,
            input=False,
            output_host_api_specific_stream_info=stream_info,
            output=True,
            output_device_index=self.device_index,
        )

    def shutdown(self):
        """Close the audio stream."""
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None


class StreamingSpeakerModule(retico_core.AbstractConsumingModule):
    """A module that consumes Audio IUs and outputs them to the speaker of the
    machine. The audio output is streamed and thus the Audio IUs have to have
    exactly [chunk_size] samples."""

    @staticmethod
    def name():
        return "Streaming Speaker Module"

    @staticmethod
    def description():
        return "A consuming module that plays audio from speakers."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return None

    def callback(self, in_data, frame_count, time_info, status):
        """The callback function that gets called by pyaudio."""
        if self.audio_buffer:
            try:
                audio_paket = self.audio_buffer.get(timeout=TIMEOUT)
                return (audio_paket, pyaudio.paContinue)
            except queue.Empty:
                pass
        return (b"\0" * frame_count * self.sample_width, pyaudio.paContinue)

    def __init__(self, frame_length=0.02, rate=44100, sample_width=2, **kwargs):
        """Initialize the streaming speaker module.

        Args:
            frame_length (float): The length of one frame (i.e., IU) in seconds.
            rate (int): The frame rate of the audio. Defaults to 44100.
            sample_width (int): The sample width of the audio. Defaults to 2.
        """
        super().__init__(**kwargs)
        self.frame_length = frame_length
        self.chunk_size = round(rate * frame_length)
        self.rate = rate
        self.sample_width = sample_width

        self._p = pyaudio.PyAudio()

        self.audio_buffer = queue.Queue()
        self.stream = None

    def process_update(self, update_message):
        for iu, ut in update_message:
            if ut == retico_core.UpdateType.ADD:
                self.audio_buffer.put(iu.raw_audio)
        return None

    def setup(self, **kwargs):
        """Set up the speaker for speaking...?"""
        super().setup(**kwargs)
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=CHANNELS,
            rate=self.rate,
            input=False,
            output=True,
            stream_callback=self.callback,
            frames_per_buffer=self.chunk_size,
        )

    def prepare_run(self):
        super().prepare_run()
        self.stream.start_stream()

    def shutdown(self):
        """Close the audio stream."""
        super().shutdown()
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.audio_buffer = queue.Queue()


class AudioDispatcherModule(retico_core.AbstractModule):
    """An Audio module that takes a raw audio stream of arbitrary size and
    outputs AudioIUs with a specific chunk size at the rate it would be produced
    if the audio was being played.

    This could be espacially useful when an agents' TTS module produces an
    utterance, but this utterance should not be transmitted as a whole but in
    an incremental way.

    Attributes:
        target_frame_length (float): The size of each output IU in seconds.
        target_chunk_size (int): The size of each output IU in samples.
        silence (bytes): A bytes array containing [target_chunk_size] samples
            of silence that is dispatched when [continuous] is True and no input
            IU is dispatched.
        continuous (bool): Whether or not the dispatching should be continuous.
            If True, AudioIUs with "silence" will be disptached if no input IUs
            are being dispatched. If False, no IUs will be produced during
            silence.
        rate (int): The sample rate of the outout and the input IU.
        sample_width (int): The sample with of the output and input IU.
        speed (float): The speed of the dispatching. 1.0 means realtime.
        dispatching_mutex (threading.Lock): The mutex if an input IU is
            currently being dispatched.
        audio_buffer (list): The current audio buffer containing the output IUs
            that are currently dispatched.
        run_loop (bool): Whether or not the dispatching loop is running.
        interrupt (bool): Whether or not incoming IUs interrupt the old
            dispatching
    """

    @staticmethod
    def name():
        return "Audio Dispatching Module"

    @staticmethod
    def description():
        return "A module that transmits audio by splitting it up into" "streamable pakets."

    @staticmethod
    def input_ius():
        return [SpeechIU]

    @staticmethod
    def output_iu():
        return DispatchedAudioIU

    def __init__(
        self,
        target_frame_length=0.02,
        rate=44100,
        sample_width=2,
        speed=1.0,
        continuous=True,
        silence=None,
        interrupt=True,
        **kwargs
    ):
        """Initialize the AudioDispatcherModule with the given arguments.

        Args:
            target_frame_length (float): The length of each output IU in seconds.
            rate (int): The sample rate of the outout and the input IU.
            sample_width (int): The sample with of the output and input IU.
            speed (float): The speed of the dispatching. 1.0 means realtime.
            continuous (bool): Whether or not the dispatching should be
                continuous. If True, AudioIUs with "silence" will be dispatched
                if no input IUs are being dispatched. If False, no IUs will be
                produced during silence.
            silence (bytes): A bytes array containing target_frame_length seconds of
                of silence. If this argument is set to None, a default silence
                of all zeros will be set.
            interrupt (boolean): If this flag is set, a new input IU with audio
                to dispatch will stop the current dispatching process. If set to
                False, the "old" dispatching will be finished before the new one
                is started. If the new input IU has the dispatching flag set to
                False, dispatching will always be stopped.
        """
        super().__init__(**kwargs)
        self.target_frame_length = target_frame_length
        self.target_chunk_size = round(target_frame_length * rate)
        if not silence:
            self.silence = b"\0" * self.target_chunk_size * sample_width
        else:
            self.silence = silence
        self.continuous = continuous
        self.rate = rate
        self.sample_width = sample_width
        self._is_dispatching = False
        self.dispatching_mutex = threading.Lock()
        self.audio_buffer = []
        self.run_loop = False
        self.speed = speed
        self.interrupt = interrupt

    def is_dispatching(self):
        """Return whether or not the audio dispatcher is dispatching a Speech
        IU.

        Returns:
            bool: Whether or not speech is currently dispatched
        """
        with self.dispatching_mutex:
            return self._is_dispatching

    def set_dispatching(self, value):
        """Set the dispatching value of this module in a thread safe way.

        Args:
            value (bool): The new value of the dispatching flag.
        """
        with self.dispatching_mutex:
            self._is_dispatching = value

    def process_update(self, update_message):
        cur_width = self.target_chunk_size * self.sample_width
        # If the AudioDispatcherModule is set to intterupt mode or if the
        # incoming IU is set to not dispatch, we stop dispatching and clean the
        # buffer
        for iu, ut in update_message:
            if ut != retico_core.UpdateType.ADD:
                continue
            if self.interrupt or not iu.dispatch:
                self.set_dispatching(False)
                self.audio_buffer = []
            if iu.dispatch:
                # Loop over all frames (frame-sized chunks of data) in the input IU
                # and add them to the buffer to be dispatched by the
                # _dispatch_audio_loop
                for i in range(0, iu.nframes, self.target_chunk_size):
                    cur_pos = i * self.sample_width
                    data = iu.raw_audio[cur_pos : cur_pos + cur_width]
                    distance = cur_width - len(data)
                    data += b"\0" * distance

                    completion = float((i + self.target_chunk_size) / iu.nframes)
                    if completion > 1:
                        completion = 1

                    # current_iu = self.create_iu(iu)
                    # current_iu.set_dispatching(completion, True)
                    # current_iu.set_audio(
                    #     data, self.target_chunk_size, self.rate, self.sample_width
                    # )
                    current_iu = self.create_iu(
                        grounded_in=iu,
                        completion=completion,
                        is_dispatching=True,
                        raw_audio=data,
                        nframes=self.target_chunk_size,
                        rate=self.rate,
                        sample_width=self.sample_width,
                    )
                    self.audio_buffer.append(current_iu)
                self.set_dispatching(True)
        return None

    def _dispatch_audio_loop(self):
        """A method run in a thread that adds IU to the output queue."""
        while self.run_loop:
            with self.dispatching_mutex:
                if self._is_dispatching:
                    if self.audio_buffer:
                        self.append(
                            retico_core.UpdateMessage.from_iu(self.audio_buffer.pop(0), retico_core.UpdateType.ADD)
                        )
                    else:
                        self._is_dispatching = False
                if not self._is_dispatching:  # no else here! bc line above
                    if self.continuous:
                        # current_iu = self.create_iu(None)
                        # current_iu.set_audio(
                        #     self.silence,
                        #     self.target_chunk_size,
                        #     self.rate,
                        #     self.sample_width,
                        # )
                        # current_iu.set_dispatching(0.0, False)
                        current_iu = self.create_iu(
                            grounded_in=None,
                            completion=0.0,
                            is_dispatching=False,
                            raw_audio=self.silence,
                            nframes=self.target_chunk_size,
                            rate=self.rate,
                            sample_width=self.sample_width,
                        )
                        self.append(retico_core.UpdateMessage.from_iu(current_iu, retico_core.UpdateType.ADD))
            time.sleep((self.target_chunk_size / self.rate) / self.speed)

    def prepare_run(self):
        super().prepare_run()
        self.run_loop = True
        t = threading.Thread(target=self._dispatch_audio_loop)
        t.start()

    def shutdown(self):
        super().shutdown()
        self.run_loop = False
        self.audio_buffer = []


class AudioRecorderModule(retico_core.AbstractConsumingModule):
    """A Module that consumes AudioIUs and saves them as a PCM wave file to
    disk."""

    @staticmethod
    def name():
        return "Audio Recorder Module"

    @staticmethod
    def description():
        return "A Module that saves incoming audio to disk."

    @staticmethod
    def input_ius():
        return [AudioIU]

    def __init__(self, filename, rate=44100, sample_width=2, **kwargs):
        """Initialize the audio recorder module.

        Args:
            filename (string): The file name where the audio should be recorded
                to. The path to the file has to be created beforehand.
            rate (int): The sample rate of the input and thus of the wave file.
                Defaults to 44100.
            sample_width (int): The width of one sample. Defaults to 2.
        """
        super().__init__(**kwargs)
        self.filename = filename
        self.wavfile = None
        self.rate = rate
        self.sample_width = sample_width

    def process_update(self, update_message):
        for iu, ut in update_message:
            if ut == retico_core.UpdateType.ADD:
                self.wavfile.writeframes(iu.raw_audio)

    def setup(self, **kwargs):
        super().setup(**kwargs)
        self.wavfile = wave.open(self.filename, "wb")
        self.wavfile.setframerate(self.rate)
        self.wavfile.setnchannels(CHANNELS)
        self.wavfile.setsampwidth(self.sample_width)

    def shutdown(self):
        self.wavfile.close()


class MicrophonePTTModule(MicrophoneModule):
    """A modules overrides the MicrophoneModule which captures audio signal from the microphone and chunks the audio signal into AudioIUs.
    The addition of this module is the introduction of the push-to-talk capacity : the microphone's audio signal is captured only while the M key is pressed.
    """

    def __init__(self, key="m", **kwargs):
        """
        Initialize the Push-To-Talk Microphone Module.

        Args:
            key (string): Key used for Push-To-Talk.
        """
        super().__init__(**kwargs)
        self.key = key

    def callback(self, in_data, frame_count, time_info, status):
        """The callback function that gets called by pyaudio.

        Args:
            in_data (bytes[]): The raw audio that is coming in from the
                microphone
            frame_count (int): The number of frames that are stored in in_data
        """
        if keyboard.is_pressed(self.key):
            self.audio_buffer.put(in_data)
        else:
            self.audio_buffer.put(b"\x00" * self.sample_width * self.chunk_size)
        return (in_data, pyaudio.paContinue)

    def process_update(self, _):
        """
        Returns:
            UpdateMessage: list of AudioIUs produced from the microphone's audio signal.
        """
        if not self.audio_buffer:
            return None
        try:
            sample = self.audio_buffer.get(timeout=1.0)
        except queue.Empty:
            return None
        output_iu = self.create_iu(
            raw_audio=sample,
            nframes=self.chunk_size,
            rate=self.rate,
            sample_width=self.sample_width,
        )
        return retico_core.UpdateMessage.from_iu(output_iu, retico_core.UpdateType.ADD)


#############
# Audio Utils
#############

"""
There is 2 commonly used format for audio data, the following functions provides you with the ability to convert between them, or load file in a specific format.
- PCM16: audio data as int16 PCM bytes, commonly used to write or play raw audio as 16-bit PCM
- float32: audio data as float32 np array, commonly used to process/analyze audio in standard float format.
- (BONUS) WAVPCM16: audio data as int16 PCM bytes (just like PCM16), but containing the headers, and metadata used by several programms to play audio. It is the format you get when you open the .wav file as bytes in python.
"""


def resample_audio_file(src: str, dst: str, outrate: int = 16000):
    """Resample the audio's frame_rate to correspond to
    self.target_framerate.

    Args:
        src (str): source file to resample
        dst (_type_): destination file to write resampled audio in
        outrate (int, optional): The target samplerate. Defaults to 16000.
    """
    if not os.path.exists(src):
        print("Source not found!")
        return False

    if not os.path.exists(os.path.dirname(dst)):
        os.makedirs(os.path.dirname(dst))

    try:
        audio, sr = librosa.load(src, sr=None)
        print(sr)
    except:
        print("Failed to open source file!")
        return False

    resampled_audio = librosa.resample(audio, orig_sr=sr, target_sr=outrate)

    try:
        sf.write(dst, resampled_audio, outrate)
    except:
        print("Failed to write wav")
        return False


def resample_audio(raw_audio: bytes, inrate: int, outrate: int):
    """Resample the audio's frame_rate to correspond to outrate.

    Args:
        raw_audio (bytes): the audio received from the microphone that
            could need resampling.
        inrate (int): the original samplerate
        outrate (int): the target samplerate

    Returns:
        bytes: resampled audio bytes
    """
    audio_np = convert_audio_PCM16_to_float32(raw_audio)
    resampled_audio = librosa.resample(audio_np, orig_sr=inrate, target_sr=outrate)
    return convert_audio_float32_to_PCM16(resampled_audio)


def get_sf_sample_width(subtype: str):
    return {"PCM_16": 2, "PCM_24": 3, "PCM_32": 4, "FLOAT": 4, "DOUBLE": 8}.get(subtype, None)


def load_audiofile_float32(file_path: str):
    audio_data, fs = sf.read(file_path)
    infos = sf.info(file_path)
    metadata = {
        "nframes": infos.frames,
        "rate": fs,
        "sampwidth": get_sf_sample_width(infos.subtype),
        "n_channels": infos.channels,
    }
    return audio_data, metadata


def load_audiofile_PCM16(file_path: str):
    with wave.open(file_path, "rb") as wf:
        metadata = {
            "nframes": wf.getnframes(),
            "rate": wf.getframerate(),
            "sampwidth": wf.getsampwidth(),
            "n_channels": wf.getnchannels(),
        }
        audio_data = wf.readframes(wf.getnframes())
    return audio_data, metadata


def load_audiofile_WAVPCM16(file_path: str):
    with open(file_path, "rb") as f:
        return f.read(), {}


def convert_audio_float32_to_PCM16(raw_audio: object, clip: bool = False):
    """Convert the audio from float32 np array to PCM int16 bytes.

    Args:
        raw_audio (ArrayLike): ArrayLike audio bytes to format.
        clip (bool, optional): Boolean to set to clip the audio bytes. Defaults to False.

    Returns:
        bytes: audio bytes formatted to PCM int16.
    """
    if clip:
        float_audio = np.clip(raw_audio, -1.0, 1.0)  # optional but good practice
    else:
        float_audio = np.array(raw_audio)
    return (float_audio * 32768).astype(np.int16).tobytes()


def convert_audio_PCM16_to_float32(raw_audio: bytes):
    """Convert the audio from PCM int16 bytes to float32 np array.

    Args:
        raw_audio (bytes): audio bytes to format.

    Returns:
        ArrayLike: Audio data formatted as a float32 np.array.
    """

    return np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0


def convert_audio_float32_to_WAVPCM16(raw_audio: object, samplerate: int = 16000):
    """Convert the audio from float32 np array to PCM int16 bytes. (adding headers, etc).

    Args:
        raw_audio (ArrayLike): ArrayLike audio bytes to format.
        samplerate (int, optional): The target samplerate. Defaults to 16000.

    Returns:
        bytes: audio bytes formatted to WAV PCM int16.
    """
    buffer = io.BytesIO()
    sf.write(buffer, raw_audio, samplerate=samplerate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def convert_audio_PCM16_to_WAVPCM16(
    raw_audio: bytes, sample_rate: int = 16000, num_channels: int = 1, sampwidth: int = 2
):
    """Convert the audio from PCM int16 bytes to WAV PCM int16. (adding headers, etc).

    Args:
        raw_audio (bytes): audio bytes to format.

    Returns:
        bytes: audio bytes formatted to WAV PCM int16.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sampwidth)  # 2 bytes for int16
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(raw_audio)
    return buffer.getvalue()


def convert_audio_PCM16_to_WAVPCM16_2(raw_audio: bytes, samplerate: int = 16000):
    """Convert the audio from PCM int16 bytes to float32 np array. (adding headers, etc).

    Args:
        raw_audio (bytes): audio bytes to format.

    Returns:
        bytes: audio bytes formatted to WAV PCM int16.
    """
    float32_data = convert_audio_PCM16_to_float32(raw_audio)
    return convert_audio_float32_to_WAVPCM16(float32_data, samplerate=samplerate)
