from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import application_root, load_config, profiles, save_config
from .dw import test_sql_connection
from .logging_config import configure_logging
from .models import CancellationToken, Coverage
from .orchestrator import Processor
from .discovery import discover_excel_files
from .reader import preview_mapping


class Application(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12); self.pack(fill="both", expand=True)
        self.config_data = load_config(); self.events = queue.Queue(); self.token = None; self.last_output = None
        root = application_root(); default_input = self.config_data.get("input_directory") or str(root); default_out = self.config_data.get("output_directory") or str(root / "resultados")
        self.input_var, self.output_var = tk.StringVar(value=default_input), tk.StringVar(value=default_out)
        self.source_var, self.profile_var, self.dw_file_var = tk.StringVar(value="none"), tk.StringVar(), tk.StringVar()
        self.coverage_start, self.coverage_end, self.coverage_description = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._build(); self.after(120, self._poll)

    def _build(self):
        self.master.title("Eventos Avulsos - Consolidação e Conflitos"); self.master.minsize(850, 620)
        def folder_row(label, var, command):
            frame = ttk.Frame(self); frame.pack(fill="x", pady=3); ttk.Label(frame, text=label, width=22).pack(side="left"); ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True); ttk.Button(frame, text="Selecionar pasta", command=command).pack(side="left", padx=(6,0))
        folder_row("Diretório de entrada", self.input_var, lambda: self.input_var.set(filedialog.askdirectory() or self.input_var.get()))
        folder_row("Diretório de saída", self.output_var, lambda: self.output_var.set(filedialog.askdirectory() or self.output_var.get()))
        frm = ttk.Frame(self); frm.pack(fill="x", pady=5); ttk.Label(frm, text="Perfil de template", width=22).pack(side="left"); self.profiles_box = ttk.Combobox(frm, textvariable=self.profile_var, state="readonly", values=[p.id for p in profiles(self.config_data)]); self.profiles_box.pack(side="left", fill="x", expand=True); self.profiles_box.current(0)
        source = ttk.LabelFrame(self, text="Fonte da verificação", padding=8); source.pack(fill="x", pady=5)
        for label, value in [("Somente consolidação", "none"), ("SQL Server", "sql"), ("Arquivo exportado do DW", "file")]: ttk.Radiobutton(source, text=label, variable=self.source_var, value=value).pack(side="left", padx=5)
        filefrm = ttk.Frame(self); filefrm.pack(fill="x", pady=3); ttk.Label(filefrm, text="Arquivo DW", width=22).pack(side="left"); ttk.Entry(filefrm, textvariable=self.dw_file_var).pack(side="left", fill="x", expand=True); ttk.Button(filefrm, text="Selecionar arquivo", command=lambda: self.dw_file_var.set(filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")]) or self.dw_file_var.get())).pack(side="left", padx=(6,0))
        cov = ttk.Frame(self); cov.pack(fill="x", pady=3); ttk.Label(cov, text="Cobertura DW (DD/MM/AAAA)", width=22).pack(side="left"); ttk.Entry(cov, textvariable=self.coverage_start, width=13).pack(side="left"); ttk.Label(cov, text="até").pack(side="left", padx=4); ttk.Entry(cov, textvariable=self.coverage_end, width=13).pack(side="left"); ttk.Entry(cov, textvariable=self.coverage_description).pack(side="left", fill="x", expand=True, padx=(6,0))
        actions = ttk.Frame(self); actions.pack(fill="x", pady=7)
        self.validate_btn = ttk.Button(actions, text="Validar arquivos", command=self.validate); self.validate_btn.pack(side="left")
        ttk.Button(actions, text="Prévia do mapeamento", command=self.preview).pack(side="left", padx=5)
        ttk.Button(actions, text="Configurar SQL", command=self.configure_sql).pack(side="left", padx=5)
        self.test_btn = ttk.Button(actions, text="Testar conexão", command=self.test_connection); self.test_btn.pack(side="left", padx=5)
        self.run_btn = ttk.Button(actions, text="Executar", command=self.run); self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=lambda: self.token and self.token.cancel(), state="disabled"); self.cancel_btn.pack(side="left", padx=5)
        self.open_report_btn = ttk.Button(actions, text="Abrir relatório", command=lambda: self.last_output and os.startfile(self.last_output), state="disabled"); self.open_report_btn.pack(side="right")
        ttk.Button(actions, text="Abrir pasta de resultados", command=lambda: os.startfile(self.output_var.get())).pack(side="right", padx=5)
        self.stage = tk.StringVar(value="Aguardando execução manual."); ttk.Label(self, textvariable=self.stage).pack(anchor="w")
        self.progress = ttk.Progressbar(self, mode="determinate"); self.progress.pack(fill="x", pady=3)
        self.log = tk.Text(self, height=18, state="disabled", wrap="word"); self.log.pack(fill="both", expand=True)

    def _profile(self): return next(p for p in profiles(self.config_data) if p.id == self.profile_var.get())
    def _coverage(self):
        from .normalize import parse_date
        start, end = parse_date(self.coverage_start.get()), parse_date(self.coverage_end.get())
        return Coverage(bool(start and end), start, end, self.coverage_description.get().strip())
    def _append(self, text): self.log.configure(state="normal"); self.log.insert("end", text + "\n"); self.log.see("end"); self.log.configure(state="disabled")
    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.stage.set(value[0] + (f" — {value[2]}" if value[2] else ""))
                    if value[1] is None:
                        if str(self.progress["mode"]) != "indeterminate": self.progress.configure(mode="indeterminate"); self.progress.start(10)
                    else:
                        self.progress.stop(); self.progress.configure(mode="determinate", value=value[1])
                elif kind == "log": self._append(value)
                elif kind == "done": self._finish(*value)
        except queue.Empty: pass
        self.after(120, self._poll)
    def validate(self):
        try:
            found, missing = Processor(self.config_data, configure_logging(Path(self.output_var.get()) / "logs", "validacao")).validate(Path(self.input_var.get()))
            messagebox.showinfo("Validação", "Encontradas: " + ", ".join(f.name for f, _ in found) + "\nAusentes: " + ", ".join(f.name for f in missing))
        except Exception as exc: messagebox.showerror("Validação", str(exc))
    def preview(self):
        try:
            found, _ = Processor(self.config_data, configure_logging(Path(self.output_var.get()) / "logs", "previa")).validate(Path(self.input_var.get()))
            for folder, folder_path in found:
                files, _ = discover_excel_files(folder_path)
                if files:
                    sheet, mapping, rows = preview_mapping(files[0], self._profile())
                    text = f"Arquivo: {files[0].name}\nAba: {sheet}\n\n" + "\n".join(f"{field}: {value}" for field, value in mapping.items()) + "\n\nPrimeiras linhas:\n" + "\n".join(str(row) for row in rows)
                    messagebox.showinfo("Prévia do mapeamento", text)
                    return
            raise ValueError("Nenhum arquivo elegível encontrado para prévia.")
        except Exception as exc: messagebox.showerror("Prévia", str(exc))
    def test_connection(self):
        def worker():
            try: test_sql_connection(self.config_data["sql"], os.environ.get("EVENTOS_AVULSOS_SQL_PASSWORD")); self.events.put(("done", (None, "Conexão SQL validada.")))
            except Exception as exc: self.events.put(("done", (None, f"Falha de conexão: {exc}")))
        threading.Thread(target=worker, daemon=True).start()
    def configure_sql(self):
        dialog = tk.Toplevel(self); dialog.title("Configuração SQL Server"); dialog.transient(self.master); dialog.grab_set(); dialog.resizable(False, False)
        fields = [("server", "Servidor"), ("database", "Banco"), ("authentication", "Autenticação (windows/sql)"), ("username", "Usuário SQL (se aplicável)"), ("odbc_driver", "Driver ODBC"), ("connect_timeout_seconds", "Timeout conexão (s)"), ("query_timeout_seconds", "Timeout consulta (s)")]
        variables = {}; sql = self.config_data["sql"]
        for row, (key, label) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
            variables[key] = tk.StringVar(value=str(sql.get(key, ""))); ttk.Entry(dialog, textvariable=variables[key], width=50).grid(row=row, column=1, padx=8, pady=4)
        encrypt = tk.BooleanVar(value=bool(sql.get("encrypt", True))); trust = tk.BooleanVar(value=bool(sql.get("trust_server_certificate", False)))
        ttk.Checkbutton(dialog, text="Criptografar conexão", variable=encrypt).grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=8)
        ttk.Checkbutton(dialog, text="Confiar no certificado (não recomendado)", variable=trust).grid(row=len(fields)+1, column=0, columnspan=2, sticky="w", padx=8)
        def save():
            try:
                sql.update({key: variable.get().strip() for key, variable in variables.items()})
                sql["connect_timeout_seconds"] = int(sql["connect_timeout_seconds"]); sql["query_timeout_seconds"] = int(sql["query_timeout_seconds"])
                sql["encrypt"], sql["trust_server_certificate"] = encrypt.get(), trust.get(); save_config(self.config_data); dialog.destroy()
            except ValueError: messagebox.showerror("Configuração SQL", "Os tempos limite devem ser números inteiros.", parent=dialog)
        ttk.Button(dialog, text="Salvar", command=save).grid(row=len(fields)+2, column=1, sticky="e", padx=8, pady=8)
    def run(self):
        self.token = CancellationToken(); self.run_btn.configure(state="disabled"); self.cancel_btn.configure(state="normal"); self.open_report_btn.configure(state="disabled"); self.progress["value"] = 0
        self.config_data["input_directory"], self.config_data["output_directory"] = self.input_var.get(), self.output_var.get(); save_config(self.config_data)
        def worker():
            execution_id = datetime.now().strftime("%Y%m%d%H%M%S")
            logger = configure_logging(Path(self.output_var.get()) / "logs", execution_id, lambda msg: self.events.put(("log", msg)))
            try:
                processor = Processor(self.config_data, logger, lambda stage, pct, current: self.events.put(("progress", (stage, pct, current))))
                result = processor.run(Path(self.input_var.get()), Path(self.output_var.get()), self._profile(), self.source_var.get(), Path(self.dw_file_var.get()) if self.dw_file_var.get() else None, self._coverage(), self.token, os.environ.get("EVENTOS_AVULSOS_SQL_PASSWORD"))
                summary = processor.last_summary
                message = f"{summary.status}. Letivas: {summary.letivas}; não letivas: {summary.nao_letivas}; conflitos: {summary.conflicts}; sem conflito: {summary.no_conflicts}; não verificados: {summary.not_verified}. Relatório: {result.name}"
                self.events.put(("done", (result, message)))
            except Exception as exc:
                message = "Execução cancelada." if self.token and self.token.is_cancelled else str(exc)
                self.events.put(("done", (None, message)))
        threading.Thread(target=worker, daemon=True).start()
    def _finish(self, path, message):
        self.last_output = path; self.run_btn.configure(state="normal"); self.cancel_btn.configure(state="disabled"); self.open_report_btn.configure(state="normal" if path else "disabled"); self.stage.set(message); self._append(message)


def main():
    root = tk.Tk(); Application(root); root.mainloop()
