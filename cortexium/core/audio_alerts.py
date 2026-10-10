import queue
import threading
import time

class AudioAlertManager:
    def __init__(self, rate=175, volume=1.0, cooldown_seconds=4):
        self.rate = rate
        self.volume = volume
        self.cooldown_seconds = cooldown_seconds
        
        self.queue = queue.Queue()
        self.last_spoken = {}
        self.muted = False
        
        # Start background daemon worker thread for TTS
        self.worker_thread = threading.Thread(target=self._run_tts, daemon=True)
        self.worker_thread.start()
        
    def speak(self, message: str, priority: str = "normal", cooldown: float = None):
        """
        Submits a message to be spoken.
        If priority is 'critical', queued normal alerts are cleared.
        """
        current_time = time.time()
        last_spoken_time = self.last_spoken.get(message, 0)
        
        cd = cooldown if cooldown is not None else self.cooldown_seconds
        # Check cooldown to prevent frame-rate trigger spamming
        if current_time - last_spoken_time < cd:
            return
            
        self.last_spoken[message] = current_time
        
        if not self.muted:
            print(f"🔊 [TTS Alert] Queueing phrase: '{message}' (Priority: {priority})")
            self.queue.put(message)
        
    def _run_tts(self):
        """
        Worker thread function that processes speech requests via pyttsx3 on Windows.
        """
        while True:
            try:
                msg = self.queue.get()
                if msg is None:
                    break
                    
                if not self.muted:
                    print(f"🔊 [TTS Alert] Speaking: '{msg}'")
                    try:
                        import pythoncom
                        import pyttsx3
                        pythoncom.CoInitialize()
                        engine = pyttsx3.init()
                        engine.setProperty('rate', self.rate)
                        engine.setProperty('volume', self.volume)
                        engine.say(msg)
                        engine.runAndWait()
                        engine.stop()
                        del engine
                        pythoncom.CoUninitialize()
                    except Exception as tts_err:
                        print(f"⚠️ Warning: TTS audio playback failed for '{msg}': {tts_err}")
                        
                self.queue.task_done()
            except Exception as e:
                print(f"⚠️ Warning: Exception in audio thread loop: {e}")
