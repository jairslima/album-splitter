"""
Album Splitter by Jair Lima - Divide um MP3 de CD Completo em faixas individuais.
"""

import json
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

import searcher
import splitter


# ─── Histórico ────────────────────────────────────────────────────────────────

_HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".albumsplitter_history.json")
_MAX_HISTORY = 10


def _load_history() -> list[dict]:
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(path: str):
    history = [h for h in _load_history() if h.get("path") != path]
    history.insert(0, {"path": path, "name": os.path.basename(path)})
    history = history[:_MAX_HISTORY]
    try:
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ─── Utilitários ──────────────────────────────────────────────────────────────

def parse_filename(path: str) -> tuple[str, str]:
    """Tenta extrair artista e álbum do nome do arquivo."""
    name = os.path.splitext(os.path.basename(path))[0]
    parts = re.split(r"\s*[｜|]\s*", name)
    parts = [p.strip() for p in parts if p.strip()
             and "CD Completo" not in p and "completo" not in p.lower()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if " - " in name:
        a, _, b = name.partition(" - ")
        return a.strip(), b.strip()
    return "", name


def seconds_to_mmss(s: int) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m}:{sec:02d}"


def mmss_to_seconds(text: str) -> int:
    text = text.strip()
    if ":" not in text:
        return -1
    parts = text.split(":")
    if len(parts) != 2:
        return -1
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return -1


# ─── Utilitário de escaneamento ──────────────────────────────────────────────

_COMPLETO_RE = re.compile(r"completo", re.IGNORECASE)


def scan_folder(folder: str) -> list[str]:
    found = []
    try:
        for name in os.listdir(folder):
            if name.lower().endswith(".mp3") and _COMPLETO_RE.search(name):
                found.append(os.path.join(folder, name))
    except OSError:
        pass
    return sorted(found)


# ─── Janela de escaneamento de pasta ─────────────────────────────────────────

