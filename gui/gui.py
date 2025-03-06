import tkinter as tk
from chat_entry_box import ChatEntryBox
from chat_history import ChatHistory
from send_button import SendButton
from pause_button import PauseButton

class AutomoyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Automoy - AI Chat Interface")
        self.root.geometry("600x500")

        # Chat History Box
        self.chat_history = ChatHistory(self.root)
        self.chat_history.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # Entry and Buttons Container
        self.input_frame = tk.Frame(self.root)
        self.input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Chat Entry Box
        self.chat_entry = ChatEntryBox(self.input_frame)
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Send Button
        self.send_button = SendButton(self.input_frame, self.chat_entry, self.chat_history)
        self.send_button.pack(side=tk.LEFT, padx=5)

        # Pause Button
        self.pause_button = PauseButton(self.input_frame)
        self.pause_button.pack(side=tk.LEFT)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutomoyGUI(root)
    app.run()
