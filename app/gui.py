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
from .discovery import discover_excel_files
from .dw import inspect_dw_export
from .logging_config import configure_logging
from .models import CancellationToken, Coverage
from .normalize import parse_date
from .orchestrator import Processor
from .reader import preview_mapping


class Application(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.pack(fill="both", expand=True)
        self.config_data = load_config()
        self.events: queue.Queue = queue.Queue()
        self.token: CancellationToken | None = None
        self.last_output: Path | None = None
        self.running = False
        self.run_started_at: float | None = None
        root = application_root()
        self.input_var = tk.StringVar(value=self.config_data.get("input_directory") or str(root))
        self.output_var = tk.StringVar(value=self.config_data.get("output_directory") or str(root / "resultados"))
        default_base = root / "base_dw.xlsx"
        self.dw_file_var = tk.StringVar(value=str(default_base) if default_base.is_file() else "")
        self.profile_var = tk.StringVar()
        self.coverage_start = tk.StringVar()
        self.coverage_end = tk.StringVar()
        self._build()
        self.after(120, self._poll)

    def _build(self) -> None:
        self.master.title("Eventos Avulsos - Consolidação e Conflitos")
        self.master.minsize(850, 620)

        def folder_row(label: str, variable: tk.StringVar) -> None:
            frame = ttk.Frame(self)
            frame.pack(fill="x", pady=3)
            ttk.Label(frame, text=label, width=22).pack(side="left")
            ttk.Entry(frame, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(frame, text="Selecionar pasta", command=lambda: variable.set(filedialog.askdirectory() or variable.get())).pack(side="left", padx=(6, 0))

        folder_row("Diretório de entrada", self.input_var)
        folder_row("Diretório de saída", self.output_var)
        profile_frame = ttk.Frame(self)
        profile_frame.pack(fill="x", pady=5)
        ttk.Label(profile_frame, text="Perfil de template", width=22).pack(side="left")
        self.profiles_box = ttk.Combobox(profile_frame, textvariable=self.profile_var, state="readonly", values=[profile.id for profile in profiles(self.config_data)])
        self.profiles_box.pack(side="left", fill="x", expand=True)
        self.profiles_box.current(0)

        base_frame = ttk.Frame(self)
        base_frame.pack(fill="x", pady=3)
        ttk.Label(base_frame, text="Arquivo base da view", width=22).pack(side="left")
        ttk.Entry(base_frame, textvariable=self.dw_file_var).pack(side="left", fill="x", expand=True)
        ttk.Button(base_frame, text="Selecionar arquivo", command=lambda: self.dw_file_var.set(filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")]) or self.dw_file_var.get())).pack(side="left", padx=(6, 0))

        coverage_frame = ttk.Frame(self)
        coverage_frame.pack(fill="x", pady=3)
        ttk.Label(coverage_frame, text="Cobertura da base (opcional)", width=22).pack(side="left")
        ttk.Entry(coverage_frame, textvariable=self.coverage_start, width=13).pack(side="left")
        ttk.Label(coverage_frame, text="até").pack(side="left", padx=4)
        ttk.Entry(coverage_frame, textvariable=self.coverage_end, width=13).pack(side="left")
        ttk.Label(coverage_frame, text="DD/MM/AAAA").pack(side="left", padx=6)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=7)
        self.validate_btn = ttk.Button(actions, text="Validar arquivos", command=self.validate)
        self.validate_btn.pack(side="left")
        ttk.Button(actions, text="Prévia do mapeamento", command=self.preview).pack(side="left", padx=5)
        self.validate_base_btn = ttk.Button(actions, text="Validar base", command=self.validate_dw_file)
        self.validate_base_btn.pack(side="left", padx=5)
        self.run_btn = ttk.Button(actions, text="Executar", command=self.run)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)
        self.open_report_btn = ttk.Button(actions, text="Abrir relatório", command=self.open_report, state="disabled")
        self.open_report_btn.pack(side="right")
        ttk.Button(actions, text="Abrir pasta de resultados", command=self.open_output).pack(side="right", padx=5)

        status = ttk.Frame(self)
        status.pack(fill="x")
        self.stage = tk.StringVar(value="Aguardando execução manual.")
        ttk.Label(status, textvariable=self.stage).pack(side="left")
        self.elapsed = tk.StringVar(value="Tempo decorrido: 00:00")
        ttk.Label(status, textvariable=self.elapsed).pack(side="right")
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", pady=3)
        self.log = tk.Text(self, height=18, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    def _profile(self):
        return next(profile for profile in profiles(self.config_data) if profile.id == self.profile_var.get())

    def _coverage(self) -> Coverage:
        start, end = parse_date(self.coverage_start.get()), parse_date(self.coverage_end.get())
        if bool(start) != bool(end):
            raise ValueError("Informe as duas datas da cobertura ou deixe ambas em branco.")
        return Coverage(bool(start and end), start, end)

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.stage.set(value[0] + (f" — {value[2]}" if value[2] else ""))
                    if value[1] is None:
                        if str(self.progress["mode"]) != "indeterminate":
                            self.progress.configure(mode="indeterminate")
                            self.progress.start(10)
                    else:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=value[1])
                elif kind == "log":
                    self._append(value)
                elif kind == "done":
                    self._finish(*value)
        except queue.Empty:
            pass
        if self.running and self.run_started_at:
            seconds = int(time.monotonic() - self.run_started_at)
            self.elapsed.set(f"Tempo decorrido: {seconds // 60:02d}:{seconds % 60:02d}")
        self.after(120, self._poll)

    def validate(self) -> None:
        try:
            found, missing = Processor(self.config_data, configure_logging(Path(self.output_var.get()) / "logs", "validacao")).validate(Path(self.input_var.get()))
            messagebox.showinfo("Validação", "Encontradas: " + ", ".join(folder.name for folder, _ in found) + "\nAusentes: " + ", ".join(folder.name for folder in missing))
        except Exception as exc:
            messagebox.showerror("Validação", str(exc))

    def preview(self) -> None:
        try:
            found, _ = Processor(self.config_data, configure_logging(Path(self.output_var.get()) / "logs", "previa")).validate(Path(self.input_var.get()))
            for _, folder_path in found:
                files, _ = discover_excel_files(folder_path)
                if files:
                    sheet, mapping, rows = preview_mapping(files[0], self._profile())
                    text = f"Arquivo: {files[0].name}\nAba: {sheet}\n\n" + "\n".join(f"{field}: {value}" for field, value in mapping.items()) + "\n\nPrimeiras linhas:\n" + "\n".join(str(row) for row in rows)
                    messagebox.showinfo("Prévia do mapeamento", text)
                    return
            raise ValueError("Nenhum arquivo elegível encontrado para prévia.")
        except Exception as exc:
            messagebox.showerror("Prévia", str(exc))

    def validate_dw_file(self) -> None:
        try:
            path = Path(self.dw_file_var.get())
            sheet, total = inspect_dw_export(path)
            rows = f"{total:,}" if total else "não informado pelo arquivo"
            messagebox.showinfo("Base da view", f"Estrutura validada. Aba: {sheet}. Linhas de dados: {rows}.")
        except Exception as exc:
            messagebox.showerror("Base da view", f"Não foi possível validar o arquivo: {exc}")

    def open_output(self) -> None:
        os.startfile(self.output_var.get())

    def open_report(self) -> None:
        if self.last_output:
            os.startfile(self.last_output)

    def cancel(self) -> None:
        if self.token:
            self.token.cancel()
            self.cancel_btn.configure(state="disabled")
            self.stage.set("Cancelamento solicitado. Aguardando o fim do lote atual.")
            self._append("Cancelamento solicitado pelo usuário.")

    def run(self) -> None:
        try:
            coverage = self._coverage()
        except ValueError as exc:
            messagebox.showerror("Cobertura da base", str(exc))
            return
        self.token = CancellationToken()
        self.running = True
        self.run_started_at = time.monotonic()
        self.elapsed.set("Tempo decorrido: 00:00")
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_report_btn.configure(state="disabled")
        self.progress["value"] = 0
        self.config_data["input_directory"] = self.input_var.get()
        self.config_data["output_directory"] = self.output_var.get()
        save_config(self.config_data)

        def worker() -> None:
            execution_id = datetime.now().strftime("%Y%m%d%H%M%S")
            logger = configure_logging(Path(self.output_var.get()) / "logs", execution_id, lambda message: self.events.put(("log", message)))
            try:
                processor = Processor(self.config_data, logger, lambda stage, percentage, current: self.events.put(("progress", (stage, percentage, current))))
                result = processor.run(Path(self.input_var.get()), Path(self.output_var.get()), self._profile(), Path(self.dw_file_var.get()), coverage, self.token)
                summary = processor.last_summary
                message = f"{summary.status}. Letivas: {summary.letivas}; não letivas: {summary.nao_letivas}; conflitos: {summary.conflicts}; sem conflito: {summary.no_conflicts}; não verificados: {summary.not_verified}. Relatório: {result.name}"
                self.events.put(("done", (result, message)))
            except Exception as exc:
                message = "Execução cancelada." if self.token and self.token.is_cancelled else str(exc)
                self.events.put(("done", (None, message)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, path: Path | None, message: str) -> None:
        self.running = False
        self.last_output = path
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.open_report_btn.configure(state="normal" if path else "disabled")
        self.stage.set(message)
        self._append(message)


def main() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
