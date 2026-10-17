import jarvis_backend as jr, os
from jarvis_requirements import PYTHONW_PATH

def add_to_registry_startup():
    import winreg
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

if __name__ == "__main__" : 
    add_to_registry_startup()
    jr.run_jarvis()

'''
Wake Word : "jarvis"

commands :-

    1. "jarvis minimize << window name >>" : minimize that perticular window.
    
    2. "jarvis maximize << window name >>" : maximize that perticular window.
    
    3. "jarvis open << website name >>" : open website in chrome.

    4. "jarvis shutdown/stop/exit" : deactivate jarvis.

    5. "jarvis shutdown pc" : shutdown's pc.

    6. "jarvis sleep pc" : activate pc's sleep made.

    7. "jarvis time right now" : tell's current time.

    8. "jarvis tell date today" : tell's date.

    9. jarvis << question >> : Give answer of asked question.

    10. jarvis play << song/video title >> : Play audio and video in vlc.

'''