#!/usr/bin/env python3
"""
Mini OCR (équivalent de TEXTEMAGE) basé sur Tesseract.
Supporte toutes les langues installées dans Tesseract (coréen, japonais, etc.).

Dépendances :
    pip install pytesseract pillow
Et Tesseract lui-même + les fichiers de langue (voir README ci-dessous).
"""
import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pytesseract
from PIL import Image, ImageGrab, ImageOps, ImageTk

# --------------------------------------------------------------------------
# Détection de Tesseract
# --------------------------------------------------------------------------
WINDOWS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def find_tesseract():
    """Retourne le chemin de l'exécutable tesseract, ou None."""
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("tesseract")
    if found:
        return found
    for p in WINDOWS_PATHS:
        if os.path.isfile(p):
            return p
    return None


PSM_MODES = {
    "Automatique (3)": 3,
    "Un seul bloc de texte (6)": 6,
    "Une seule ligne (7)": 7,
    "Texte épars (11)": 11,
}


# Seuil de confiance minimum de l'OSD avant de tenter la méthode de secours
OSD_MIN_CONF = 1.0

# Écriture (nom renvoyé par l'OSD / nom du modèle script/) -> langues Tesseract proposées
SCRIPT_TO_LANGS = {
    "Arabic": ["ara"], "Armenian": ["hye"], "Bengali": ["ben"],
    "Canadian_Aboriginal": ["iku"], "Cherokee": ["chr"], "Cyrillic": ["rus"],
    "Devanagari": ["hin"], "Ethiopic": ["amh"], "Fraktur": [], "Georgian": ["kat"],
    "Greek": ["ell"], "Gujarati": ["guj"], "Gurmukhi": ["pan"],
    "Han": ["chi_sim", "chi_tra"], "HanS": ["chi_sim"], "HanT": ["chi_tra"],
    "Hangul": ["kor"], "Hebrew": ["heb"], "Japanese": ["jpn"], "Kannada": ["kan"],
    "Khmer": ["khm"], "Lao": ["lao"], "Latin": ["eng"], "Malayalam": ["mal"],
    "Myanmar": ["mya"], "Oriya": ["ori"], "Sinhala": ["sin"], "Syriac": ["syr"],
    "Tamil": ["tam"], "Telugu": ["tel"], "Thaana": ["div"], "Thai": ["tha"],
    "Tibetan": ["bod"], "Vietnamese": ["vie"],
}

SCRIPT_LABELS = {
    "Hangul": "coréen (Hangul)", "Han": "chinois (Han)", "HanS": "chinois simplifié",
    "HanT": "chinois traditionnel", "Japanese": "japonais",
    "Devanagari": "devanagari (hindi, marathi, népalais…)", "Latin": "latin",
    "Cyrillic": "cyrillique", "Arabic": "arabe", "Greek": "grec", "Hebrew": "hébreu",
    "Thai": "thaï", "Tamil": "tamoul", "Bengali": "bengali", "Telugu": "télougou",
    "Kannada": "kannada", "Malayalam": "malayalam", "Gujarati": "gujarati",
    "Gurmukhi": "gurmukhi (pendjabi)", "Khmer": "khmer", "Lao": "lao",
    "Myanmar": "birman", "Tibetan": "tibétain", "Georgian": "géorgien",
    "Armenian": "arménien", "Ethiopic": "éthiopien", "Sinhala": "cingalais",
}


class OcrApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mini OCR – Tesseract")
        self.geometry("980x620")
        self.minsize(760, 460)

        self.image = None          # image PIL courante
        self.photo = None          # référence ImageTk (évite le garbage collect)

        if not self._setup_tesseract():
            self.destroy()
            return

        self._build_ui()
        self._load_languages()
        self.bind("<Control-v>", lambda e: self.paste_image())

    # ------------------------------------------------------------------
    def _setup_tesseract(self):
        path = find_tesseract()
        if not path:
            messagebox.showinfo(
                "Tesseract introuvable",
                "Tesseract n'a pas été trouvé automatiquement.\n"
                "Sélectionnez tesseract.exe (ou le binaire tesseract).",
            )
            path = filedialog.askopenfilename(title="Localiser tesseract")
            if not path:
                return False
        pytesseract.pytesseract.tesseract_cmd = path
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            messagebox.showerror("Erreur Tesseract", str(exc))
            return False
        return True

    # ------------------------------------------------------------------
    def _build_ui(self):
        # Barre d'outils
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="Ouvrir une image…", command=self.open_image).pack(side="left")
        ttk.Button(bar, text="Coller (Ctrl+V)", command=self.paste_image).pack(side="left", padx=4)
        self.detect_btn = ttk.Button(bar, text="Détecter l'écriture", command=self.detect_script)
        self.detect_btn.pack(side="left", padx=4)
        self.run_btn = ttk.Button(bar, text="Lancer l'OCR", command=self.run_ocr)
        self.run_btn.pack(side="left", padx=4)
        ttk.Button(bar, text="Copier le texte", command=self.copy_text).pack(side="left", padx=4)
        ttk.Button(bar, text="Enregistrer…", command=self.save_text).pack(side="left", padx=4)

        # Corps
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Colonne gauche : langues + options + aperçu
        left = ttk.Frame(body, padding=4)
        body.add(left, weight=1)

        ttk.Label(left, text="Langues (Ctrl/Maj pour plusieurs) :").pack(anchor="w")
        lang_frame = ttk.Frame(left)
        lang_frame.pack(fill="x")
        self.lang_list = tk.Listbox(lang_frame, selectmode="extended", height=8, exportselection=False)
        sb = ttk.Scrollbar(lang_frame, orient="vertical", command=self.lang_list.yview)
        self.lang_list.configure(yscrollcommand=sb.set)
        self.lang_list.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")

        ttk.Label(left, text="Mode de segmentation :").pack(anchor="w", pady=(8, 0))
        self.psm_var = tk.StringVar(value=list(PSM_MODES)[0])
        ttk.Combobox(left, textvariable=self.psm_var, values=list(PSM_MODES),
                     state="readonly").pack(fill="x")

        self.enhance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Améliorer l'image (niveaux de gris, contraste, agrandissement)",
                        variable=self.enhance_var).pack(anchor="w", pady=(8, 0))

        self.preview = ttk.Label(left, anchor="center", relief="sunken")
        self.preview.pack(fill="both", expand=True, pady=(8, 0))

        # Colonne droite : texte
        right = ttk.Frame(body, padding=4)
        body.add(right, weight=2)
        self.text = tk.Text(right, wrap="word", font=("TkDefaultFont", 12), undo=True)
        tsb = ttk.Scrollbar(right, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=tsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")

        # Barre de statut
        self.status = tk.StringVar(value="Ouvrez ou collez une image.")
        ttk.Label(self, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x")

    def _load_languages(self):
        self.has_osd = False
        try:
            all_langs = pytesseract.get_languages(config="")
            self.has_osd = "osd" in all_langs
            langs = sorted(l for l in all_langs if l != "osd")
        except Exception:
            langs = ["eng"]
        for l in langs:
            self.lang_list.insert("end", l)
        # Présélection : coréen + anglais s'ils sont installés, sinon anglais
        wanted = [l for l in ("kor", "eng") if l in langs] or langs[:1]
        for l in wanted:
            self.lang_list.selection_set(langs.index(l))
        if "kor" not in langs:
            self.status.set("⚠ Le coréen (kor) n'est pas installé dans Tesseract – voir les instructions.")

    # ------------------------------------------------------------------
    # Chargement des images
    # ------------------------------------------------------------------
    def _set_image(self, img, source):
        self.image = img
        thumb = img.copy()
        thumb.thumbnail((380, 380))
        self.photo = ImageTk.PhotoImage(thumb)
        self.preview.configure(image=self.photo)
        self.status.set(f"Image chargée ({source}) – {img.width}×{img.height}px")

    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif"),
                       ("Tous les fichiers", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir l'image :\n{exc}")
            return
        self._set_image(img, os.path.basename(path))

    def paste_image(self):
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:
            messagebox.showerror("Presse-papiers", str(exc))
            return
        if isinstance(data, Image.Image):
            self._set_image(data, "presse-papiers")
        elif isinstance(data, list) and data:  # fichiers copiés
            try:
                img = Image.open(data[0])
                img.load()
                self._set_image(img, os.path.basename(data[0]))
            except Exception:
                self.status.set("Le presse-papiers ne contient pas d'image.")
        else:
            self.status.set("Le presse-papiers ne contient pas d'image.")

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    def _prepare(self, img):
        img = img.convert("RGB")
        if not self.enhance_var.get():
            return img
        gray = ImageOps.grayscale(img)
        gray = ImageOps.autocontrast(gray)
        if gray.width < 1500:  # Tesseract aime les caractères assez grands
            factor = 2 if gray.width >= 750 else 3
            gray = gray.resize((gray.width * factor, gray.height * factor), Image.LANCZOS)
        return gray

    def run_ocr(self):
        if self.image is None:
            messagebox.showinfo("OCR", "Chargez d'abord une image.")
            return
        sel = [self.lang_list.get(i) for i in self.lang_list.curselection()]
        if not sel:
            messagebox.showinfo("OCR", "Sélectionnez au moins une langue.")
            return
        lang = "+".join(sel)
        config = f"--psm {PSM_MODES[self.psm_var.get()]}"
        img = self._prepare(self.image)

        self.run_btn.state(["disabled"])
        self.status.set(f"OCR en cours ({lang})…")

        def work():
            try:
                result = pytesseract.image_to_string(img, lang=lang, config=config)
                self.after(0, lambda r=result.strip(): self._done(r, None))
            except Exception as exc:
                self.after(0, lambda e=exc: self._done(None, e))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, result, error):
        self.run_btn.state(["!disabled"])
        if error:
            self.status.set("Erreur pendant l'OCR.")
            messagebox.showerror("Erreur OCR", str(error))
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", result)
        self.status.set(f"Terminé – {len(result)} caractères reconnus.")

    # ------------------------------------------------------------------
    # Détection de l'écriture
    # ------------------------------------------------------------------
    def detect_script(self):
        if self.image is None:
            messagebox.showinfo("Détection", "Chargez d'abord une image.")
            return
        installed = list(self.lang_list.get(0, "end"))
        img = self._prepare(self.image)
        self.detect_btn.state(["disabled"])
        self.status.set("Détection de l'écriture en cours…")

        def work():
            try:
                res = self._detect(img, installed)
                self.after(0, lambda r=res: self._detect_done(r, None))
            except Exception as exc:
                self.after(0, lambda e=exc: self._detect_done(None, e))

        threading.Thread(target=work, daemon=True).start()

    def _detect(self, img, installed):
        """1) OSD de Tesseract ; 2) sinon comparaison des modèles script/*."""
        weak = None
        if self.has_osd:
            try:
                d = pytesseract.image_to_osd(
                    img, config="--psm 0", output_type=pytesseract.Output.DICT)
                res = {"script": d["script"], "conf": float(d["script_conf"]),
                       "rotate": int(d["rotate"]), "method": "OSD"}
                if res["conf"] >= OSD_MIN_CONF:
                    return res
                weak = res
            except Exception:
                pass  # trop peu de texte, image trop petite, etc.

        # Méthode de secours : on lance chaque modèle d'écriture et on garde
        # celui qui reconnaît le plus de caractères avec confiance.
        models = [m for m in installed if m.startswith("script/") and not m.endswith("_vert")]
        if models:
            best, best_score = None, 0.0
            for m in models:
                data = pytesseract.image_to_data(
                    img, lang=m, config="--psm 3", output_type=pytesseract.Output.DICT)
                score = 0.0
                for txt, conf in zip(data["text"], data["conf"]):
                    txt = txt.strip()
                    conf = float(conf)
                    if txt and conf > 0:
                        score += conf * len(txt)
                if score > best_score:
                    best, best_score = m, score
            if best:
                return {"script": best.split("/", 1)[1], "conf": None, "rotate": 0,
                        "method": "comparaison des modèles script/"}

        if weak:
            return weak
        raise RuntimeError(
            "Détection impossible : texte insuffisant, ou ni 'osd' ni les modèles "
            "'script/…' ne sont installés dans Tesseract.")

    def _detect_done(self, res, error):
        self.detect_btn.state(["!disabled"])
        if error:
            self.status.set("Détection impossible.")
            messagebox.showerror("Détection de l'écriture", str(error))
            return

        script = res["script"]
        installed = list(self.lang_list.get(0, "end"))
        wanted = SCRIPT_TO_LANGS.get(script, [])
        available = [l for l in wanted if l in installed]
        missing = [l for l in wanted if l not in installed]
        # À défaut de pack de langue, on utilise le modèle d'écriture s'il existe
        if not available and f"script/{script}" in installed:
            available = [f"script/{script}"]
        # Les textes mixtes sont fréquents : on ajoute l'anglais pour les autres écritures
        if script != "Latin" and "eng" in installed and "eng" not in available:
            available.append("eng")

        self.lang_list.selection_clear(0, "end")
        for l in available:
            idx = installed.index(l)
            self.lang_list.selection_set(idx)
            self.lang_list.see(idx)

        label = SCRIPT_LABELS.get(script, script)
        details = res["method"]
        if res["conf"] is not None:
            details += f", confiance {res['conf']:.1f}"
        msg = f"Écriture détectée : {label} ({details}) → langues : {'+'.join(available) or 'aucune'}"
        if res["rotate"]:
            msg += f" – image à pivoter de {res['rotate']}°"
        if script == "Latin":
            msg += " – la langue exacte n'est pas détectable, ajustez la sélection"
        elif script == "Han":
            msg += " – si c'est du japonais, ajoutez jpn"
        self.status.set(msg)

        if missing:
            messagebox.showwarning(
                "Pack de langue manquant",
                f"Écriture détectée : {label}.\n\n"
                f"Il manque le(s) pack(s) : {', '.join(missing)}\n"
                "Installez-les puis relancez l'application.")

    # ------------------------------------------------------------------
    # Sortie
    # ------------------------------------------------------------------
    def copy_text(self):
        content = self.text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status.set("Texte copié dans le presse-papiers.")

    def save_text(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Texte", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end").strip())
            self.status.set(f"Enregistré : {path}")


if __name__ == "__main__":
    app = OcrApp()
    if app.winfo_exists():
        app.mainloop()
