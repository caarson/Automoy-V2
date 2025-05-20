import tkinter as tk
import pygetwindow as gw
import threading

def list_windows():
    return [w for w in gw.getWindowsWithTitle('') if w.title and not w.isMinimized]

def select_window_popup(callback):
    """
    Shows a list of open windows for the user to select.
    Calls the callback with the geometry of the selected window.
    """
    window_selector = tk.Toplevel()
    window_selector.title("Select a Window")
    window_selector.geometry("300x400")
    
    lb = tk.Listbox(window_selector)
    lb.pack(fill=tk.BOTH, expand=True)

    windows = list_windows()
    for w in windows:
        lb.insert(tk.END, w.title)

    def on_select(event):
        index = lb.curselection()
        if not index:
            return
        selected_window = windows[index[0]]
        window_selector.destroy()
        bbox = (selected_window.left, selected_window.top,
                selected_window.right, selected_window.bottom)
        callback(bbox)

    lb.bind("<Double-1>", on_select)

def create_outline_window(coords):
    """
    Creates an outline window at the specified coordinates.
    """
    x1, y1, x2, y2 = map(int, coords)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    x = min(x1, x2)
    y = min(y1, y2)

    outline_window = tk.Toplevel()
    outline_window.geometry(f"{width}x{height}+{x}+{y}")
    outline_window.overrideredirect(True)
    outline_window.attributes('-topmost', True)
    outline_window.attributes('-transparentcolor', outline_window['bg'])

    canvas = tk.Canvas(outline_window, bd=0, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    rect = canvas.create_rectangle(0, 0, width, height, outline='red', width=4)

    def close_outline():
        print("Closing outline window.")
        outline_window.destroy()
        root.quit()

    close_btn = tk.Button(outline_window, text="Close", command=close_outline, bg='white')
    close_btn.place(relx=0.5, rely=0.5, anchor='center')

    def toggle_visibility():
        print("Temporarily hiding outline...")
        outline_window.after(3000, lambda: (
            canvas.itemconfig(rect, state='hidden'),
            close_btn.place_forget()
        ))
        outline_window.after(4000, lambda: (
            canvas.itemconfig(rect, state='normal'),
            close_btn.place(relx=0.5, rely=0.5, anchor='center')
        ))

    return toggle_visibility

# Entry point
if __name__ == "__main__":
    def handle_window_selection(bbox):
        print(f"Selected window box: {bbox}")
        toggle_visibility = create_outline_window(bbox)
        toggle_visibility()

    root = tk.Tk()
    root.withdraw()
    select_window_popup(handle_window_selection)
    root.mainloop()
