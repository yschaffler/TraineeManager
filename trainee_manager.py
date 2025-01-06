import os
import shutil
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from screenshot_manager import ScreenshotManager
from utils import load_config, save_config
from docx import Document
import time
import uuid

DEFAULT_SCREENSHOT_FOLDER = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")


class TraineeManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trainee Manager")
        self.geometry("600x400")

        self.config_dict = load_config()
        self.trainee_folder = self.config_dict.get("trainee_folder", "")
        if not self.trainee_folder or not os.path.isdir(self.trainee_folder):
            self.trainee_folder = filedialog.askdirectory(title="Bitte den Trainee-Hauptordner auswählen")
            if not self.trainee_folder:
                messagebox.showerror("Abbruch", "Kein Ordner ausgewählt. Das Programm wird beendet.")
                self.destroy()
                return
            self.config_dict["trainee_folder"] = self.trainee_folder
            save_config(self.config_dict)

        self.training_mode_active = False
        self.current_training_folder = None
        self.screenshot_manager = None
        self.current_training_id = None
        self.screenshot_folder = DEFAULT_SCREENSHOT_FOLDER
        os.makedirs(self.screenshot_folder, exist_ok=True)

        self.create_widgets()
        self.update_trainee_list()

        self.observer = None
        self.start_observer()

    def create_widgets(self):
        lbl = tk.Label(self, text="Trainees:")
        lbl.pack(pady=(10, 0))

        self.trainee_listbox = tk.Listbox(self, height=10, width=50)
        self.trainee_listbox.pack(pady=5)

        btn_add_trainee = tk.Button(self, text="Neuen Trainee anlegen", command=self.add_trainee)
        btn_add_trainee.pack(pady=5)

        btn_start_training = tk.Button(self, text="Neues Training anlegen", command=self.start_training_mode)
        btn_start_training.pack(pady=5)

        self.training_mode_label = tk.Label(self, text="Trainingsmodus nicht aktiv", fg="red")
        self.training_mode_label.pack(pady=5)

        self.stop_training_button = tk.Button(
            self, text="Training beenden", command=self.stop_training_mode, state=tk.DISABLED
        )
        self.stop_training_button.pack(pady=5)

    # Trainingsmodus und Screenshots
    def start_training_mode(self):
        selected_trainee = self.trainee_listbox.get(tk.ACTIVE)
        if not selected_trainee:
            messagebox.showerror("Fehler", "Bitte wähle zuerst einen Trainee aus.")
            return

        training_name = simpledialog.askstring("Training-Name", "Name des Trainings:")
        if not training_name:
            return

        self.current_training_id = str(uuid.uuid4())

        self.current_training_folder = os.path.join(self.trainee_folder, selected_trainee, training_name)
        os.makedirs(self.current_training_folder, exist_ok=True)

        self.training_mode_active = True
        self.training_mode_label.config(text="Trainingsmodus aktiv", fg="green")
        self.stop_training_button.config(state=tk.NORMAL)
        #self.create_and_open_training_doc(selected_trainee, training_name)
        self.manage_screenshot_manager()
        self.start_timer()

    def stop_training_mode(self):
        self.training_mode_active = False
        self.current_training_folder = None
        self.training_mode_label.config(text="Trainingsmodus nicht aktiv", fg="red")
        self.stop_training_button.config(state=tk.DISABLED)
        self.stop_timer()

    def create_and_open_training_doc(self, trainee_folder_name, training_name):
        template_path = os.path.join("templates", "training_template.docx")
        if not os.path.exists(template_path):
            messagebox.showerror("Fehler", f"Template '{template_path}' nicht gefunden.")
            return

        doc = Document(template_path)
        for para in doc.paragraphs:
            if "{Name}" in para.text:
                para.text = para.text.replace("{Name}", trainee_folder_name)
            if "{Training}" in para.text:
                para.text = para.text.replace("{Training}", training_name)
            if "{Date}" in para.text:
                para.text = para.text.replace("{Date}", datetime.now().strftime("%Y-%m-%d"))

        doc_filename = f"{training_name}_training_notes.docx"
        doc_path = os.path.join(self.current_training_folder, doc_filename)
        doc.save(doc_path)
        os.startfile(doc_path)  # Öffnet in Word (Windows)

    def on_new_screenshot_detected(self, file_path):
        if not self.training_mode_active or not self.current_training_folder:
            return

        print(file_path)
        self.move_screenshot_to_training_folder(file_path)
        self.after(0, self.manage_screenshot_manager)

    def move_screenshot_to_training_folder(self, file_path):
        screenshots_subfolder = os.path.join(self.current_training_folder, "screenshots")
        os.makedirs(screenshots_subfolder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"screenshot_{timestamp}.png"
        destination_path = os.path.join(screenshots_subfolder, new_filename)

        time.sleep(0.5)
        
        try:
            shutil.move(file_path, destination_path)
        except Exception as e:
            print(f"Fehler beim Verschieben des Screenshots: {e}")

    def manage_screenshot_manager(self):
        if not self.screenshot_manager:
            manager_window = tk.Toplevel(self)
            self.screenshot_manager = ScreenshotManager(
                root=manager_window,
                base_folder=self.current_training_folder,
                training_id=self.current_training_id,  
                api_base_url="http://localhost:3000",
                on_close_callback=self.on_manager_close
            )
        else:
            self.screenshot_manager.refresh()

    def on_manager_close(self):
        self.screenshot_manager = None

    # ------------------------------
    # Timer
    # ------------------------------
    def start_timer(self):
        self.training_start_time = time.time()
        print("Stoppuhr gestartet.")

    def stop_timer(self):
        if not hasattr(self, "training_start_time"):
            print("Die Stoppuhr wurde nicht gestartet.")
            return

        duration = time.time() - self.training_start_time
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        messagebox.showinfo("Trainingsdauer", f"Das Training dauerte: {duration_str}")
        del self.training_start_time
    # ------------------------------
    # Trainees
    # ------------------------------
    def update_trainee_list(self):
        self.trainee_listbox.delete(0, tk.END)
        if os.path.isdir(self.trainee_folder):
            for folder_name in os.listdir(self.trainee_folder):
                full_path = os.path.join(self.trainee_folder, folder_name)
                if os.path.isdir(full_path):
                    self.trainee_listbox.insert(tk.END, folder_name)
    
    def add_trainee(self):
        trainee_name = simpledialog.askstring("Trainee-Name", "Name des Trainees:")
        if not trainee_name:
            return

        trainee_id = simpledialog.askstring("Trainee-ID", f"ID für {trainee_name} eingeben:")
        if not trainee_id:
            return

        folder_name = f"{trainee_name}-{trainee_id}"
        path = os.path.join(self.trainee_folder, folder_name)
        if os.path.exists(path):
            messagebox.showerror("Fehler", f"Trainee-Ordner '{folder_name}' existiert bereits.")
            return

        try:
            os.makedirs(path)
            messagebox.showinfo("Erfolg", f"Trainee {folder_name} wurde angelegt.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Anlegen des Ordners:\n{e}")
            return

        self.update_trainee_list()

    # Observer
    def start_observer(self):
        if not os.path.isdir(self.screenshot_folder):
            return
        event_handler = ScreenshotFolderHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.screenshot_folder, recursive=False)
        self.observer.start()

    def on_closing(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.config_dict["trainee_folder"] = self.trainee_folder
        save_config(self.config_dict)
        self.destroy()


class ScreenshotFolderHandler(FileSystemEventHandler):
    def __init__(self, app):
        super().__init__()
        self.app = app

    def on_created(self, event):
        if not event.is_directory:
            _, ext = os.path.splitext(event.src_path)
            if ext.lower() == ".png":
                self.app.on_new_screenshot_detected(event.src_path)
