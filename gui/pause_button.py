import tkinter as tk

class PauseButton(tk.Button):
    def __init__(self, parent):
        super().__init__(parent, text="Pause", font=("Arial", 12), command=self.pause_ai)
        self.paused = False

    def pause_ai(self):
        self.paused = not self.paused
        self.config(text="Resume" if self.paused else "Pause")
        print(f"AI {'Paused' if self.paused else 'Resumed'}")  # Replace with actual pause logic
