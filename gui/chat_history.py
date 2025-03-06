import tkinter as tk
from tkinter import scrolledtext

class ChatHistory(scrolledtext.ScrolledText):
    def __init__(self, parent):
        super().__init__(parent, wrap=tk.WORD, height=20, width=60, font=("Arial", 12))
        self.config(state=tk.DISABLED)

    def append_message(self, message):
        """Adds a message to chat history."""
        self.config(state=tk.NORMAL)
        self.insert(tk.END, message + "\n")
        self.config(state=tk.DISABLED)
        self.yview(tk.END)
