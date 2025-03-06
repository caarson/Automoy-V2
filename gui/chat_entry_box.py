import tkinter as tk

class ChatEntryBox(tk.Entry):
    def __init__(self, parent):
        super().__init__(parent)
        self.config(width=50, font=("Arial", 12))
        self.bind("<Return>", self.send_message)

    def send_message(self, event=None):
        """Triggers sending message (handled in `send_button.py`)."""
        self.master.event_generate("<<SendMessage>>")
