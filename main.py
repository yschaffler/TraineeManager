import os
import sys
import json
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from datetime import datetime
from docx import Document

# watchdog zum Überwachen des Screenshot-Ordners
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Standardpfad für Windows-Screenshots
DEFAULT_SCREENSHOT_FOLDER = os.path.join(
    os.path.expanduser("~"), "Pictures", "Screenshots"
)
# Name der Konfigurationsdatei
CONFIG_FILE = "config.json"


def load_config():
    """
    Lädt die Konfiguration aus config.json (wenn vorhanden).
    Gibt ein Dictionary zurück, z.B. {"trainee_folder": "..."}
    """
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_config(config):
    """
    Speichert das gegebene config-Dict als config.json.
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Fehler beim Speichern der Konfiguration:", e)


class TraineeManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Trainee Manager")
        self.geometry("600x400")

        # 1) Konfiguration laden
        self.config_dict = load_config()
        self.trainee_folder = self.config_dict.get("trainee_folder", "")

        # Falls der gespeicherte Pfad leer ist oder nicht existiert, Dialog anzeigen
        if not self.trainee_folder or not os.path.isdir(self.trainee_folder):
            self.trainee_folder = filedialog.askdirectory(
                title="Bitte den Trainee-Hauptordner auswählen"
            )
            if not self.trainee_folder:
                messagebox.showerror("Abbruch", "Kein Ordner ausgewählt. Das Programm wird beendet.")
                self.destroy()
                return
            # In Konfiguration speichern
            self.config_dict["trainee_folder"] = self.trainee_folder
            save_config(self.config_dict)

        # Trainingsmodus
        self.training_mode_active = False
        self.current_training_folder = None

        # Screenshot-Ordner (Standard: C:\Users\<Name>\Pictures\Screenshots)
        self.screenshot_folder = DEFAULT_SCREENSHOT_FOLDER
        if not os.path.isdir(self.screenshot_folder):
            os.makedirs(self.screenshot_folder, exist_ok=True)

        # GUI-Elemente
        self.create_widgets()
        self.update_trainee_list()

        # 2) Watchdog starten, um Screenshots zu erkennen
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

    # ------------------------------
    # Trainingsmodus
    # ------------------------------
    def start_training_mode(self):
        selected_trainee = self.trainee_listbox.get(tk.ACTIVE)
        if not selected_trainee:
            messagebox.showerror("Fehler", "Bitte wähle zuerst einen Trainee aus.")
            return

        training_name = simpledialog.askstring("Training-Name", "Name des Trainings:")
        if not training_name:
            return

        self.current_training_folder = os.path.join(
            self.trainee_folder, selected_trainee, training_name
        )
        os.makedirs(self.current_training_folder, exist_ok=True)

        self.training_mode_active = True
        self.training_mode_label.config(text="Trainingsmodus aktiv", fg="green")
        self.stop_training_button.config(state=tk.NORMAL)

        self.create_and_open_training_doc(selected_trainee, training_name)

    def stop_training_mode(self):
        self.training_mode_active = False
        self.current_training_folder = None
        self.training_mode_label.config(text="Trainingsmodus nicht aktiv", fg="red")
        self.stop_training_button.config(state=tk.DISABLED)

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

    # ------------------------------
    # Watchdog - Ordnerüberwachung
    # ------------------------------
    def start_observer(self):
        """Startet den Watchdog-Observer auf den Screenshot-Ordner."""
        if not os.path.isdir(self.screenshot_folder):
            return
        event_handler = ScreenshotFolderHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.screenshot_folder, recursive=False)
        self.observer.start()

    def on_new_screenshot_detected(self, file_path):
        """
        Wird aufgerufen, wenn im Screenshot-Ordner eine neue .png-Datei auftaucht.
        Falls Trainingsmodus aktiv -> Bemerkungspopup, Datei verschieben + umbenennen.
        """
        if not self.training_mode_active or not self.current_training_folder:
            # Nicht im Trainingsmodus -> nicht verschieben
            return

        # Popup im Haupt-Thread
        self.after(0, lambda: self.handle_screenshot_popup(file_path))

    def handle_screenshot_popup(self, screenshot_path):
        """Zeigt ein Topmost-Popup an und verschiebt danach die Screenshotdatei."""
        if not os.path.exists(screenshot_path):
            return  # Datei nicht mehr da?

        popup = tk.Toplevel(self)
        popup.title("Bemerkung für Screenshot")
        popup.geometry("300x100")
        popup.resizable(False, False)

        # Immer im Vordergrund
        popup.lift()
        popup.attributes("-topmost", True)
        popup.focus_force()
        popup.grab_set()
        popup.after_idle(popup.focus_force)

  

        lbl = tk.Label(popup, text="Bemerkung (optional):")
        lbl.pack(pady=5)

        entry = tk.Entry(popup, width=40)
        entry.pack(pady=5)
        entry.focus()

        def on_enter(event=None):
            note = entry.get().strip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"screenshot_{timestamp}"
            if note:
                base_name += f"_{note}"
            new_filename = base_name + ".png"

            screenshots_subfolder = os.path.join(self.current_training_folder, "screenshots")
            os.makedirs(screenshots_subfolder, exist_ok=True)
            destination_path = os.path.join(screenshots_subfolder, new_filename)

            try:
                shutil.move(screenshot_path, destination_path)
            except Exception as e:
                messagebox.showerror("Fehler beim Verschieben", str(e))
            popup.destroy()

        entry.bind("<Return>", on_enter)

    def on_closing(self):
        """Beim Beenden der App: Watchdog sauber stoppen und config speichern."""
        # Watchdog stoppen
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Konfiguration (aktuelle trainee_folder) nochmals speichern
        self.config_dict["trainee_folder"] = self.trainee_folder
        save_config(self.config_dict)

        self.destroy()


class ScreenshotFolderHandler(FileSystemEventHandler):
    """
    Watchdog-Event-Handler. Wenn eine neue Datei .png auftaucht,
    rufen wir app.on_new_screenshot_detected(...) auf.
    """
    def __init__(self, app):
        super().__init__()
        self.app = app

    def on_created(self, event):
        if not event.is_directory:
            _, ext = os.path.splitext(event.src_path)
            if ext.lower() == ".png":
                self.app.on_new_screenshot_detected(event.src_path)


if __name__ == "__main__":
    app = TraineeManagerApp()
    # Wenn das Fenster geschlossen wird, rufe `on_closing` auf.
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
