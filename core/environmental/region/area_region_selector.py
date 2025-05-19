import tkinter as tk
import threading

def select_area(callback):
    """
    Opens a selection overlay to allow the user to select a region on the screen.
    Once the region is selected, the callback is called with the coordinates.
    """
    overlay = tk.Toplevel()
    overlay.attributes('-topmost', True)
    overlay.attributes('-alpha', 0.3)
    overlay.overrideredirect(True)

    sw = overlay.winfo_screenwidth()
    sh = overlay.winfo_screenheight()
    overlay.geometry(f"{sw}x{sh}+0+0")

    canvas = tk.Canvas(overlay, cursor="cross", bd=0, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    rect = None

    def on_press(event):
        nonlocal rect
        rect = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=4)

    def on_drag(event):
        if rect:
            x1, y1, _, _ = canvas.coords(rect)
            canvas.coords(rect, x1, y1, event.x, event.y)

    def on_release(event):
        coords = canvas.coords(rect)
        overlay.destroy()  # Close the selection overlay
        callback(coords)  # Pass selected coordinates

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

    overlay.mainloop()  # Main GUI loop for selection

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

    outline_canvas = tk.Canvas(outline_window, bd=0, highlightthickness=0)
    outline_canvas.pack(fill=tk.BOTH, expand=True)

    outline_rect = outline_canvas.create_rectangle(0, 0, width, height, outline='red', width=4)

    def close_outline():
        """
        Closes the outline window.
        """
        print("Closing the outline window...")
        outline_canvas.itemconfig(outline_rect, state='hidden')
        close_btn.place_forget()  # Hide the button
        outline_window.destroy()  # Close the outline window
        print("Outline window closed.")
        root.quit()  # Tells Tk to stop the main event loop immediately!
        

    close_btn = tk.Button(outline_window, text="Close", command=close_outline, bg='white', relief='flat')
    close_btn.place(relx=0.5, rely=0.5, anchor='center')

    def toggle_visibility_for_screenshot():
        """
        Toggles the visibility of the outline and close button for a screenshot.
        """
        print("Hiding outline and close button in 3 seconds...")
        outline_window.after(3000, lambda: (
            print("Hiding now..."),
            outline_canvas.itemconfig(outline_rect, state='hidden'),
            close_btn.place_forget()
        ))

        outline_window.after(4000, lambda: (
            print("Restoring outline and close button..."),
            outline_canvas.itemconfig(outline_rect, state='normal'),
            close_btn.place(relx=0.5, rely=0.5, anchor='center')
        ))

    return toggle_visibility_for_screenshot

# Testable main block
if __name__ == "__main__":
    print("Starting region selection test...")

    def handle_selection(coords):
        print(f"Selected region coordinates: {coords}")
        toggle_visibility = create_outline_window(coords)
        print("Visibility test: hiding outline for a second after 3 seconds.")
        toggle_visibility()  # Toggle visibility for testing

    root = tk.Tk()
    root.withdraw()  # Hide the main window
    select_area(handle_selection)  # Opens the Toplevel selection window

    print("Root window cleanup complete.")
    root.quit()     # Cleanly exits the mainloop
    root.destroy()  # Destroys the root window

