"""Optional Tk push-to-talk panel. Audio/model work never runs on the UI thread."""
import queue
import threading


def run_panel(model, config, service, no_speak=False):
    import tkinter as tk
    window = tk.Tk()
    window.title('JARVIS voice control')
    window.geometry('460x200')
    updates = queue.Queue()
    stop = threading.Event()
    busy = False
    closing = False
    phase = tk.StringVar(value='Ready. Click Speak, then say “Jarvis, show Japan”.')
    tk.Label(window, textvariable=phase, wraplength=420, pady=20).pack()

    def worker():
        try:
            audio = service.record(config['record_seconds'], stop=stop,
                                   device=config.get('input_device'),
                                   microphone_allowed=config.get('microphone_enabled', False))
            updates.put('Transcribing locally…')
            service.status('transcribing')
            try:
                words = service.transcribe(model, audio)
            finally:
                del audio
            if not closing and words:
                service.handle(words, config, no_speak)
            updates.put('Ready. Click Speak for another command.')
        except Exception as exc:
            updates.put('Voice error: ' + type(exc).__name__)
            service.status('error', error=str(exc))
        finally:
            if closing:
                service.status('idle')
            updates.put(None)

    def speak():
        nonlocal busy
        if busy:
            stop.set()
            button.config(state='disabled')
            phase.set('Finishing capture…')
            return
        busy = True
        stop.clear()
        phase.set('Listening locally. Click Stop when finished.')
        button.config(text='Stop recording')
        service.status('listening')
        threading.Thread(target=worker, daemon=False).start()

    button = tk.Button(window, text='Speak', command=speak, width=24, height=2)
    button.pack()
    tk.Label(window, text='No always-on recording. Clips stay in memory.', pady=12).pack()

    def close():
        nonlocal closing
        closing = True
        stop.set()
        button.config(state='disabled')
        phase.set('Stopping…')
        if not busy:
            window.destroy()

    def refresh():
        nonlocal busy
        while True:
            try:
                message = updates.get_nowait()
            except queue.Empty:
                break
            if message is None:
                busy = False
                button.config(text='Speak', state='normal')
            elif not closing:
                phase.set(message)
                if message.startswith('Transcribing'):
                    button.config(state='disabled')
        if closing and not busy:
            window.destroy()
        else:
            window.after(50, refresh)

    window.protocol('WM_DELETE_WINDOW', close)
    window.after(50, refresh)
    window.mainloop()
