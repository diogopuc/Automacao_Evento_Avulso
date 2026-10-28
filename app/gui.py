from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import application_root, load_config, profiles, save_config
from .dw import inspect_dw_export
from .logging_config import configure_logging
from .models import CancellationToken, Coverage
from .orchestrator import Processor
from .discovery import discover_excel_files
from .reader import preview_mapping


class Application(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12); self.pack(fill="both", expand=True)
        self.config_data = load_config(); self.events = queue.Queue(); self.token = None; self.last_output = None
        self.running = False; self.run_started_at = None
        root = application_root(); default_input = self.config_data.get("input_directory") or str(root); default_out = self.config_data.get("output_directory") or str(root / "resultados")
        self.input_var, self.output_var = tk.StringVar(value=default_input), tk.StringVar(value=default_out)
        default_dw = root / self.config_data.get("dw_export_file_name", "base_dw.xlsx")
        self.source_var, self.profile_var, self.dw_file_var = tk.StringVar(value="file"), tk.StringVar(), tk.StringVar(value=str(default_dw) if default_dw.is_file() else "")
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
        for label, value in [("Arquivo exportado da view", "file"), ("Somente consolidação", "none")]: ttk.Radiobutton(source, text=label, variable=self.source_var, value=value).pack(side="left", padx=5)
        filefrm = ttk.Frame(self); filefrm.pack(fill="x", pady=3); ttk.Label(filefrm, text="Arquivo da view", width=22).pack(side="left"); ttk.Entry(filefrm, textvariable=self.dw_file_var).pack(side="left", fill="x", expand=True); ttk.Button(filefrm, text="Selecionar arquivo", command=lambda: self.dw_file_var.set(filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")]) or self.dw_file_var.get())).pack(side="left", padx=(6,0))
        cov = ttk.Frame(self); cov.pack(fill="x", pady=3); ttk.Label(cov, text="Cobertura DW (DD/MM/AAAA)", width=22).pack(side="left"); ttk.Entry(cov, textvariable=self.coverage_start, width=13).pack(side="left"); ttk.Label(cov, text="até").pack(side="left", padx=4); ttk.Entry(cov, textvariable=self.coverage_end, width=13).pack(side="left"); ttk.Entry(cov, textvariable=self.coverage_description).pack(side="left", fill="x", expand=True, padx=(6,0))
        actions = ttk.Frame(self); actions.pack(fill="x", pady=7)
        self.validate_btn = ttk.Button(actions, text="Validar arquivos", command=self.validate); self.validate_btn.pack(side="left")
        ttk.Button(actions, text="Prévia do mapeamento", command=self.preview).pack(side="left", padx=5)
        self.test_btn = ttk.Button(actions, text="Validar arquivo da view", command=self.validate_dw_file); self.test_btn.pack(side="left", padx=5)
        self.run_btn = ttk.Button(actions, text="Executar", command=self.run); self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=self.cancel, state="disabled"); self.cancel_btn.pack(side="left", padx=5)
        self.open_report_btn = ttk.Button(actions, text="Abrir relatório", command=lambda: self.last_output and os.startfile(self.last_output), state="disabled"); self.open_report_btn.pack(side="right")
        ttk.Button(actions, text="Abrir pasta de resultados", command=lambda: os.startfile(self.output_var.get())).pack(side="right", padx=5)
        status = ttk.Frame(self); status.pack(fill="x")
        self.stage = tk.StringVar(value="Aguardando execução manual."); ttk.Label(status, textvariable=self.stage).pack(side="left")
        self.elapsed = tk.StringVar(value="Tempo decorrido: 00:00"); ttk.Label(status, textvariable=self.elapsed).pack(side="right")
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
        if self.running and self.run_started_at:
            seconds = int(time.monotonic() - self.run_started_at)
            self.elapsed.set(f"Tempo decorrido: {seconds // 60:02d}:{seconds % 60:02d}")
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
    def validate_dw_file(self):
        try:
            path = Path(self.dw_file_var.get())
            if not path.is_file():
                raise ValueError("Selecione o arquivo Excel exportado da view.")
            sheet, total = inspect_dw_export(path)
            messagebox.showinfo("Arquivo da view", f"Estrutura validada. Aba: {sheet}. Linhas de dados: {total:,}.")
        except Exception as exc:
            messagebox.showerror("Arquivo da view", f"Não foi possível validar o arquivo: {exc}")
    def cancel(self):
        if self.token:
            self.token.cancel()
            self.cancel_btn.configure(state="disabled")
            self.stage.set("Cancelamento solicitado. Aguardando o fim do lote atual.")
            self._append("Cancelamento solicitado pelo usuário.")
    def run(self):
        self.token = CancellationToken(); self.running = True; self.run_started_at = time.monotonic(); self.elapsed.set("Tempo decorrido: 00:00")
        self.run_btn.configure(state="disabled"); self.cancel_btn.configure(state="normal"); self.open_report_btn.configure(state="disabled"); self.progress["value"] = 0
        self.config_data["input_directory"], self.config_data["output_directory"] = self.input_var.get(), self.output_var.get(); save_config(self.config_data)
        def worker():
            execution_id = datetime.now().strftime("%Y%m%d%H%M%S")
            logger = configure_logging(Path(self.output_var.get()) / "logs", execution_id, lambda msg: self.events.put(("log", msg)))
            try:
                processor = Processor(self.config_data, logger, lambda stage, pct, current: self.events.put(("progress", (stage, pct, current))))
                result = processor.run(Path(self.input_var.get()), Path(self.output_var.get()), self._profile(), self.source_var.get(), Path(self.dw_file_var.get()) if self.dw_file_var.get() else None, self._coverage(), self.token)
                summary = processor.last_summary
                message = f"{summary.status}. Letivas: {summary.letivas}; não letivas: {summary.nao_letivas}; conflitos: {summary.conflicts}; sem conflito: {summary.no_conflicts}; não verificados: {summary.not_verified}. Relatório: {result.name}"
                self.events.put(("done", (result, message)))
            except Exception as exc:
                message = "Execução cancelada." if self.token and self.token.is_cancelled else str(exc)
                self.events.put(("done", (None, message)))
        threading.Thread(target=worker, daemon=True).start()
    def _finish(self, path, message):
        self.running = False; self.last_output = path; self.run_btn.configure(state="normal"); self.cancel_btn.configure(state="disabled"); self.open_report_btn.configure(state="normal" if path else "disabled"); self.stage.set(message); self._append(message)


def main():
    root = tk.Tk(); Application(root); root.mainloop()