class FolderScanner(tk.Toplevel):
    def __init__(self, parent, files: list[str]):
        super().__init__(parent)
        self.title("CDs Completos encontrados")
        self.resizable(True, False)
        self.result = None

        tk.Label(self, text=f"{len(files)} arquivo(s) encontrado(s). Selecione para carregar:",
                 padx=12, pady=8).pack(anchor="w")

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("Arquivo", "Pasta")
        tree = ttk.Treeview(frame, columns=cols, show="headings",
                            height=min(len(files), 12), selectmode="browse")
        tree.heading("Arquivo", text="Arquivo")
        tree.heading("Pasta", text="Pasta")
        tree.column("Arquivo", width=380)
        tree.column("Pasta", width=260)

        self._paths = {}
        for path in files:
            iid = tree.insert("", "end", values=(os.path.basename(path), os.path.dirname(path)))
            self._paths[iid] = path

        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._tree = tree
        tree.bind("<Double-1>", lambda _: self._select())

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Carregar", command=self._select, width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=10).pack(side="left", padx=4)

        self.grab_set()
        self.transient(parent)

    def _select(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um arquivo.", parent=self)
            return
        self.result = self._paths[sel[0]]
        self.destroy()


# ─── Janela de busca de releases ─────────────────────────────────────────────

class ReleaseChooser(tk.Toplevel):
    def __init__(self, parent, releases: list[dict]):
        super().__init__(parent)
        self.title("Selecionar versão do álbum")
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text="Múltiplas versões encontradas. Selecione a correta:",
                 padx=12, pady=8).pack(anchor="w")

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12)

        cols = ("Título", "Artista", "Ano", "Faixas")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=min(len(releases), 8))
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Título", width=220)
        tree.column("Artista", width=180)
        tree.column("Ano", width=60)
        tree.column("Faixas", width=55)

        for r in releases:
            tree.insert("", "end", iid=r["id"],
                        values=(r["title"], r["artist"], r["date"], r["track_count"]))
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._tree = tree
        self._releases = {r["id"]: r for r in releases}

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Selecionar", command=self._select, width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=10).pack(side="left", padx=4)

        self.grab_set()
        self.transient(parent)

    def _select(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione uma versão.", parent=self)
            return
        self.result = self._releases[sel[0]]
        self.destroy()


# ─── App principal ────────────────────────────────────────────────────────────

_AppBase = TkinterDnD.Tk if _HAS_DND else tk.Tk


class App(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("Album Splitter by Jair Lima")
        self.resizable(True, True)
        self.minsize(700, 600)

        self._mp3_duration: int | None = None  # duração real do MP3 em segundos

        self._build_menu()
        self._build_ui()

        self._ffmpeg = splitter.find_ffmpeg()
        if not self._ffmpeg:
            messagebox.showwarning(
                "ffmpeg não encontrado",
                "Coloque ffmpeg.exe na pasta do app ou adicione ao PATH.\n"
                "Download: https://ffmpeg.org/download.html"
            )

        if _HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        self._recent_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Recentes", menu=self._recent_menu)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self._recent_menu.delete(0, "end")
        history = _load_history()
        if not history:
            self._recent_menu.add_command(label="(nenhum histórico)", state="disabled")
            return
        for entry in history:
            path = entry["path"]
            name = entry["name"]
            self._recent_menu.add_command(
                label=name,
                command=lambda p=path: self._load_mp3(p)
            )
        self._recent_menu.add_separator()
        self._recent_menu.add_command(label="Limpar histórico", command=self._clear_history)

    def _clear_history(self):
        try:
            os.remove(_HISTORY_FILE)
        except Exception:
            pass
        self._refresh_recent_menu()

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ── Arquivo MP3 ──
        f1 = tk.LabelFrame(self, text=" Arquivo MP3 (CD Completo) ", padx=8, pady=6)
        f1.pack(fill="x", padx=12, pady=(10, 4))

        self._mp3_var = tk.StringVar()
        tk.Entry(f1, textvariable=self._mp3_var, width=60).pack(side="left", fill="x", expand=True)
        tk.Button(f1, text="Procurar…", command=self._browse_mp3).pack(side="left", padx=(6, 0))
        tk.Button(f1, text="Escanear Pasta…", command=self._scan_folder).pack(side="left", padx=(4, 0))

        if _HAS_DND:
            tk.Label(f1, text="(ou arraste o MP3 aqui)", fg="gray", font=("Segoe UI", 8)
                     ).pack(side="left", padx=(8, 0))

        # ── Metadados ──
        f2 = tk.LabelFrame(self, text=" Informações do Álbum ", padx=8, pady=6)
        f2.pack(fill="x", padx=12, pady=4)

        tk.Label(f2, text="Artista:").grid(row=0, column=0, sticky="e", **pad)
        self._artist_var = tk.StringVar()
        tk.Entry(f2, textvariable=self._artist_var, width=35).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(f2, text="Álbum:").grid(row=0, column=2, sticky="e", **pad)
        self._album_var = tk.StringVar()
        tk.Entry(f2, textvariable=self._album_var, width=35).grid(row=0, column=3, sticky="w", **pad)

        tk.Label(f2, text="Ano:").grid(row=1, column=0, sticky="e", **pad)
        self._year_var = tk.StringVar()
        tk.Entry(f2, textvariable=self._year_var, width=8).grid(row=1, column=1, sticky="w", **pad)

        tk.Button(f2, text="🔍  Buscar Tracklist (MusicBrainz)",
                  command=self._search_thread).grid(row=1, column=2, columnspan=2, sticky="w", **pad)

        # ── Tracklist ──
        f3 = tk.LabelFrame(self, text=" Faixas ", padx=8, pady=6)
        f3.pack(fill="both", expand=True, padx=12, pady=4)

        cols = ("#", "Título", "Duração (M:SS)")
        self._tree = ttk.Treeview(f3, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("#", text="#")
        self._tree.heading("Título", text="Título")
        self._tree.heading("Duração (M:SS)", text="Duração (M:SS)")
        self._tree.column("#", width=40, anchor="center")
        self._tree.column("Título", width=400)
        self._tree.column("Duração (M:SS)", width=100, anchor="center")
        self._tree.tag_configure("zero_dur", foreground="red")
        self._tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(f3, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._edit_row)

        # Botões da tabela + total
        btn_row = tk.Frame(self)
        btn_row.pack(fill="x", padx=12, pady=(0, 4))
        tk.Button(btn_row, text="+ Adicionar faixa", command=self._add_row).pack(side="left", padx=2)
        tk.Button(btn_row, text="✕ Remover", command=self._remove_row).pack(side="left", padx=2)
        tk.Button(btn_row, text="▲ Subir", command=lambda: self._move_row(-1)).pack(side="left", padx=2)
        tk.Button(btn_row, text="▼ Descer", command=lambda: self._move_row(1)).pack(side="left", padx=2)
        tk.Button(btn_row, text="Limpar tudo", command=self._clear_rows).pack(side="right", padx=2)

        self._total_lbl = tk.Label(btn_row, text="", fg="#555555", font=("Segoe UI", 9))
        self._total_lbl.pack(side="right", padx=8)

        # ── Saída ──
        f4 = tk.LabelFrame(self, text=" Pasta de Saída ", padx=8, pady=6)
        f4.pack(fill="x", padx=12, pady=4)

        self._out_var = tk.StringVar()
        tk.Entry(f4, textvariable=self._out_var, width=60).pack(side="left", fill="x", expand=True)
        tk.Button(f4, text="Procurar…", command=self._browse_out).pack(side="left", padx=(6, 0))

        # ── Botão principal ──
        self._split_btn = tk.Button(self, text="✂  Dividir Álbum",
                                    command=self._split_thread,
                                    font=("Segoe UI", 11, "bold"),
                                    bg="#2d6a4f", fg="white", activebackground="#1b4332",
                                    padx=16, pady=6)
        self._split_btn.pack(pady=(4, 2))

        # ── Barra de progresso ──
        self._progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self._progress.pack(fill="x", padx=12, pady=(0, 4))

        # ── Log ──
        self._log = tk.Text(self, height=5, state="disabled", bg="#1e1e1e", fg="#d4d4d4",
                            font=("Consolas", 9))
        self._log.pack(fill="x", padx=12, pady=(0, 10))

    # ── Drag and drop ─────────────────────────────────────────────────────────

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        if path.lower().endswith(".mp3") and os.path.isfile(path):
            self._load_mp3(path)
        else:
            messagebox.showwarning("Arquivo inválido", "Arraste apenas arquivos MP3.")

    # ── Ações de arquivo ─────────────────────────────────────────────────────

    def _browse_mp3(self):
        path = filedialog.askopenfilename(
            title="Selecionar MP3",
            filetypes=[("Arquivos MP3", "*.mp3"), ("Todos", "*.*")]
        )
        if path:
            self._load_mp3(path)

    def _browse_out(self):
        path = filedialog.askdirectory(title="Selecionar pasta de saída")
        if path:
            self._out_var.set(path)

    def _load_mp3(self, path: str):
        self._mp3_var.set(path)
        artist, album = parse_filename(path)
        if artist:
            self._artist_var.set(artist)
        if album:
            self._album_var.set(album)
        self._clear_rows()
        folder = os.path.join(os.path.dirname(path), f"{artist} - {album}".strip(" -"))
        self._out_var.set(folder)
        _save_history(path)
        self._refresh_recent_menu()

        # Duração real do MP3 via ffprobe (em background)
        self._mp3_duration = None
        self._update_total()
        threading.Thread(target=self._probe_mp3, args=(path,), daemon=True).start()

        # Busca automática no MusicBrainz se artista e álbum foram extraídos
        if artist and album:
            self._log_write(f"Carregado: {os.path.basename(path)}")
            self._search_thread()

    def _probe_mp3(self, path: str):
        dur = splitter.get_mp3_duration(path, self._ffmpeg)
        self._mp3_duration = dur
        self.after(0, self._update_total)
        if dur:
            self._log_write(f"Duração do MP3: {seconds_to_mmss(dur)}")

    def _scan_folder(self):
        folder = filedialog.askdirectory(title="Selecionar pasta para escanear")
        if not folder:
            return
        files = scan_folder(folder)
        if not files:
            messagebox.showinfo("Nenhum resultado",
                                "Nenhum MP3 com 'completo' no nome foi encontrado nessa pasta.")
            return
        dlg = FolderScanner(self, files)
        self.wait_window(dlg)
        if dlg.result:
            self._load_mp3(dlg.result)

    # ── Busca de tracklist ───────────────────────────────────────────────────

    def _search_thread(self):
        artist = self._artist_var.get().strip()
        album = self._album_var.get().strip()
        if not artist or not album:
            messagebox.showwarning("Atenção", "Preencha Artista e Álbum antes de buscar.")
            return
        self._log_write(f"Buscando '{album}' de '{artist}' no MusicBrainz…")
        threading.Thread(target=self._do_search, args=(artist, album), daemon=True).start()

    def _do_search(self, artist: str, album: str):
        try:
            releases = searcher.search_releases(artist, album)
            if not releases:
                self._log_write("Nenhum resultado encontrado. Adicione as faixas manualmente.")
                return

            if len(releases) == 1:
                mbid = releases[0]["id"]
            else:
                mbid = self._ask_release(releases)
                if not mbid:
                    self._log_write("Busca cancelada.")
                    return

            self._log_write("Baixando tracklist…")
            tracks = searcher.get_tracklist(mbid)
            if not tracks:
                self._log_write("Tracklist vazia. Adicione as faixas manualmente.")
                return

            self.after(0, lambda: self._load_tracks(tracks))
            self._log_write(f"{len(tracks)} faixas carregadas.")
        except Exception as e:
            self._log_write(f"Erro na busca: {e}")

    def _ask_release(self, releases):
        result = [None]
        event = threading.Event()

        def show():
            dlg = ReleaseChooser(self, releases)
            self.wait_window(dlg)
            result[0] = dlg.result["id"] if dlg.result else None
            event.set()

        self.after(0, show)
        event.wait()
        return result[0]

    def _load_tracks(self, tracks: list[tuple[str, int]]):
        self._clear_rows()
        for title, secs in tracks:
            dur_str = seconds_to_mmss(secs) if secs else "0:00"
            num = len(self._tree.get_children()) + 1
            tag = "zero_dur" if not secs else ""
            self._tree.insert("", "end", values=(num, title, dur_str), tags=(tag,))

        self._update_total()

        zero_count = sum(1 for _, s in tracks if not s)
        if zero_count > 0:
            self._log_write(
                f"Atenção: {zero_count} faixa(s) marcadas em vermelho com duração 0:00 — "
                "o MusicBrainz não tem essa informação. Preencha manualmente (duplo clique)."
            )

        if len(tracks) >= 2:
            last_dur = tracks[-1][1]
            others_sum = sum(s for _, s in tracks[:-1])
            if others_sum > 0 and last_dur > others_sum:
                self._log_write(
                    f"Atenção: a última faixa ({seconds_to_mmss(last_dur)}) é maior que a soma das demais "
                    f"({seconds_to_mmss(others_sum)}). Os dados podem estar incorretos — verifique as durações."
                )

    # ── Total de duração ─────────────────────────────────────────────────────

    def _update_total(self):
        children = self._tree.get_children()
        n = len(children)
        total_secs = 0
        for iid in children:
            vals = self._tree.item(iid, "values")
            s = mmss_to_seconds(vals[2]) if len(vals) > 2 else 0
            total_secs += max(s, 0)

        parts = [f"{n} faixa{'s' if n != 1 else ''}"]
        if n > 0:
            parts.append(f"Tracklist: {seconds_to_mmss(total_secs)}")
        if self._mp3_duration:
            parts.append(f"MP3: {seconds_to_mmss(self._mp3_duration)}")
            if n > 0:
                diff = abs(self._mp3_duration - total_secs)
                if diff > 10:
                    parts.append(f"⚠ Dif: {seconds_to_mmss(diff)}")

        self._total_lbl.config(text="  |  ".join(parts))

    # ── Edição da tabela ─────────────────────────────────────────────────────

    def _edit_row(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        values = self._tree.item(iid, "values")
        dlg = _TrackEditor(self, values[1], values[2])
        self.wait_window(dlg)
        if dlg.result:
            title, dur = dlg.result
            tag = "zero_dur" if mmss_to_seconds(dur) == 0 else ""
            self._tree.item(iid, values=(values[0], title, dur), tags=(tag,))
            self._update_total()

    def _add_row(self):
        dlg = _TrackEditor(self, "", "0:00")
        self.wait_window(dlg)
        if dlg.result:
            title, dur = dlg.result
            num = len(self._tree.get_children()) + 1
            tag = "zero_dur" if mmss_to_seconds(dur) == 0 else ""
            self._tree.insert("", "end", values=(num, title, dur), tags=(tag,))
            self._update_total()

    def _remove_row(self):
        sel = self._tree.selection()
        if sel:
            self._tree.delete(sel[0])
            self._renumber()
            self._update_total()

    def _move_row(self, direction: int):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        children = list(self._tree.get_children())
        idx = children.index(iid)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(children):
            return
        a_vals = self._tree.item(children[idx], "values")
        a_tags = self._tree.item(children[idx], "tags")
        b_vals = self._tree.item(children[new_idx], "values")
        b_tags = self._tree.item(children[new_idx], "tags")
        self._tree.item(children[idx], values=(a_vals[0], b_vals[1], b_vals[2]), tags=b_tags)
        self._tree.item(children[new_idx], values=(b_vals[0], a_vals[1], a_vals[2]), tags=a_tags)
        self._tree.selection_set(children[new_idx])

    def _clear_rows(self):
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._update_total()

    def _renumber(self):
        for i, iid in enumerate(self._tree.get_children()):
            vals = self._tree.item(iid, "values")
            self._tree.item(iid, values=(i + 1, vals[1], vals[2]))

    # ── Divisão ──────────────────────────────────────────────────────────────

    def _split_thread(self):
        mp3 = self._mp3_var.get().strip()
        out = self._out_var.get().strip()
        artist = self._artist_var.get().strip()
        album = self._album_var.get().strip()
        year = self._year_var.get().strip()

        if not mp3 or not os.path.isfile(mp3):
            messagebox.showerror("Erro", "Selecione um arquivo MP3 válido.")
            return
        if not out:
            messagebox.showerror("Erro", "Selecione a pasta de saída.")
            return
        children = self._tree.get_children()
        if not children:
            messagebox.showerror("Erro", "Adicione ao menos uma faixa.")
            return

        tracks = []
        for iid in children:
            vals = self._tree.item(iid, "values")
            title = vals[1]
            secs = mmss_to_seconds(vals[2])
            if secs < 0:
                messagebox.showerror("Erro", f"Duração inválida na faixa '{title}': '{vals[2]}'.\nUse o formato M:SS.")
                return
            tracks.append((title, secs))

        # Última faixa muito maior que a soma das outras = dados suspeitos
        if len(tracks) >= 2:
            last_dur = tracks[-1][1]
            others_sum = sum(s for _, s in tracks[:-1])
            if others_sum > 0 and last_dur > others_sum:
                resp = messagebox.askyesno(
                    "Dados suspeitos",
                    f"A última faixa '{tracks[-1][0]}' tem duração {seconds_to_mmss(last_dur)}, "
                    f"maior que a soma de todas as outras ({seconds_to_mmss(others_sum)}).\n\n"
                    "Isso indica que os dados do MusicBrainz estão incorretos para este álbum.\n\n"
                    "Deseja continuar mesmo assim?"
                )
                if not resp:
                    return

        # Faixas intermediárias com duração 0 causam arquivos vazios
        zero_tracks = [t[0] for t in tracks[:-1] if t[1] == 0]
        if zero_tracks:
            nomes = "\n".join(f"  • {n}" for n in zero_tracks[:5])
            if len(zero_tracks) > 5:
                nomes += f"\n  … e mais {len(zero_tracks) - 5}"
            resp = messagebox.askyesno(
                "Durações zeradas",
                f"{len(zero_tracks)} faixa(s) têm duração 0:00:\n{nomes}\n\n"
                "Isso vai gerar arquivos vazios para essas faixas e jogar todo o áudio na última faixa.\n\n"
                "Preencha as durações e tente novamente. Deseja continuar mesmo assim?"
            )
            if not resp:
                return

        if not self._ffmpeg:
            messagebox.showerror("Erro", "ffmpeg não encontrado.")
            return

        self._split_btn.config(state="disabled", text="Dividindo…")
        threading.Thread(
            target=self._do_split,
            args=(mp3, tracks, out, artist, album, year),
            daemon=True
        ).start()

    def _do_split(self, mp3, tracks, out, artist, album, year):
        try:
            total_tracks = len(tracks)
            self.after(0, lambda: self._progress.configure(maximum=total_tracks, value=0))

            def progress(current, total, msg):
                self._log_write(msg)
                self.after(0, lambda v=current: self._progress.configure(value=v))

            files = splitter.split_album(
                input_mp3=mp3,
                tracks=tracks,
                output_dir=out,
                artist=artist,
                album=album,
                year=year,
                ffmpeg_path=self._ffmpeg,
                progress_cb=progress,
            )
            self._log_write(f"\n✓ Concluído! {len(files)} faixas salvas em:\n  {out}")

            def _on_done():
                msg = (f"{len(files)} faixas criadas com sucesso!\n\n{out}\n\n"
                       "Deseja apagar o arquivo de origem?")
                resp = messagebox.askyesno("Concluído", msg)
                if resp:
                    try:
                        os.remove(mp3)
                        self._log_write(f"Arquivo de origem apagado: {os.path.basename(mp3)}")
                    except Exception as e:
                        messagebox.showerror("Erro", f"Não foi possível apagar o arquivo:\n{e}")
                if messagebox.askyesno("Abrir pasta", "Deseja abrir a pasta de saída?"):
                    os.startfile(out)

            self.after(0, _on_done)
        except Exception as e:
            self._log_write(f"ERRO: {e}")
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))
        finally:
            self.after(0, lambda: self._split_btn.config(state="normal", text="✂  Dividir Álbum"))
            self.after(0, lambda: self._progress.configure(value=0))

    # ── Log ──────────────────────────────────────────────────────────────────

    def _log_write(self, msg: str):
        def _write():
            self._log.config(state="normal")
            self._log.insert("end", msg.rstrip() + "\n")
            self._log.see("end")
            self._log.config(state="disabled")
        self.after(0, _write)


# ─── Diálogo de edição de faixa ──────────────────────────────────────────────

class _TrackEditor(tk.Toplevel):
    def __init__(self, parent, title: str, dur: str):
        super().__init__(parent)
        self.title("Editar faixa")
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text="Título:").grid(row=0, column=0, padx=10, pady=(12, 4), sticky="e")
        self._title = tk.Entry(self, width=40)
        self._title.insert(0, title)
        self._title.grid(row=0, column=1, padx=10, pady=(12, 4))

        tk.Label(self, text="Duração (M:SS):").grid(row=1, column=0, padx=10, pady=4, sticky="e")
        self._dur = tk.Entry(self, width=10)
        self._dur.insert(0, dur)
        self._dur.grid(row=1, column=1, padx=10, pady=4, sticky="w")

        tk.Label(self, text="Ex: 4:03 ou 14:30", fg="gray").grid(row=2, column=1, sticky="w", padx=10)

        btn = tk.Frame(self)
        btn.grid(row=3, column=0, columnspan=2, pady=10)
        tk.Button(btn, text="OK", command=self._ok, width=10).pack(side="left", padx=4)
        tk.Button(btn, text="Cancelar", command=self.destroy, width=10).pack(side="left", padx=4)

        self._title.focus_set()
        self.bind("<Return>", lambda _: self._ok())
        self.grab_set()
        self.transient(parent)

    def _ok(self):
        t = self._title.get().strip()
        d = self._dur.get().strip()
        if not t:
            messagebox.showwarning("Atenção", "Título não pode ser vazio.", parent=self)
            return
        if mmss_to_seconds(d) < 0:
            messagebox.showwarning("Atenção", "Duração inválida. Use M:SS (ex: 4:03).", parent=self)
            return
        self.result = (t, d)
        self.destroy()


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
