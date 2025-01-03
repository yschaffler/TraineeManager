import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import os
import json
from datetime import datetime

class ScreenshotManager:
    def __init__(self, root, base_folder, on_close_callback=None):
        self.root = root
        self.base_folder = base_folder
        self.screenshot_folder = os.path.join(base_folder, "screenshots")
        self.comments_file = os.path.join(base_folder, "comments.json")
        self.screenshots = []
        self.comments = {}
        self.on_close_callback = on_close_callback
        self.last_screenshot_path = None

        # Extrahiere Name des Trainees und Trainingsname aus dem Ordnerpfad
        path_parts = os.path.normpath(base_folder).split(os.sep)
        if len(path_parts) >= 2:
            self.trainee_name = path_parts[-2]
            self.training_name = path_parts[-1]
        else:
            self.trainee_name = "Unbekannt"
            self.training_name = "Unbekannt"

        os.makedirs(self.screenshot_folder, exist_ok=True)

        self.load_screenshots()
        self.load_comments()

        self.create_gui()
        self.bind_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

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
            self.comments = {}

    def save_comments(self):
        with open(self.comments_file, "w") as f:
            json.dump(self.comments, f, indent=4)

    def create_gui(self):
        # Info-Leiste
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(fill="x", pady=5)

        # Setze die Info-Leiste auf "Name des Trainees - Trainingsname"
        self.info_label = tk.Label(
            self.info_frame,
            text=f"{self.trainee_name} - {self.training_name} | Screenshots: {len(self.screenshots)}",
            font=("Arial", 12, "bold"),
        )
        self.info_label.pack()

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

    def bind_hotkey(self):
        self.root.bind("<Control-b>", lambda event: self.add_comment_to_last_screenshot())

    def display_screenshots(self):
        # Lösche vorhandene Widgets
        for widget in self.frame.winfo_children():
            widget.destroy()

        # Aktualisiere die Info-Leiste
        self.info_label.config(
            text=f"{self.trainee_name} - {self.training_name} | Screenshots: {len(self.screenshots)}"
        )

        # Anzeige der Screenshots
        for idx, screenshot_path in enumerate(self.screenshots):
            try:
                # Lade das Bild
                image = Image.open(screenshot_path)
                image.thumbnail((150, 150))
                photo = ImageTk.PhotoImage(image)

                # Grid-Position berechnen
                row = idx // 3 * 2  # Jede Bildzeile benötigt 2 Zeilen (Bild + Info)
                col = idx % 3

                # Bild-Label
                img_label = tk.Label(self.frame, image=photo)
                img_label.image = photo
                img_label.grid(row=row, column=col, padx=5, pady=5)

                # Zusatzinformationen
                filename = os.path.basename(screenshot_path)
                filename_without_ext = os.path.splitext(filename)[0]
                try:
                    timestamp = filename_without_ext.split("_")[1] + "_" + filename_without_ext.split("_")[2]
                    timestamp_str = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%H:%M:%S")
                except (IndexError, ValueError):
                    timestamp_str = "Unbekannte Zeit"

                comment = self.comments.get(filename, "Keine Bemerkung")

                # Info-Label
                info_label = tk.Label(
                    self.frame,
                    text=f"Zeit: {timestamp_str}\nBemerkung: {comment}",
                    font=("Arial", 9),
                    justify="center",
                )
                info_label.grid(row=row + 1, column=col, padx=5, pady=5)

                # Kontextmenü für Optionen
                context_menu = tk.Menu(self.root, tearoff=0)
                context_menu.add_command(label="Bemerkung bearbeiten", command=lambda path=screenshot_path: self.add_comment(path))
                context_menu.add_command(label="Screenshot löschen", command=lambda path=screenshot_path: self.delete_screenshot(path))

                def show_context_menu(event, menu=context_menu):
                    menu.post(event.x_root, event.y_root)

                # Rechtsklick-Bindung
                img_label.bind("<Button-3>", show_context_menu)
            except Exception as e:
                print(f"Error loading image {screenshot_path}: {e}")

    def add_comment(self, screenshot_path):
        filename = os.path.basename(screenshot_path)
        current_comment = self.comments.get(filename, "")

        comment = simpledialog.askstring(
            "Bemerkung bearbeiten",
            f"Bemerkung für {filename} eingeben:",
            initialvalue=current_comment,
        )
        if comment is not None:  # Nicht abbrechen
            self.comments[filename] = comment
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

    def refresh(self):
        self.load_screenshots()
        self.display_screenshots()

    def on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.root.destroy()
