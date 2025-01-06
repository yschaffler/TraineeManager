import base64
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import os
import json
import requests
from datetime import datetime
import subprocess

class ScreenshotManager:
    def __init__(self, root, base_folder, training_id, api_base_url, on_close_callback=None):
        self.root = root
        self.base_folder = base_folder
        self.training_id = training_id
        self.api_base_url = api_base_url
        self.screenshot_folder = os.path.join(base_folder, "screenshots")
        self.comments_file = os.path.join(base_folder, "comments.json")
        self.screenshots = []
        self.comments = {}
        self.on_close_callback = on_close_callback
        self.debrief_active = False
        self.last_screenshot_path = None
        self.double_click_detected = False
        
        os.makedirs(self.screenshot_folder, exist_ok=True)

        self.load_screenshots()
        self.load_comments()

        self.create_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.bind("<Control-b>", lambda event: self.add_comment_to_last_screenshot())

    def load_screenshots(self):
        self.screenshots = [
            os.path.join(self.screenshot_folder, f)
            for f in os.listdir(self.screenshot_folder)
            if f.endswith(".png")
        ]
        if self.screenshots:
            self.last_screenshot_path = max(self.screenshots, key=os.path.getctime)

    def load_comments(self):
        if os.path.exists(self.comments_file):
            with open(self.comments_file, "r") as f:
                self.comments = json.load(f)
        else:
            self.comments = {"comments": {}, "besprochen": [], "live": ""}

    def save_comments(self):
        with open(self.comments_file, "w") as f:
            json.dump(self.comments, f, indent=4)

    def create_gui(self):
        # Info-Leiste
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(fill="x", pady=5)

        self.info_label = tk.Label(
            self.info_frame,
            text=f"Training ID: {self.training_id} | Screenshots: {len(self.screenshots)}",
            font=("Arial", 12, "bold"),
        )
        self.info_label.pack()

        self.debrief_button = tk.Button(
            self.info_frame, text="Debrief starten", command=self.toggle_debrief
        )
        self.debrief_button.pack(pady=5)

        self.refresh_button = tk.Button(
            self.info_frame, text="Refresh", command=self.refresh
        )
        self.refresh_button.pack(pady=5)

        # Scrollbarer Bereich
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas)

        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.display_screenshots()

    def display_screenshots(self):
        # Vorhandene Widgets löschen
        for widget in self.frame.winfo_children():
            widget.destroy()

        # Info-Leiste aktualisieren
        self.info_label.config(
            text=f"Training ID: {self.training_id} | Screenshots: {len(self.screenshots)}"
        )

        # Liste der besprochenen Screenshots
        besprochen = set(self.comments.get("besprochen", []))

        # Screenshots anzeigen
        for idx, screenshot_path in enumerate(self.screenshots):
            try:
                # Screenshot laden
                image = Image.open(screenshot_path)
                image.thumbnail((150, 150))
                photo = ImageTk.PhotoImage(image)

                # Grid-Position berechnen
                row = idx // 3 * 4  # Jede Gruppe von 3 Bildern benötigt 4 Zeilen
                col = idx % 3

                filename = os.path.basename(screenshot_path)
                is_besprochen = filename in besprochen

                # Timestamp aus dem Dateinamen extrahieren
                filename_without_ext = os.path.splitext(filename)[0]
                timestamp = filename_without_ext.split("_")[1] + "_" + filename_without_ext.split("_")[2]
                timestamp_str = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%d.%m.%Y %H:%M:%S")

                # Screenshot anzeigen
                img_label = tk.Label(self.frame, image=photo)
                img_label.image = photo
                img_label.grid(row=row, column=col, padx=5, pady=5)

                # Timestamp anzeigen
                timestamp_label = tk.Label(
                    self.frame,
                    text=timestamp_str,
                    font=("Arial", 9, "bold"),
                    justify="center",
                )
                timestamp_label.grid(row=row + 1, column=col, padx=5, pady=2)

                # Status anzeigen (falls vorhanden)
                if is_besprochen:
                    status_label = tk.Label(
                        self.frame,
                        text="Besprochen",
                        font=("Arial", 9),
                        fg="green",
                        justify="center",
                    )
                    status_label.grid(row=row + 2, column=col, padx=5, pady=2)

                # Bemerkung anzeigen (falls vorhanden)
                comment = self.comments.get("comments", {}).get(filename, "")
                if comment:
                    comment_label = tk.Label(
                        self.frame,
                        text=comment,
                        font=("Arial", 8),
                        justify="center",
                    )
                    comment_label.grid(row=row + 3, column=col, padx=5, pady=2)

                # Kontextmenü für Aktionen
                context_menu = tk.Menu(self.root, tearoff=0)
                if self.debrief_active:
                    context_menu.add_command(label="Manuell hochladen", command=lambda path=screenshot_path: self.upload_screenshot(path))
                    context_menu.add_command(label="Live schalten", command=lambda path=screenshot_path: self.sync_screenshot(path))

                context_menu.add_command(label="Bemerkung bearbeiten", command=lambda path=screenshot_path: self.add_comment(path))
                context_menu.add_command(label="Screenshot löschen", command=lambda path=screenshot_path: self.delete_screenshot(path))

                def show_context_menu(event, menu=context_menu):
                    menu.post(event.x_root, event.y_root)

                # Klick-Events binden
                img_label.bind("<Button-1>", lambda e, path=screenshot_path: self.on_click(path))
                img_label.bind("<Double-1>", lambda e, path=screenshot_path: self.on_double_click(path))
                img_label.bind("<Button-3>", show_context_menu)

            except Exception as e:
                print(f"Error loading image {screenshot_path}: {e}")



    def on_click(self, path):
        """
        Führt beim Einzelklick die Paint-Funktion aus, wenn kein Doppelklick erkannt wurde.
        """
        # Wenn in kurzer Zeit kein Doppelklick ausgelöst wird, führe den Einzelklick aus
        self.root.after(200, lambda: self.open_with_paint(path) if not self.double_click_detected else None)

    def on_double_click(self, path):
        """
        Führt beim Doppelklick die Kommentar-Funktion aus.
        """
        self.double_click_detected = True  # Doppelklick erkannt
        self.add_comment(path)
        # Zurücksetzen des Doppelklick-Status nach kurzer Zeit
        self.root.after(300, lambda: setattr(self, "double_click_detected", False))
    def add_comment(self, screenshot_path):
        filename = os.path.basename(screenshot_path)
        current_comment = self.comments.get("comments", {}).get(filename, "")

        comment = simpledialog.askstring(
            "Bemerkung bearbeiten",
            f"Bemerkung für {filename} eingeben:",
            initialvalue=current_comment,
        )
        if comment is not None:  # Nicht abbrechen
            if "comments" not in self.comments:
                self.comments["comments"] = {}

            # Bemerkung speichern
            self.comments["comments"][filename] = comment
            self.save_comments()
            self.refresh()

    def add_comment_to_last_screenshot(self):
        if not self.last_screenshot_path:
            messagebox.showinfo("Keine Screenshots", "Es wurde noch kein Screenshot gemacht.")
            return

        self.add_comment(self.last_screenshot_path)

    def delete_screenshot(self, screenshot_path):
        try:
            os.remove(screenshot_path)
            print(f"Screenshot gelöscht: {screenshot_path}")
            self.refresh()
        except Exception as e:
            print(f"Fehler beim Löschen des Screenshots: {e}")

    def open_with_paint(self, screenshot_path):
        """
        Öffnet den Screenshot in Paint zur Bearbeitung.
        """
        try:
            # Paint starten mit dem Screenshot
            subprocess.run(["mspaint", screenshot_path], check=True)
            print(f"Screenshot wurde in Paint geöffnet: {screenshot_path}")
            self.refresh()  # Nach der Bearbeitung aktualisieren
        except FileNotFoundError:
            messagebox.showerror("Fehler", "Paint wurde nicht gefunden.")
        except Exception as e:
            print(f"Fehler beim Öffnen von Paint: {e}")
            messagebox.showerror("Fehler", "Paint konnte nicht gestartet werden.")
        
    def refresh(self):
        self.load_screenshots()
        self.display_screenshots()
        
    def toggle_debrief(self):
        if self.debrief_active:
            self.end_debrief()
        else:
            self.start_debrief()

    def start_debrief(self):
        total_screenshots = len(self.screenshots)
        if total_screenshots == 0:
            messagebox.showinfo("Keine Screenshots", "Es gibt keine Screenshots zum Hochladen.")
            return
        self.debrief_active = True
        self.debrief_button.config(text="Debrief beenden")
        
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Debrief Fortschritt")

        progress_label = tk.Label(progress_window, text="Hochladen...")
        progress_label.pack(pady=10)

        progress_bar = tk.Scale(progress_window, from_=0, to=total_screenshots, orient="horizontal", length=300)
        progress_bar.pack(pady=10)

        link_label = tk.Label(progress_window, text="", font=("Arial", 10, "bold"))
        link_label.pack(pady=10)

        def upload_all():
            for idx, screenshot_path in enumerate(self.screenshots):
                success = self.upload_screenshot(screenshot_path)
                if success:
                    progress_bar.set(idx + 1)
                else:
                    messagebox.showerror("Upload-Fehler", f"Fehler beim Hochladen von {os.path.basename(screenshot_path)}")

            progress_label.config(text="Hochladen abgeschlossen!")
            training_link = f"http://localhost:3000/vatsim/traineemanager/training/{self.training_id}"
            link_label.config(text=f"Link: {training_link}")

            def copy_link():
                self.root.clipboard_clear()
                self.root.clipboard_append(training_link)
                self.root.update()
                messagebox.showinfo("Link kopiert", "Der Link wurde in die Zwischenablage kopiert.")

            copy_button = tk.Button(progress_window, text="Link kopieren", command=copy_link)
            copy_button.pack(pady=5)
            
        self.root.after(100, upload_all)
        self.refresh()

    def end_debrief(self):
        self.debrief_active = False
        self.debrief_button.config(text="Debrief starten")

        # Signal senden, dass das Debrief beendet ist
        url = f"{self.api_base_url}/api/Vatsim/traineemanager/training/{self.training_id}/sync"
        try:
            response = requests.post(url, json={"current_screenshot": "DEBRIEFENDE"})
            if response.status_code == 200:
                print("Debrief beendet, Signal gesendet.")
            else:
                print(f"Fehler beim Senden des Debrief-Ende-Signals: {response.status_code}")
        except Exception as e:
            print(f"Fehler beim Senden des Debrief-Ende-Signals: {e}")

        self.refresh()
         
    def upload_screenshot(self, screenshot_path):
        url = f"{self.api_base_url}/api/Vatsim/traineemanager/training/{self.training_id}/upload"
        filename = os.path.basename(screenshot_path)

        try:
            with open(screenshot_path, "rb") as file:
                encoded_file = base64.b64encode(file.read()).decode("utf-8")
            response = requests.post(url, json={"file": encoded_file, "filename": filename})

            if response.status_code == 200:
                print(f"Screenshot hochgeladen: {filename}")
                return True
            else:
                print(f"Fehler beim Hochladen von {filename}: {response.status_code}")
                return False
        except Exception as e:
            print(f"Fehler beim Hochladen von {filename}: {e}")
            return False

    def sync_screenshot(self, screenshot_path):
        url = f"{self.api_base_url}/api/Vatsim/traineemanager/training/{self.training_id}/sync"
        filename = os.path.basename(screenshot_path)

        try:
            response = requests.post(url, json={"current_screenshot": filename})

            if response.status_code == 200:
                print(f"Screenshot live geschaltet: {filename}")
                self.comments["live"] = filename
                if filename not in self.comments.get("besprochen", []):
                    self.comments["besprochen"] = self.comments.get("besprochen", []) + [filename]
                self.save_comments()
                self.refresh()
            else:
                print(f"Fehler beim Live-Schalten von {filename}: {response.status_code}")
        except Exception as e:
            print(f"Fehler beim Live-Schalten von {filename}: {e}")

    def on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.root.destroy()
