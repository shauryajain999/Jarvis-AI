print("Preparing Jarvis......")
import os
import sounddevice as sd
from scipy.io.wavfile import write
from scipy.signal import butter, lfilter
from jarvis_requirements import BANDPASS_HIGH, BANDPASS_LOW, SAMPLE_RATE
from jarvis_requirements import BANDPASS_ORDER
print("Prepared")
# --------------------------------------------------------------------------------------------------------


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    return butter(order, [low, high], btype='band')
#------------------------------------------------------------------------------------------------------------------


_BANDPASS_B, _BANDPASS_A = butter_bandpass(
    BANDPASS_LOW, BANDPASS_HIGH, SAMPLE_RATE, order=BANDPASS_ORDER
)
#-------------------------------------------------------------------------------------------------------------


def apply_bandpass(data):
    return lfilter(_BANDPASS_B, _BANDPASS_A, data)
# --------------------------------------------------------------------------------------------------------


def speak(text, dwrt = False):
    import pyttsx3
    import os, winsound
    from jarvis_backend import speak
    from pycaw.pycaw import AudioUtilities
    from jarvis_requirements import LEVEL

    engine = pyttsx3.init()
    engine.setProperty("rate", 194)
    engine.setProperty("volume", 1.0)
    if dwrt == False :
        print(text)
    
    MY_PID = os.getpid()
    saved = {}
    for s in AudioUtilities.GetAllSessions():
        if s.Process and s.Process.pid != MY_PID:
            vol = s.SimpleAudioVolume
            saved[s.Process.pid] = vol.GetMasterVolume()
            vol.SetMasterVolume(LEVEL, None)

    engine.say(text)
    engine.runAndWait()

    for s in AudioUtilities.GetAllSessions():
        if s.Process and s.Process.pid in saved:
            s.SimpleAudioVolume.SetMasterVolume(saved[s.Process.pid], None)
# --------------------------------------------------------------------------------------------------------


def wish_user():
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        speak("Good morning.")
    elif hour < 18:
        speak("Good afternoon.")
    else:
        speak("Good evening.")
    speak("I am Jarvis. how can i help you?")
# -----------------------------------------------------------------------------------------------------------


def get_best_device_index():
    """Return the index of a usable input device, or None if none found."""
    try:
        default = sd.default.device[0]  # default input device
        if default is not None and default >= 0:
            return default
    except (AttributeError, IndexError, TypeError):
        pass  # fall through to manual scan below

    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                return i
    except Exception:
        pass

    return None
#----------------------------------------------------------------------------------------------------------------


def wait_for_input_device(poll_interval=2.0):
    import time
    """Block until a usable input device is found, retrying periodically.

    Raises KeyboardInterrupt if the user cancels while waiting.
    """
    device = get_best_device_index()
    attempt = 0
    while device is None:
        attempt += 1
        print(f"No input device found (attempt {attempt}). Retrying in {poll_interval}s...")
        time.sleep(poll_interval)
        device = get_best_device_index()
    return device
# -----------------------------------------------------------------------------------------------------------


