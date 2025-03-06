import tkinter as tk

class SendButton(tk.Button):
    def __init__(self, parent, entry_box, chat_history):
        super().__init__(parent, text="Send", font=("Arial", 12), command=self.send_message)
        self.entry_box = entry_box
        self.chat_history = chat_history
        parent.bind("<<SendMessage>>", lambda e: self.send_message())

    def send_message(self):
        message = self.entry_box.get()
        if message.strip():
            self.chat_history.append_message("You: " + message)
            self.entry_box.delete(0, tk.END)
