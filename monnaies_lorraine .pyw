import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import sqlite3
import os
import io

ORDRE_PAS = 100


def init_db():
    with sqlite3.connect("data/monnaies.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monnaies'")
        table_exists = cursor.fetchone() is not None
        if not table_exists:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monnaies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attribution TEXT,
                    type TEXT,
                    valeur_faciale TEXT,
                    localite TEXT,
                    periode_annee TEXT,
                    legende_avers TEXT,
                    description_avers TEXT,
                    legende_revers TEXT,
                    description_revers TEXT,
                    atelier TEXT,
                    metal TEXT,
                    poids_gr REAL DEFAULT 0,
                    ouvrage_numismatique TEXT,
                    possession BOOLEAN,
                    observations TEXT,
                    image_gravure BLOB,
                    image_monnaie BLOB,
                    biographie TEXT,
                    image_biographie BLOB,
                    ordre INTEGER DEFAULT 0
                )
            ''')
            conn.commit()
            return
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_periode ON monnaies(periode_annee)')
        conn.commit()


def reorder_all_fiches():
    with sqlite3.connect("data/monnaies.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            WITH ordered AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        ORDER BY CAST(substr(periode_annee, 1, instr(periode_annee, '-') - 1) AS INT),
                         substr(valeur_faciale, instr(valeur_faciale, ' ') + 1, 1) DESC,
                          CAST(substr(valeur_faciale, 1, instr(valeur_faciale, ' ') - 1) AS INTEGER),
                           attribution
                    ) * ? AS new_order
                FROM monnaies
                )
                UPDATE monnaies
                    SET ordre = (
                        SELECT new_order
                        FROM ordered
                        WHERE ordered.id = monnaies.id
                    )
        ''', (ORDRE_PAS,))
        conn.commit()