def listen():
    import tempfile
    import queue
    import speech_recognition as sr
    import numpy as np
    from jarvis_requirements import SAMPLE_RATE, BLOCKSIZE, GAIN, ENERGY_THRESHOLD
    from jarvis_requirements import SILENCE_LIMIT_BLOCKS, WAKE_WORD, LANGUAGE
    
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 250
    recognizer.pause_threshold = 1.0

    device = wait_for_input_device()

    sd.default.device = device

    fs = SAMPLE_RATE
    audio_queue = queue.Queue()
    print("Listening...")

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        audio_queue.put(indata.copy())

    stream = sd.InputStream(
        samplerate=fs,
        channels=1,
        dtype='float32',
        blocksize=BLOCKSIZE,
        callback=callback)
    stream.start()

    chunks = []  # collect chunks and concatenate once, instead of repeated np.concatenate
    speech_started = False
    silence_counter = 0

    try:
        while True:
            try:
                # Block briefly instead of busy-polling audio_queue.empty()
                data = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            audio = data.flatten()
            audio = audio * GAIN
            audio = np.clip(audio, -1.0, 1.0)
            audio = apply_bandpass(audio)
            energy = np.sqrt(np.mean(audio ** 2))

            if energy > ENERGY_THRESHOLD:
                speech_started = True
                silence_counter = 0
                chunks.append(audio)
            else:
                if speech_started:
                    silence_counter += 1
                    chunks.append(audio)

            if speech_started and silence_counter > SILENCE_LIMIT_BLOCKS:
                audio_data = np.concatenate(chunks)
                max_val = np.max(np.abs(audio_data))
                if max_val > 0:
                    audio_data = audio_data / max_val
                audio_data = (audio_data * 32767).astype(np.int16)

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                filename = temp_file.name
                temp_file.close()
                write(filename, fs, audio_data)

                try:
                    with sr.AudioFile(filename) as source:
                        recorded_audio = recognizer.record(source)
                    command = recognizer.recognize_google(
                        recorded_audio,
                        language=LANGUAGE
                    ).lower()
                    if WAKE_WORD in command:
                        clean_command = command.replace(WAKE_WORD, "").strip()
                        speak("please wait for results.")
                        return clean_command
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    print("Speech service unavailable")
                finally:
                    try:
                        os.remove(filename)
                    except OSError:
                        pass

                chunks = []
                speech_started = False
                silence_counter = 0
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        stream.stop()
        stream.close()
# -------------------------------------------------------------------------------------------


def close(site):
    import time
    import pyautogui
    time.sleep(1)
    speak(f"closing {site}.")
    pyautogui.hotkey("ctrl", "shift", "a")
    time.sleep(1)
    pyautogui.write(site)
    time.sleep(1)
    pyautogui.press("enter")
    time.sleep(1)
    pyautogui.hotkey("ctrl", "w")
# ----------------------------------------------------------------------------------------------------------------


def search(topic):
    from google import genai
    from google.genai.errors import ClientError
    from jarvis_requirements import GEMINI_API_KEY_ENV_VAR, GEMINI_MODEL

    api_key = os.getenv(GEMINI_API_KEY_ENV_VAR)
    if not api_key:
        return "I can't reach the search service because no Gemini API key is configured."

    client = genai.Client(api_key=api_key)

    SYSTEM_PROMPT = """
    You are Jarvis, an advanced AI assistant.
    Rules:
    - Keep answers clear and concise
    - Give direct answers
    - Give answers in 2-3 lines only
    - Give answers only using complete words.
    - Do not use symbols or brachets.
    -you are created by shourya jain.
    """
    prompt = f'''{SYSTEM_PROMPT}
    user:{topic}
    '''

    answer = "Sorry, I couldn't get an answer right now."
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt)
        answer = response.text
    except ClientError:
        answer = "A.P.I requests reached its limits"
    except Exception as e:
        print(e)
    return answer
# --------------------------------------------------------------------------------------------------


