import tkinter as tk
from trainee_manager import TraineeManagerApp

if __name__ == "__main__":
    app = TraineeManagerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
