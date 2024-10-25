import tkinter as tk
import asyncio
from ui.dashboard import Dashboard
from components.ib_connection import connect_ib

async def init_app(root, loop):
    try:
        connection_successful = await connect_ib()
        if not connection_successful:
            error_label = tk.Label(root, text="Failed to connect to IBKR. Please check your connection and try again.", fg="red", wraplength=300)
            error_label.pack(pady=20)
            return False
        
        dashboard = Dashboard(root, loop)
        dashboard.pack(fill=tk.BOTH, expand=True)
        return True
        
    except Exception as e:
        error_label = tk.Label(root, text=f"Error initializing application: {str(e)}", fg="red", wraplength=300)
        error_label.pack(pady=20)
        return False

def main():
    root = tk.Tk()
    root.title("Auto Hedger and IV/RV Calculator")

    # Create and set the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize the application
    init_success = loop.run_until_complete(init_app(root, loop))
    
    if init_success:
        # Set up the event loop to run in the background
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        import threading
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Handle window closing
        def on_closing():
            loop.stop()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    else:
        # If initialization failed, close after a delay
        root.after(5000, root.destroy)
        root.mainloop()

if __name__ == '__main__':
    main()