def play(name):
    import subprocess
    import yt_dlp
    from jarvis_requirements import VLC_PATH

    ydl_opts = {
        "format": "best[height<=1080]",
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{name}", download=False)
            entries = info.get("entries", [])
            if not entries:
                speak("No video found")
                return

            video = entries[0]
            url = video.get("url")
            if not url and "formats" in video:
                for f in reversed(video["formats"]):
                    if f.get("url") and f.get("vcodec") != "none":
                        url = f["url"]
                        break

            if not url:
                speak("No playable URL found")
                return

            print("Playing:", video["title"])

            if not os.path.exists(VLC_PATH):
                print("VLC not found at", VLC_PATH)
                return

            process = subprocess.Popen(
                [
                    VLC_PATH,
                    "--fullscreen",
                    "--qt-minimal-view",
                    "--no-video-title-show",
                    "--no-embedded-video",
                    "--network-caching=1000",
                    "--volume=512",
                    "--gain=8.0",
                    "--mmdevice-volume=1.0",
                    "--audio-filter=normvol",      
                    "--norm-max-level=2.0"
                    "--mouse-hide-timeout=2",
                    "--play-and-exit",
                    url
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            print("Playing Song/video.....")
            # process.wait()
            # speak("Playback Ended")
    except Exception as e:
        print("Error:", e)
# ---------------------------------------------------------------------------------------------------


def _resize_window(command, keywords, action_name, action_fn):
    """Shared helper for the minimize/maximize commands."""
    import pygetwindow as gw

    window_query = command
    for kw in keywords:
        window_query = window_query.replace(kw, "")
    window_query = window_query.strip()

    matches = [
        w for w in gw.getAllWindows()
        if w.title and window_query.lower() in w.title.lower()
    ]
    if matches:
        action_fn(matches[0])
        speak(f"{action_name} {window_query}")
    else:
        speak("No matching window found")
# ---------------------------------------------------------------------------------------------------


def execute(command):
    import datetime

    command = command.lower().strip().replace("please", "").replace("can you", "")

    if "play" in command:
        song = command.replace("play", "").strip()
        if song:
            speak(f"Playing {song}")
            play(song)
    
    elif "time" in command and "right now" in command :
        current_t = datetime.datetime.now()
        speak(current_t.strftime("%I:%M %p"))
    
    elif "date" in command or "today" in command :
        speak(f"{datetime.date.today()}")

    elif "open" in command:
        import webbrowser
        site_name = command.replace("open", "").replace(" ", "").strip()
        site = site_name if ".com" in site_name else f"{site_name}.com"
        if not site.startswith("https://"):
            site = "https://" + site
        speak(f"Opening {site_name}")
        webbrowser.open(site)

    elif "close" in command:
        app = command.replace("close", "").strip()
        if app:
            close(app)

    elif "minimize" in command or "minimise" in command:
        _resize_window(
            command, ["minimize", "minimise"], "Minimizing",
            lambda w: w.minimize()
        )

    elif "maximize" in command or "maximise" in command:
        _resize_window(
            command, ["maximize", "maximise"], "Maximizing",
            lambda w: w.maximize()
        )

    elif ("shutdown pc" in command) or ("shut down pc" in command):
        speak("Shutting down PC")
        os.system("shutdown /s /t 0")

    elif "sleep" in command and "pc" in command:
        speak("Activating sleep mode")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    elif "exit" in command or "stop" in command or "shut down" in command or "shutdown" in command:
        speak("jarvis deactivated")
        return False

    else:
        from jarvis_requirements import WAKE_WORD
        topic = command.replace(WAKE_WORD, "").strip()
        if topic:
            result = search(topic)
            print("Question:", topic)
            print("Answer:", end="")
            speak(result)

    return True
#--------------------------------------------------------------------------------------------------------------


def run_jarvis():
    wish_user()

    while True:
        co = listen()

        if co:

            co = co.lower()
            commands = co.replace(" then ", " and ").replace(",", " and ").split(" and ")

            for command in commands:
                command = command.strip()
                if command:
                    status = execute(command)
                    if status is False:
                        return
# -------------------------------------------------------------------------------------------------------------


def add_to_registry_startup():
    import winreg
    from jarvis_requirements import PYTHONW_PATH

    path = os.path.abspath(__file__)

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(
            key,
            "Jarvis",
            0,
            winreg.REG_SZ,
            f'"{PYTHONW_PATH}" "{path}"'
        )
        winreg.CloseKey(key)
    except OSError as e:
        print("Could not register startup entry:", e)
#---------------------------------------------------------------------------------------------------------------


def remove_from_registry_startup(): 
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE
    )
    winreg.DeleteValue(key, "Jarvis")
    winreg.CloseKey(key)
#--------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    run_jarvis()
# -------------------------------------------------------------------------------------------------