class FicheDetailWindow:
    def __init__(self, parent, fiche_id=None, insert_after_id=None):
        self.parent = parent
        self.fiche_id = fiche_id
        self.insert_after_id = insert_after_id
        self.window = tk.Toplevel(parent.root)
        self.window.title(f"Fiche {'-' + str(fiche_id) if fiche_id else 'Nouvelle'}")
        self.window.geometry("950x700")
        self.image_gravure_blob = None
        self.image_monnaie_blob = None
        self.biographie_image_blob = None
        self.biographie_text_content = ""
        self.main_frame = ttk.Frame(self.window, padding="5")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.images_frame = ttk.LabelFrame(self.main_frame, text="Images", padding="5")
        self.images_frame.grid(row=0, column=1, rowspan=16, sticky=tk.NSEW, padx=5, pady=5)
        self.gravure_frame = ttk.Frame(self.images_frame)
        self.gravure_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self.gravure_frame, text="Gravure", font=("Times New Roman", 10, "bold")).pack()
        self.gravure_canvas = tk.Canvas(self.gravure_frame, width=180, height=180, bg="#FFFDD0")
        self.gravure_canvas.pack(pady=2)
        self.gravure_canvas.bind("<Double-1>", lambda e: self.zoom_image("gravure"))
        ttk.Button(self.gravure_frame, text="Charger Gravure", command=lambda: self.load_image("gravure")).pack(
            fill=tk.X, pady=2)
        self.monnaie_frame = ttk.Frame(self.images_frame)
        self.monnaie_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self.monnaie_frame, text="Monnaie", font=("Times New Roman", 10, "bold")).pack()
        self.monnaie_canvas = tk.Canvas(self.monnaie_frame, width=180, height=180, bg="#FFFDD0")
        self.monnaie_canvas.pack(pady=2)
        self.monnaie_canvas.bind("<Double-1>", lambda e: self.zoom_image("monnaie"))
        ttk.Button(self.monnaie_frame, text="Charger Monnaie", command=lambda: self.load_image("monnaie")).pack(
            fill=tk.X, pady=2)
        self.fields_frame = ttk.Frame(self.main_frame)
        self.fields_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.create_fields()
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=16, column=0, columnspan=2, sticky=tk.S + tk.E + tk.W, pady=5)
        ttk.Button(self.button_frame, text="Enregistrer", command=self.save_fiche).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Modification", command=self.enable_modification).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Fermer", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        self.main_frame.columnconfigure(0, weight=2)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        if self.fiche_id:
            self.load_fiche()
            self.disable_fields()

    def disable_fields(self):
        for widget in [self.attribution_combobox, self.type_combobox, self.valeur_combobox, self.localite_combobox,
                       self.periode_entry, self.legende_avers_entry, self.legende_revers_entry, self.atelier_combobox,
                       self.metal_combobox, self.poids_entry, self.ouvrage_entry]:
            widget.config(state="disabled")
        for text in [self.description_avers_entry, self.description_revers_entry, self.observations_entry]:
            text.config(state="disabled")

    def enable_fields(self):
        for widget in [self.attribution_combobox, self.type_combobox, self.valeur_combobox, self.localite_combobox,
                       self.periode_entry, self.legende_avers_entry, self.legende_revers_entry, self.atelier_combobox,
                       self.metal_combobox, self.poids_entry, self.ouvrage_entry]:
            widget.config(state="normal")
        for text in [self.description_avers_entry, self.description_revers_entry, self.observations_entry]:
            text.config(state="normal")

    def enable_modification(self):
        if not self.fiche_id:
            return
        if messagebox.askyesno("Modification", "Voulez-vous vraiment modifier cette fiche ?"):
            self.enable_fields()

    def create_fields(self):
        self.fields_frame.columnconfigure(1, weight=1)
        self.fields_frame.columnconfigure(2, weight=1)
        ttk.Label(self.fields_frame, text="ID", font=("Times New Roman", 10, "bold")).grid(row=0, column=0, sticky=tk.W,
                                                                                           pady=2)
        self.id_entry = ttk.Entry(self.fields_frame, state="readonly", width=10)
        self.id_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Attribution", font=("Times New Roman", 10, "bold italic")).grid(row=1,
                                                                                                           column=0,
                                                                                                           sticky=tk.W,
                                                                                                           pady=2)
        self.attribution_combobox = ttk.Combobox(self.fields_frame, width=38, state="normal")
        self.attribution_combobox.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.attribution_combobox.bind("<<ComboboxSelected>>", self.on_attribution_change)
        ttk.Button(self.fields_frame, text="Biographie", command=self.open_biographie).grid(row=1, column=2,
                                                                                            sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.fields_frame, text="Type", font=("Times New Roman", 10, "bold italic")).grid(row=2, column=0,
                                                                                                    sticky=tk.W, pady=2)
        self.type_combobox = ttk.Combobox(self.fields_frame, width=28, state="normal")
        self.type_combobox.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Valeur faciale", font=("Times New Roman", 10, "bold italic")).grid(row=3,
                                                                                                              column=0,
                                                                                                              sticky=tk.W,
                                                                                                              pady=2)
        self.valeur_combobox = ttk.Combobox(self.fields_frame, width=13, state="normal")
        self.valeur_combobox.grid(row=3, column=1, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Localité", font=("Times New Roman", 10, "bold italic")).grid(row=4, column=0,
                                                                                                        sticky=tk.W,
                                                                                                        pady=2)
        self.localite_combobox = ttk.Combobox(self.fields_frame, width=28, state="normal")
        self.localite_combobox.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Période/Année", font=("Times New Roman", 10, "bold italic")).grid(row=5,
                                                                                                             column=0,
                                                                                                             sticky=tk.W,
                                                                                                             pady=2)
        self.periode_entry = ttk.Entry(self.fields_frame, width=30)
        self.periode_entry.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Légende Avers", font=("Times New Roman", 10, "bold italic")).grid(row=6,
                                                                                                             column=0,
                                                                                                             sticky=tk.W,
                                                                                                             pady=2)
        self.legende_avers_entry = ttk.Entry(self.fields_frame, width=100)
        self.legende_avers_entry.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Description Avers", font=("Times New Roman", 10, "bold italic")).grid(row=7,
                                                                                                                 column=0,
                                                                                                                 sticky=tk.W,
                                                                                                                 pady=2)
        self.description_avers_entry = tk.Text(self.fields_frame, height=3, width=40, bg="#FFFDD0", fg="#555555",
                                               font=("Times New Roman", 10))
        self.description_avers_entry.grid(row=7, column=1, columnspan=2, sticky=tk.W + tk.E, pady=2)
        ttk.Label(self.fields_frame, text="Légende Revers", font=("Times New Roman", 10, "bold italic")).grid(row=8,
                                                                                                              column=0,
                                                                                                              sticky=tk.W,
                                                                                                              pady=2)
        self.legende_revers_entry = ttk.Entry(self.fields_frame, width=100)
        self.legende_revers_entry.grid(row=8, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Description Revers", font=("Times New Roman", 10, "bold italic")).grid(row=9,
                                                                                                                  column=0,
                                                                                                                  sticky=tk.W,
                                                                                                                  pady=2)
        self.description_revers_entry = tk.Text(self.fields_frame, height=3, width=40, bg="#FFFDD0", fg="#555555",
                                                font=("Times New Roman", 10))
        self.description_revers_entry.grid(row=9, column=1, columnspan=2, sticky=tk.W + tk.E, pady=2)
        ttk.Label(self.fields_frame, text="Atelier", font=("Times New Roman", 10, "bold italic")).grid(row=10, column=0,
                                                                                                       sticky=tk.W,
                                                                                                       pady=2)
        self.atelier_combobox = ttk.Combobox(self.fields_frame, width=28, state="normal")
        self.atelier_combobox.grid(row=10, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Métal", font=("Times New Roman", 10, "bold italic")).grid(row=11, column=0,
                                                                                                     sticky=tk.W,
                                                                                                     pady=2)
        self.metal_combobox = ttk.Combobox(self.fields_frame, width=18, state="normal")
        self.metal_combobox.grid(row=11, column=1, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Poids ( grs )", font=("Times New Roman", 10, "bold italic")).grid(row=12,
                                                                                                             column=0,
                                                                                                             sticky=tk.W,
                                                                                                             pady=2)
        self.poids_entry = ttk.Entry(self.fields_frame, width=10)
        self.poids_entry.grid(row=12, column=1, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Ouvrage Numismatique", font=("Times New Roman", 10, "bold italic")).grid(
            row=13, column=0, sticky=tk.W, pady=2)
        self.ouvrage_entry = ttk.Entry(self.fields_frame, width=40)
        self.ouvrage_entry.grid(row=13, column=1, columnspan=2, sticky=tk.W, pady=2)
        self.possession_var = tk.BooleanVar()
        self.possession_check = ttk.Checkbutton(self.fields_frame, text="Possession", variable=self.possession_var)
        self.possession_check.grid(row=14, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(self.fields_frame, text="Observations", font=("Times New Roman", 10, "bold italic")).grid(row=15,
                                                                                                            column=0,
                                                                                                            sticky=tk.W,
                                                                                                            pady=2)
        self.observations_entry = tk.Text(self.fields_frame, height=5, width=40, bg="#FFFDD0", fg="#555555",
                                          font=("Times New Roman", 10))
        self.observations_entry.grid(row=15, column=1, columnspan=2, sticky=tk.W + tk.E, pady=(2, 5))
        self.load_combobox_values()

    def on_attribution_change(self, event=None):
        attribution = self.attribution_combobox.get()
        if attribution:
            self.load_biographie_by_attribution(attribution)

    def load_biographie_by_attribution(self, attribution):
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT biographie, image_biographie FROM monnaies WHERE attribution=? AND biographie IS NOT NULL LIMIT 1",
                    (attribution,))
                row = cursor.fetchone()
                if row:
                    self.biographie_text_content = row[0] if row[0] else ""
                    self.biographie_image_blob = row[1]
        except sqlite3.Error as e:
            messagebox.showerror("Erreur",
                                 f"Impossible de charger la biographie pour l'attribution {attribution} : {e}")

    def validate_required_fields(self):
        required_fields = [
            ("Attribution", self.attribution_combobox),
            ("Type", self.type_combobox),
            ("Valeur faciale", self.valeur_combobox),
            ("Localité", self.localite_combobox),
            ("Période/Année", self.periode_entry)
        ]
        missing_fields = []
        for field_name, widget in required_fields:
            value = widget.get() if hasattr(widget, 'get') else widget.get(1.0, tk.END).strip()
            if not value:
                missing_fields.append(field_name)
        if missing_fields:
            messagebox.showerror("Champs obligatoires manquants",
                                 f"Les champs suivants sont obligatoires : {', '.join(missing_fields)}. Veuillez les remplir avant d'enregistrer.")
            return False
        return True

    def load_combobox_values(self):
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT attribution FROM monnaies WHERE attribution IS NOT NULL ORDER BY attribution")
                attributions = [row[0] for row in cursor.fetchall() if row[0]]
                self.attribution_combobox["values"] = attributions
                cursor.execute("SELECT DISTINCT type FROM monnaies WHERE type IS NOT NULL ORDER BY type")
                types = [row[0] for row in cursor.fetchall() if row[0]]
                self.type_combobox["values"] = types
                cursor.execute(
                    "SELECT DISTINCT valeur_faciale FROM monnaies WHERE valeur_faciale IS NOT NULL ORDER BY valeur_faciale")
                valeurs = [row[0] for row in cursor.fetchall() if row[0]]
                self.valeur_combobox["values"] = valeurs
                cursor.execute("SELECT DISTINCT localite FROM monnaies WHERE localite IS NOT NULL ORDER BY localite")
                localites = [row[0] for row in cursor.fetchall() if row[0]]
                self.localite_combobox["values"] = localites
                cursor.execute("SELECT DISTINCT atelier FROM monnaies WHERE atelier IS NOT NULL ORDER BY atelier")
                ateliers = [row[0] for row in cursor.fetchall() if row[0]]
                self.atelier_combobox["values"] = ateliers
                cursor.execute("SELECT DISTINCT metal FROM monnaies WHERE metal IS NOT NULL ORDER BY metal")
                metaux = [row[0] for row in cursor.fetchall() if row[0]]
                self.metal_combobox["values"] = metaux
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible de charger les valeurs des menus déroulants : {e}")

    def load_fiche(self):
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM monnaies WHERE id=?", (self.fiche_id,))
                row = cursor.fetchone()
                if not row:
                    messagebox.showerror("Erreur", f"Aucune fiche trouvée avec l'ID {self.fiche_id}.")
                    return
                self.id_entry.config(state="normal")
                self.id_entry.delete(0, tk.END)
                self.id_entry.insert(0, row[0])
                self.id_entry.config(state="readonly")
                self.attribution_combobox.set(row[1] if row[1] else "")
                self.type_combobox.set(row[2] if row[2] else "")
                self.valeur_combobox.set(row[3] if row[3] else "")
                self.localite_combobox.set(row[4] if row[4] else "")
                self.periode_entry.delete(0, tk.END)
                self.periode_entry.insert(0, row[5] if row[5] else "")
                self.legende_avers_entry.delete(0, tk.END)
                self.legende_avers_entry.insert(0, row[6] if row[6] else "")
                self.description_avers_entry.delete(1.0, tk.END)
                self.description_avers_entry.insert(1.0, row[7] if row[7] else "")
                self.legende_revers_entry.delete(0, tk.END)
                self.legende_revers_entry.insert(0, row[8] if row[8] else "")
                self.description_revers_entry.delete(1.0, tk.END)
                self.description_revers_entry.insert(1.0, row[9] if row[9] else "")
                self.atelier_combobox.set(row[10] if row[10] else "")
                self.metal_combobox.set(row[11] if row[11] else "")
                self.poids_entry.delete(0, tk.END)
                self.poids_entry.insert(0, row[12] if row[12] is not None else "")
                self.ouvrage_entry.delete(0, tk.END)
                self.ouvrage_entry.insert(0, row[13] if row[13] else "")
                self.possession_var.set(bool(row[14]))
                self.observations_entry.delete(1.0, tk.END)
                self.observations_entry.insert(1.0, row[15] if row[15] else "")
                self.image_gravure_blob = row[16]
                self.image_monnaie_blob = row[17]
                if len(row) > 18:
                    self.biographie_text_content = row[18] if row[18] else ""
                if len(row) > 19:
                    self.biographie_image_blob = row[19]
                if row[16]:
                    self.display_image(self.gravure_canvas, row[16])
                else:
                    self.gravure_canvas.delete("all")
                    self.gravure_canvas.create_text(90, 90, text="Aucune image", anchor=tk.CENTER, fill="#555555",
                                                    font=("Times New Roman", 10))
                if row[17]:
                    self.display_image(self.monnaie_canvas, row[17])
                else:
                    self.monnaie_canvas.delete("all")
                    self.monnaie_canvas.create_text(90, 90, text="Aucune image", anchor=tk.CENTER, fill="#555555",
                                                    font=("Times New Roman", 10))
                if row[1]:
                    self.load_biographie_by_attribution(row[1])
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible de charger la fiche : {e}")

    def display_image(self, canvas, image_data):
        canvas.delete("all")
        try:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((180, 180))
            photo = ImageTk.PhotoImage(image)
            canvas.image = photo
            canvas.create_image(90, 90, image=photo, anchor=tk.CENTER)
        except Exception as e:
            canvas.create_text(90, 90, text=f"Erreur: {e}", anchor=tk.CENTER, fill="#555555",
                               font=("Times New Roman", 10))

    def load_image(self, image_type):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    image_data = f.read()
                if image_type == "gravure":
                    self.display_image(self.gravure_canvas, image_data)
                    self.image_gravure_blob = image_data
                elif image_type == "monnaie":
                    self.display_image(self.monnaie_canvas, image_data)
                    self.image_monnaie_blob = image_data
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur de chargement : {e}")

    def zoom_image(self, image_type):
        blob = self.image_gravure_blob if image_type == "gravure" else self.image_monnaie_blob
        if blob:
            self.show_zoomed_image(blob)

    def show_zoomed_image(self, image_blob):
        try:
            window = tk.Toplevel(self.window)
            window.title("Image agrandie")
            window.configure(bg="#FFFDD0")
            image = Image.open(io.BytesIO(image_blob))
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(window, image=photo, bg="#FFFDD0")
            label.image = photo
            label.pack()
            ttk.Button(window, text="Fermer", command=window.destroy).pack(pady=5)
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur d'affichage : {e}")

    def ensure_biographie_loaded(self):
        if not self.biographie_text_content and not self.biographie_image_blob:
            attribution = self.attribution_combobox.get()
            if attribution:
                self.load_biographie_by_attribution(attribution)

    def save_fiche(self):
        if not self.validate_required_fields():
            return False
        self.ensure_biographie_loaded()
        try:
            try:
                poids = float(self.poids_entry.get()) if self.poids_entry.get() else None
            except ValueError:
                messagebox.showerror("Erreur", "Le poids doit être un nombre.")
                return False
            data = {
                "attribution": self.attribution_combobox.get(),
                "type": self.type_combobox.get(),
                "valeur_faciale": self.valeur_combobox.get(),
                "localite": self.localite_combobox.get(),
                "periode_annee": self.periode_entry.get(),
                "legende_avers": self.legende_avers_entry.get(),
                "description_avers": self.description_avers_entry.get(1.0, tk.END).strip(),
                "legende_revers": self.legende_revers_entry.get(),
                "description_revers": self.description_revers_entry.get(1.0, tk.END).strip(),
                "atelier": self.atelier_combobox.get(),
                "metal": self.metal_combobox.get(),
                "poids_gr": poids,
                "ouvrage_numismatique": self.ouvrage_entry.get(),
                "possession": self.possession_var.get(),
                "observations": self.observations_entry.get(1.0, tk.END).strip(),
                "image_gravure": self.image_gravure_blob,
                "image_monnaie": self.image_monnaie_blob,
                "biographie": self.biographie_text_content,
                "image_biographie": self.biographie_image_blob
            }
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                if self.fiche_id:
                    cursor.execute('''
                        UPDATE monnaies SET
                        attribution=?, type=?, valeur_faciale=?, localite=?, periode_annee=?,  -- ✅ Ajout du "?" après periode_annee
                        legende_avers=?, description_avers=?, legende_revers=?, description_revers=?,
                        atelier=?, metal=?, poids_gr=?, ouvrage_numismatique=?, possession=?, observations=?, image_gravure=?, image_monnaie=?, biographie=?, image_biographie=?,
                        ordre=COALESCE(ordre, 0)
                        WHERE id=?
                    ''', (
                        data["attribution"], data["type"], data["valeur_faciale"], data["localite"],
                        data["periode_annee"],
                        data["legende_avers"], data["description_avers"], data["legende_revers"],
                        data["description_revers"],
                        data["atelier"], data["metal"], data["poids_gr"], data["ouvrage_numismatique"],
                        data["possession"],
                        # ✅ Cette valeur était déjà dans le tuple, mais le "?" manquait dans la requête
                        data["observations"], data["image_gravure"], data["image_monnaie"],
                        data["biographie"], data["image_biographie"], self.fiche_id
                    ))
                else:
                    if self.insert_after_id:
                        new_order = self.compute_insert_order(cursor, self.insert_after_id)
                    else:
                        cursor.execute("SELECT MAX(ordre) FROM monnaies")
                        max_order = cursor.fetchone()[0]
                        new_order = max_order + ORDRE_PAS if max_order is not None else 0

                    cursor.execute('''
                        INSERT INTO monnaies (
                            attribution, type, valeur_faciale, localite, periode_annee,
                            legende_avers, description_avers, legende_revers, description_revers,
                            atelier, metal, poids_gr, ouvrage_numismatique, possession,
                            observations, image_gravure, image_monnaie, biographie, image_biographie, ordre
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data["attribution"], data["type"], data["valeur_faciale"], data["localite"],
                        data["periode_annee"],
                        data["legende_avers"], data["description_avers"], data["legende_revers"],
                        data["description_revers"],
                        data["atelier"], data["metal"], data["poids_gr"], data["ouvrage_numismatique"],
                        data["possession"], data["observations"], data["image_gravure"], data["image_monnaie"],
                        data["biographie"], data["image_biographie"], new_order
                    ))
                    self.fiche_id = cursor.lastrowid
                    self.id_entry.config(state="normal")
                    self.id_entry.delete(0, tk.END)
                    self.id_entry.insert(0, self.fiche_id)
                    self.id_entry.config(state="readonly")
                conn.commit()
            messagebox.showinfo("Succès", "Fiche enregistrée avec succès !")
            self.parent.load_data()
            self.parent.load_combobox_values()
            self.load_combobox_values()
            return True
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer la fiche : {e}")
            return False

    @staticmethod
    def compute_insert_order(cursor, insert_after_id):
        cursor.execute("SELECT ordre FROM monnaies WHERE id=?", (insert_after_id,))
        ref_order = cursor.fetchone()[0]
        cursor.execute("SELECT MIN(ordre) FROM monnaies WHERE ordre > ?", (ref_order,))
        next_order = cursor.fetchone()[0]
        if next_order is None:
            return ref_order + ORDRE_PAS
        if next_order - ref_order > 1:
            return ref_order + (next_order - ref_order) // 2
        cursor.execute("UPDATE monnaies SET ordre = ordre + ? WHERE ordre > ?", (ORDRE_PAS, ref_order))
        return ref_order + ORDRE_PAS // 2

    def open_biographie(self):
        if not self.fiche_id:
            if not self.save_fiche():
                return
        self.ensure_biographie_loaded()
        self.biographie_window = tk.Toplevel(self.window)
        self.biographie_window.title(f"Biographie - {self.attribution_combobox.get()}")
        self.biographie_window.geometry("800x750")
        self.biographie_window.minsize(500, 400)
        self.biographie_window.configure(bg="#FFFDD0")
        image_frame = ttk.LabelFrame(self.biographie_window, text="Image de la biographie", padding="5")
        image_frame.pack(fill=tk.X, padx=10, pady=5)
        self.biographie_canvas = tk.Canvas(image_frame, width=200, height=200, bg="#FFFDD0", highlightthickness=0)
        self.biographie_canvas.pack(pady=5)
        self.biographie_canvas.bind("<Double-1>", lambda e: self.zoom_biographie_image())
        button_image_frame = ttk.Frame(image_frame)
        button_image_frame.pack(fill=tk.X, pady=2)
        ttk.Button(button_image_frame, text="Charger une image", command=self.load_biographie_image).pack(side=tk.LEFT,
                                                                                                          fill=tk.X,
                                                                                                          expand=True,
                                                                                                          padx=2)
        ttk.Button(button_image_frame, text="Supprimer l'image", command=self.clear_biographie_image).pack(
            side=tk.RIGHT, padx=2)
        text_frame = ttk.Frame(self.biographie_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.biographie_text = tk.Text(text_frame, wrap=tk.WORD, bg="#FFFDD0", fg="#555555",
                                       font=("Times New Roman", 10))
        self.biographie_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.biographie_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.biographie_text.configure(yscrollcommand=scrollbar.set)
        if self.biographie_text_content:
            self.biographie_text.insert(1.0, self.biographie_text_content)
        if self.biographie_image_blob:
            self.display_biographie_image(self.biographie_canvas, self.biographie_image_blob)
        else:
            self.biographie_canvas.delete("all")
            self.biographie_canvas.create_text(100, 100, text="Aucune image", anchor=tk.CENTER, fill="#555555",
                                               font=("Times New Roman", 10))
        button_frame = ttk.Frame(self.biographie_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(button_frame, text="Enregistrer", command=self.save_biographie).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Fermer", command=self.biographie_window.destroy).pack(side=tk.RIGHT, padx=5)

    def load_biographie_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    image_data = f.read()
                self.display_biographie_image(self.biographie_canvas, image_data)
                self.biographie_image_blob = image_data
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur de chargement : {e}")

    def clear_biographie_image(self):
        self.biographie_canvas.delete("all")
        self.biographie_canvas.create_text(100, 100, text="Aucune image", anchor=tk.CENTER, fill="#555555",
                                           font=("Times New Roman", 10))
        self.biographie_image_blob = None

    def display_biographie_image(self, canvas, image_data):
        canvas.delete("all")
        try:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(image)
            canvas.image = photo
            canvas.create_image(100, 100, image=photo, anchor=tk.CENTER)
        except Exception as e:
            canvas.create_text(100, 100, text=f"Erreur: {e}", anchor=tk.CENTER, fill="#555555",
                               font=("Times New Roman", 10))

    def zoom_biographie_image(self):
        if self.biographie_image_blob:
            try:
                window = tk.Toplevel(self.window)
                window.title("Image de la biographie (agrandie)")
                window.configure(bg="#FFFDD0")
                image = Image.open(io.BytesIO(self.biographie_image_blob))
                photo = ImageTk.PhotoImage(image)
                label = tk.Label(window, image=photo, bg="#FFFDD0")
                label.image = photo
                label.pack()
                ttk.Button(window, text="Fermer", command=window.destroy).pack(pady=5)
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur d'affichage : {e}")

    def save_biographie(self):
        if not self.fiche_id:
            messagebox.showerror("Erreur", "Impossible d'enregistrer la biographie : la fiche n'a pas d'ID.")
            return
        self.biographie_text_content = self.biographie_text.get(1.0, tk.END).strip()
        self.biographie_image_blob = getattr(self, 'biographie_image_blob', None)
        attribution = self.attribution_combobox.get()
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE monnaies SET biographie=?, image_biographie=? WHERE attribution=?",
                               (self.biographie_text_content, self.biographie_image_blob, attribution))
                conn.commit()
            messagebox.showinfo("Succès",
                                "Biographie et image enregistrées avec succès pour toutes les fiches avec cette attribution !")
            self.biographie_window.destroy()
            self.parent.load_data()
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer la biographie : {e}")


class MonnaiesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Les monnaies en Terre de Lorraine")
        self.root.geometry("1400x800")
        self.root.minsize(1200, 700)
        self.root.configure(bg="#FFFFF0")
        self.apply_ancient_style()
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.button_frame = ttk.Frame(self.main_container)
        self.button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(self.button_frame, text="Ajouter une fiche", command=self.add_fiche).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Insérer une fiche", command=self.insert_fiche).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Supprimer la fiche", command=self.delete_fiche).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Actualiser", command=self.load_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Réordonner", command=self.reorder_fiches).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.button_frame, text="Quitter", command=self.quit_app).pack(side=tk.RIGHT, padx=5)
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)
        self.liste_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.liste_frame, text="Liste des Fiches")
        self.recherche_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.recherche_frame, text="Recherche")
        self.tree_images = {}
        self.tree_images_recherche = {}
        self.taille_miniature = 40
        self.recherche_dans_resultats_var = tk.BooleanVar()
        self.create_liste_fiches_tab()
        self.create_recherche_tab()
        self.load_data()
        self.load_combobox_values()

    def apply_ancient_style(self):
        style = ttk.Style()
        bg_color = "#FFFFF0"
        fg_color = "#555555"
        highlight_color = "#CD853F"
        creme_color = "#FFFDD0"
        self.root.configure(bg=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Times New Roman", 10, "italic"))
        style.configure("TNotebook", background=bg_color)
        style.configure("TNotebook.Tab", background=creme_color, foreground=fg_color,
                        font=("Times New Roman", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", highlight_color)])
        style.configure("Custom.Treeview", background=creme_color, foreground=fg_color, fieldbackground=creme_color,
                        font=("Times New Roman", 10), rowheight=52)
        style.map("Custom.Treeview", background=[("selected", highlight_color)], foreground=[("selected", "white")])
        style.configure("Treeview", rowheight=52)
        style.configure("TButton", background=highlight_color, foreground=fg_color,
                        font=("Times New Roman", 10, "bold"), borderwidth=2, relief="raised")
        style.map("TButton", background=[("active", creme_color)], foreground=[("active", "white")])
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        style.configure("TEntry", fieldbackground=creme_color, foreground=fg_color, font=("Times New Roman", 10))
        style.configure("TCombobox", fieldbackground=creme_color, foreground=fg_color, font=("Times New Roman", 10))
        style.configure("TScrollbar", background=bg_color, troughcolor=highlight_color)

    def load_combobox_values(self):
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT attribution FROM monnaies WHERE attribution IS NOT NULL ORDER BY attribution")
                attributions = [row[0] for row in cursor.fetchall() if row[0]]
                cursor.execute("SELECT DISTINCT type FROM monnaies WHERE type IS NOT NULL ORDER BY type")
                types = [row[0] for row in cursor.fetchall() if row[0]]
                cursor.execute(
                    "SELECT DISTINCT valeur_faciale FROM monnaies WHERE valeur_faciale IS NOT NULL ORDER BY valeur_faciale")
                valeurs = [row[0] for row in cursor.fetchall() if row[0]]
                cursor.execute("SELECT DISTINCT localite FROM monnaies WHERE localite IS NOT NULL ORDER BY localite")
                localites = [row[0] for row in cursor.fetchall() if row[0]]
                cursor.execute("SELECT DISTINCT atelier FROM monnaies WHERE atelier IS NOT NULL ORDER BY atelier")
                ateliers = [row[0] for row in cursor.fetchall() if row[0]]
                cursor.execute("SELECT DISTINCT metal FROM monnaies WHERE metal IS NOT NULL ORDER BY metal")
                metaux = [row[0] for row in cursor.fetchall() if row[0]]
            for window in self.root.winfo_children():
                if isinstance(window, tk.Toplevel):
                    for child in window.winfo_children():
                        if isinstance(child, ttk.Frame):
                            for subchild in child.winfo_children():
                                if isinstance(subchild, ttk.Frame):
                                    for widget in subchild.winfo_children():
                                        if isinstance(widget, ttk.Combobox):
                                            if hasattr(widget, 'winfo_class') and widget.winfo_class() == 'TCombobox':
                                                if 'attribution_combobox' in str(widget):
                                                    widget["values"] = attributions
                                                elif 'type_combobox' in str(widget):
                                                    widget["values"] = types
                                                elif 'valeur_combobox' in str(widget):
                                                    widget["values"] = valeurs
                                                elif 'localite_combobox' in str(widget):
                                                    widget["values"] = localites
                                                elif 'atelier_combobox' in str(widget):
                                                    widget["values"] = ateliers
                                                elif 'metal_combobox' in str(widget):
                                                    widget["values"] = metaux
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible de charger les valeurs des menus déroulants : {e}")

    def create_liste_fiches_tab(self):
        title_label = ttk.Label(
            self.liste_frame,
            text="Les monnaies en Terre de Lorraine",
            font=("Times New Roman", 18, "bold italic"),
            foreground="#555555",
            background="#FFFFF0",
            anchor=tk.CENTER
        )
        title_label.pack(fill=tk.X, pady=(10, 5))
        self.liste_container = ttk.Frame(self.liste_frame)
        self.liste_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.tree_liste = ttk.Treeview(
            self.liste_container,
            columns=("ID", "Attribution", "Type", "Valeur Faciale", "Localité", "Période"),
            show="tree headings",
            style="Custom.Treeview"
        )
        self.tree_liste.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.liste_container, orient=tk.VERTICAL, command=self.tree_liste.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_liste.configure(yscrollcommand=scrollbar.set)
        self.tree_liste.heading("#0", text="", anchor=tk.CENTER)
        self.tree_liste.heading("ID", text="ID", anchor=tk.CENTER)
        self.tree_liste.heading("Attribution", text="Attribution", anchor=tk.W)
        self.tree_liste.heading("Type", text="Type", anchor=tk.W)
        self.tree_liste.heading("Valeur Faciale", text="Valeur Faciale", anchor=tk.CENTER)
        self.tree_liste.heading("Localité", text="Localité", anchor=tk.W)
        self.tree_liste.heading("Période", text="Période", anchor=tk.CENTER)
        self.tree_liste.column("#0", width=42, anchor=tk.CENTER, stretch=False)
        self.tree_liste.column("ID", width=20, anchor=tk.CENTER)
        self.tree_liste.column("Valeur Faciale", width=70, anchor=tk.CENTER)
        self.tree_liste.column("Période", width=70, anchor=tk.CENTER)
        self.tree_liste.column("Attribution", width=200, anchor=tk.W)
        self.tree_liste.column("Type", width=100, anchor=tk.W)
        self.tree_liste.column("Localité", width=120, anchor=tk.W)
        self.tree_liste.tag_configure("odd", background="#FFFFF0")
        self.tree_liste.tag_configure("even", background="#FFFDD0")
        self.tree_liste.bind("<Double-1>", self.open_fiche_from_liste)
        self.tree_liste.bind("<Button-1>", self.on_tree_click)

    def on_tree_click(self, event):
        item = self.tree_liste.identify("item", event.x, event.y)
        column = self.tree_liste.identify("column", event.x, event.y)
        if item and column == "#0":
            fiche_id = self.tree_liste.item(item)["values"][0]
            if fiche_id in self.tree_images:
                image_blob = self.tree_images[fiche_id][1]
                self.show_zoomed_image_from_list(image_blob)

    def delete_fiche(self):
        selected_items = self.tree_liste.selection()
        if not selected_items:
            messagebox.showwarning("Attention", "Veuillez sélectionner une fiche à supprimer.")
            return
        selected_item = selected_items[0]
        fiche_id = self.tree_liste.item(selected_item)["values"][0]
        if messagebox.askyesno("Supprimer", "Voulez-vous vraiment supprimer cette fiche ?"):
            try:
                with sqlite3.connect("data/monnaies.db") as conn:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM monnaies WHERE id=?", (fiche_id,))
                    conn.commit()
                messagebox.showinfo("Succès", "Fiche supprimée avec succès !")
                self.load_data()
                self.load_combobox_values()
            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Impossible de supprimer la fiche : {e}")

    # def delete_fiche(self):
    #    selected_items = self.tree_liste.selection()
    #    if not selected_items:
    #        messagebox.showwarning("Attention", "Veuillez sélectionner une fiche à supprimer.")
    #        return
    #    selected_item = selected_items[0]
    #    fiche_id = self.tree_liste.item(selected_item)["values"][0]
    #    if messagebox.askyesno("Supprimer", "Voulez-vous vraiment supprimer cette fiche ?"):
    #        try:
    #            with sqlite3.connect("data/monnaies.db") as conn:
    #                conn.execute("PRAGMA foreign_keys = OFF")
    #                cursor = conn.cursor()
    #                cursor.execute("DELETE FROM monnaies WHERE id=?", (fiche_id,))
    #                cursor.execute("SELECT id FROM monnaies ORDER BY ordre")
    #                rows = cursor.fetchall()
    #                for new_order, (old_id,) in enumerate(rows, start=0):
    #                    cursor.execute("UPDATE monnaies SET ordre=? WHERE id=?", (new_order, old_id))
    #                conn.commit()
    #            messagebox.showinfo("Succès", "Fiche supprimée avec succès !")
    #            self.load_data()
    #            self.load_combobox_values()
    #        except sqlite3.Error as e:
    #            messagebox.showerror("Erreur", f"Impossible de supprimer la fiche : {e}")

    def create_recherche_tab(self):
        self.recherche_main_frame = ttk.Frame(self.recherche_frame)
        self.recherche_main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        criteria_frame = ttk.Frame(self.recherche_main_frame)
        criteria_frame.pack(fill=tk.X, pady=5)
        ttk.Label(criteria_frame, text="Champ :", font=("Times New Roman", 10, "bold")).grid(row=0, column=0, padx=5,
                                                                                             pady=5)
        self.recherche_champ = ttk.Combobox(
            criteria_frame,
            values=[
                "Attribution", "Type", "Valeur faciale", "Localité", "Période/Année",
                "Légende Avers", "Description Avers", "Légende Revers", "Description Revers",
                "Atelier", "Ouvrage Numismatique", "Observations"
            ],
            font=("Times New Roman", 10)
        )
        self.recherche_champ.grid(row=0, column=1, padx=5, pady=5)
        self.recherche_champ.set("Attribution")
        ttk.Label(criteria_frame, text="Type :", font=("Times New Roman", 10, "bold")).grid(row=0, column=2, padx=5,
                                                                                            pady=5)
        self.recherche_type = ttk.Combobox(
            criteria_frame,
            values=["Identique", "Commence par", "Contient", "Finit par", "Ne contient pas"],
            font=("Times New Roman", 10)
        )
        self.recherche_type.grid(row=0, column=3, padx=5, pady=5)
        self.recherche_type.set("Contient")
        ttk.Label(criteria_frame, text="Valeur :", font=("Times New Roman", 10, "bold")).grid(row=0, column=4, padx=5,
                                                                                              pady=5)
        self.recherche_valeur = ttk.Entry(criteria_frame, font=("Times New Roman", 10))
        self.recherche_valeur.grid(row=0, column=5, padx=5, pady=5)
        self.recherche_dans_resultats_check = ttk.Checkbutton(
            criteria_frame,
            text="Poursuivre la recherche dans les résultats",
            variable=self.recherche_dans_resultats_var
        )
        self.recherche_dans_resultats_check.grid(row=0, column=7, padx=10, pady=5)
        ttk.Button(criteria_frame, text="Rechercher", command=self.perform_recherche).grid(row=0, column=6, padx=5,
                                                                                           pady=5)
        self.recherche_results_frame = ttk.Frame(self.recherche_main_frame)
        self.recherche_results_frame.pack(fill=tk.BOTH, expand=True)
        self.tree_recherche = ttk.Treeview(
            self.recherche_results_frame,
            columns=("ID", "Attribution", "Type", "Valeur Faciale", "Localité", "Période"),
            show="tree headings",
            style="Custom.Treeview"
        )
        self.tree_recherche.heading("#0", text="", anchor=tk.CENTER)
        self.tree_recherche.heading("ID", text="ID", anchor=tk.CENTER)
        self.tree_recherche.heading("Attribution", text="Attribution", anchor=tk.W)
        self.tree_recherche.heading("Type", text="Type", anchor=tk.W)
        self.tree_recherche.heading("Valeur Faciale", text="Valeur Faciale", anchor=tk.CENTER)
        self.tree_recherche.heading("Localité", text="Localité", anchor=tk.W)
        self.tree_recherche.heading("Période", text="Période", anchor=tk.CENTER)
        self.tree_recherche.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_recherche.column("#0", width=42, anchor=tk.CENTER, stretch=False)
        self.tree_recherche.column("ID", width=40, anchor=tk.CENTER)
        self.tree_recherche.column("Valeur Faciale", width=70, anchor=tk.CENTER)
        self.tree_recherche.column("Période", width=70, anchor=tk.CENTER)
        self.tree_recherche.column("Attribution", width=200, anchor=tk.W)
        self.tree_recherche.column("Type", width=100, anchor=tk.W)
        self.tree_recherche.column("Localité", width=120, anchor=tk.W)
        self.tree_recherche.tag_configure("odd", background="#FFFFF0")
        self.tree_recherche.tag_configure("even", background="#FFFDD0")
        scrollbar = ttk.Scrollbar(self.recherche_results_frame, orient=tk.VERTICAL, command=self.tree_recherche.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_recherche.configure(yscrollcommand=scrollbar.set)
        self.tree_recherche.bind("<Double-1>", self.open_fiche_from_recherche)
        self.tree_recherche.bind("<Button-1>", self.on_recherche_tree_click)

    def on_recherche_tree_click(self, event):
        item = self.tree_recherche.identify("item", event.x, event.y)
        column = self.tree_recherche.identify("column", event.x, event.y)
        if item and column == "#0":
            fiche_id = self.tree_recherche.item(item)["values"][0]
            if fiche_id in self.tree_images_recherche:
                image_blob = self.tree_images_recherche[fiche_id][1]
                self.show_zoomed_image_from_list(image_blob)

    def show_zoomed_image_from_list(self, image_blob):
        try:
            zoom_window = tk.Toplevel(self.root)
            zoom_window.title("Image agrandie")
            zoom_window.configure(bg="#FFFDD0")
            image = Image.open(io.BytesIO(image_blob))
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(zoom_window, image=photo, bg="#FFFDD0")
            label.image = photo
            label.pack()
            ttk.Button(zoom_window, text="Fermer", command=zoom_window.destroy).pack(pady=5)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'afficher l'image : {e}")

    def load_data(self):
        try:
            with sqlite3.connect("data/monnaies.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, attribution, type, valeur_faciale, localite, periode_annee, image_monnaie, image_gravure FROM monnaies ORDER BY ordre")
                rows = cursor.fetchall()
            for row in self.tree_liste.get_children():
                self.tree_liste.delete(row)
            self.tree_images = {}
            if self.notebook.index("current") == 1:
                self.perform_recherche()
            for i, row in enumerate(rows):
                fiche_id, attribution, type_, valeur, localite, periode, image_monnaie_blob, image_gravure_blob = row
                tags = ("even",) if i % 2 == 0 else ("odd",)
                image_blob = image_monnaie_blob if image_monnaie_blob else image_gravure_blob
                photo = None
                if image_blob:
                    try:
                        image = Image.open(io.BytesIO(image_blob))
                        image = image.resize((self.taille_miniature, self.taille_miniature), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        self.tree_images[fiche_id] = (photo, image_blob)
                    except Exception as e:
                        print(f"Erreur image pour ID {fiche_id}: {e}")
                if photo:
                    self.tree_liste.insert("", tk.END, values=(fiche_id, attribution, type_, valeur, localite, periode),
                                           iid=fiche_id, tags=tags, image=photo)
                else:
                    self.tree_liste.insert("", tk.END, values=(fiche_id, attribution, type_, valeur, localite, periode),
                                           iid=fiche_id, tags=tags)
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible de charger les données : {e}")

    def open_fiche_from_liste(self, event):
        selected_item = self.tree_liste.selection()[0]
        fiche_id = self.tree_liste.item(selected_item)["values"][0]
        FicheDetailWindow(self, fiche_id)

    def open_fiche_from_recherche(self, event):
        selected_item = self.tree_recherche.selection()[0]
        fiche_id = self.tree_recherche.item(selected_item)["values"][0]
        FicheDetailWindow(self, fiche_id)

    def add_fiche(self):
        FicheDetailWindow(self, None)

    def insert_fiche(self):
        selected_items = self.tree_liste.selection()
        if not selected_items:
            messagebox.showwarning("Attention",
                                   "Veuillez sélectionner une fiche pour insérer une nouvelle fiche après celle-ci.")
            return
        selected_item = selected_items[0]
        fiche_id = self.tree_liste.item(selected_item)["values"][0]
        FicheDetailWindow(self, None, insert_after_id=fiche_id)

    def perform_recherche(self):
        champ = self.recherche_champ.get()
        type_recherche = self.recherche_type.get()
        valeur = self.recherche_valeur.get()
        rechercher_dans_resultats = self.recherche_dans_resultats_var.get()
        if not champ or not valeur:
            messagebox.showwarning("Attention", "Veuillez sélectionner un champ et une valeur.")
            return
        champ_map = {
            "Attribution": "attribution",
            "Type": "type",
            "Valeur faciale": "valeur_faciale",
            "Localité": "localite",
            "Période/Année": "periode_annee",
            "Légende Avers": "legende_avers",
            "Description Avers": "description_avers",
            "Légende Revers": "legende_revers",
            "Description Revers": "description_revers",
            "Atelier": "atelier",
            "Ouvrage Numismatique": "ouvrage_numismatique",
            "Observations": "observations"
        }
        db_champ = champ_map.get(champ, "attribution")
        if not rechercher_dans_resultats:
            if type_recherche == "Identique":
                condition = f"{db_champ} = ?"
            elif type_recherche == "Commence par":
                condition = f"{db_champ} LIKE ?"
                valeur = valeur + "%"
            elif type_recherche == "Contient":
                condition = f"{db_champ} LIKE ?"
                valeur = "%" + valeur + "%"
            elif type_recherche == "Finit par":
                condition = f"{db_champ} LIKE ?"
                valeur = "%" + valeur
            elif type_recherche == "Ne contient pas":
                condition = f"{db_champ} NOT LIKE ?"
                valeur = "%" + valeur + "%"
            try:
                with sqlite3.connect("data/monnaies.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"SELECT id, attribution, type, valeur_faciale, localite, periode_annee, image_monnaie, image_gravure FROM monnaies WHERE {condition} ORDER BY ordre",
                        (valeur,))
                    rows = cursor.fetchall()
                for row in self.tree_recherche.get_children():
                    self.tree_recherche.delete(row)
                self.tree_images_recherche = {}
                for i, row in enumerate(rows):
                    fiche_id, attribution, type_, valeur, localite, periode, image_monnaie_blob, image_gravure_blob = row
                    tags = ("even",) if i % 2 == 0 else ("odd",)
                    image_blob = image_monnaie_blob if image_monnaie_blob else image_gravure_blob
                    photo = None
                    if image_blob:
                        try:
                            image = Image.open(io.BytesIO(image_blob))
                            image = image.resize((self.taille_miniature, self.taille_miniature), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(image)
                            self.tree_images_recherche[fiche_id] = (photo, image_blob)
                        except Exception as e:
                            print(f"Erreur image pour ID {fiche_id}: {e}")
                    if photo:
                        self.tree_recherche.insert("", tk.END,
                                                   values=(fiche_id, attribution, type_, valeur, localite, periode),
                                                   iid=fiche_id, tags=tags, image=photo)
                    else:
                        self.tree_recherche.insert("", tk.END,
                                                   values=(fiche_id, attribution, type_, valeur, localite, periode),
                                                   iid=fiche_id, tags=tags)
            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Impossible d'effectuer la recherche : {e}")
        else:
            if not self.tree_recherche.get_children():
                messagebox.showwarning("Attention", "Aucun résultat à filtrer. Effectuez d'abord une recherche.")
                return
            current_results = []
            for item in self.tree_recherche.get_children():
                values = self.tree_recherche.item(item)["values"]
                current_results.append(values)
            ids = [row[0] for row in current_results]
            placeholders = ", ".join("?" * len(ids))
            try:
                with sqlite3.connect("data/monnaies.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"SELECT id, {db_champ}, image_monnaie, image_gravure FROM monnaies WHERE id IN ({placeholders})",
                        ids)
                    fiches = {row[0]: row[1:] for row in cursor.fetchall()}
            except sqlite3.Error as e:
                messagebox.showerror("Erreur", f"Impossible de filtrer les résultats : {e}")
                return
            filtered_results = []
            for row in current_results:
                fiche = fiches.get(row[0])
                if fiche is None:
                    continue
                field_value = str(fiche[0]) if fiche[0] is not None else ""
                if self.match_recherche(field_value, valeur, type_recherche):
                    filtered_results.append(row)
            for row in self.tree_recherche.get_children():
                self.tree_recherche.delete(row)
            for i, row in enumerate(filtered_results):
                fiche_id = row[0]
                tags = ("even",) if i % 2 == 0 else ("odd",)
                self.tree_recherche.insert("", tk.END, values=row, iid=fiche_id, tags=tags)
                image_monnaie_blob, image_gravure_blob = fiches[fiche_id][1:]
                image_blob = image_monnaie_blob if image_monnaie_blob else image_gravure_blob
                if not image_blob:
                    continue
                try:
                    image = Image.open(io.BytesIO(image_blob))
                    image = image.resize((self.taille_miniature, self.taille_miniature), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                except Exception as e:
                    print(f"Erreur image pour ID {fiche_id}: {e}")
                    continue
                self.tree_images_recherche[fiche_id] = (photo, image_blob)
                self.tree_recherche.item(fiche_id, image=photo)

    @staticmethod
    def match_recherche(field_value, valeur, type_recherche):
        field_value = field_value.lower()
        valeur = valeur.lower()
        if type_recherche == "Identique":
            return field_value == valeur
        if type_recherche == "Commence par":
            return field_value.startswith(valeur)
        if type_recherche == "Contient":
            return valeur in field_value
        if type_recherche == "Finit par":
            return field_value.endswith(valeur)
        if type_recherche == "Ne contient pas":
            return valeur not in field_value
        return False

    def reorder_fiches(self):
        if not messagebox.askyesno(
                "Réordonner",
                "Voulez-vous vraiment reclasser toutes les fiches par période, valeur faciale et attribution ? "
                "L'ordre obtenu par insertion manuelle sera perdu."):
            return
        try:
            reorder_all_fiches()
        except sqlite3.Error as e:
            messagebox.showerror("Erreur", f"Impossible de réordonner les fiches : {e}")
            return
        self.load_data()

    def quit_app(self):
        if messagebox.askyesno("Quitter", "Voulez-vous vraiment quitter l'application ?"):
            self.root.destroy()


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    os.makedirs("images/gravures", exist_ok=True)
    os.makedirs("images/monnaies", exist_ok=True)
    init_db()
    root = tk.Tk()
    app = MonnaiesApp(root)
    root.mainloop()
