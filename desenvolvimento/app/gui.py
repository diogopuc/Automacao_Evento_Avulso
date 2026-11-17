from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
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
        super().__init__(master, padding=0, style="Page.TFrame")
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
        default_base = root / "dados" / "base_dw.xlsx"
        self.dw_file_var = tk.StringVar(value=str(default_base) if default_base.is_file() else "")
        self.profile_var = tk.StringVar()
        self.coverage_start = tk.StringVar()
        self.coverage_end = tk.StringVar()
        self._build()
        self.after(120, self._poll)

    def _build(self) -> None:
        self.master.title("Eventos Avulsos - Consolidação e Conflitos")
        self.master.minsize(900, 700)
        self.master.geometry("1120x850")
        self.master.configure(background="#F0F2F2")
        families = set(tkfont.families(self.master))
        heading = "Poppins" if "Poppins" in families else "Segoe UI"
        body = "Source Sans Pro" if "Source Sans Pro" in families else "Segoe UI"
        style = ttk.Style(self.master)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#F0F2F2")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("Header.TFrame", background="#8A0538")
        style.configure("Header.TLabel", background="#8A0538", foreground="#FFFFFF", font=(heading, 19, "bold"))
        style.configure("HeaderSub.TLabel", background="#8A0538", foreground="#E5C3D0", font=(body, 10))
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#1E1E1E", font=(heading, 12, "bold"))
        style.configure("Body.TLabel", background="#FFFFFF", foreground="#404040", font=(body, 10))
        style.configure("Hint.TLabel", background="#FFFFFF", foreground="#787878", font=(body, 9))
        style.configure("Status.TLabel", background="#F0F2F2", foreground="#404040", font=(body, 10))
        style.configure("TEntry", fieldbackground="#FAFAFA", bordercolor="#E4E4E4", lightcolor="#E4E4E4", darkcolor="#E4E4E4", padding=7)
        style.configure("TCombobox", fieldbackground="#FAFAFA", bordercolor="#E4E4E4", padding=6, font=(body, 10))
        style.configure("TButton", font=(body, 10), padding=(12, 8), background="#FFFFFF", foreground="#8A0538", bordercolor="#E5C3D0", relief="solid")
        style.map("TButton", background=[("active", "#E5C3D0"), ("disabled", "#F0F2F2")], foreground=[("disabled", "#787878")])
        style.configure("Primary.TButton", font=(body, 10, "bold"), padding=(20, 9), background="#8A0538", foreground="#FFFFFF", bordercolor="#8A0538")
        style.map("Primary.TButton", background=[("active", "#B20235"), ("disabled", "#E4E4E4")], foreground=[("disabled", "#787878")])
        style.configure("Brand.Horizontal.TProgressbar", background="#8A0538", troughcolor="#E4E4E4", borderwidth=0, thickness=8)

        banner = ttk.Frame(self, style="Header.TFrame", padding=(28, 20))
        banner.pack(fill="x")
        ttk.Label(banner, text="Eventos Avulsos", style="Header.TLabel").pack(anchor="w")
        ttk.Label(banner, text="CONSOLIDAÇÃO E VERIFICAÇÃO DE CONFLITOS", style="HeaderSub.TLabel").pack(anchor="w", pady=(3, 0))
        content = ttk.Frame(self, style="Page.TFrame", padding=(24, 18))
        content.pack(fill="both", expand=True)
        card = ttk.Frame(content, style="Card.TFrame", padding=(20, 16))
        card.pack(fill="x")
        ttk.Label(card, text="Configuração da execução", style="Section.TLabel").pack(anchor="w")
        ttk.Label(card, text="Selecione as pastas e a base para verificar as solicitações.", style="Hint.TLabel").pack(anchor="w", pady=(2, 12))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        def path_row(row: int, label: str, variable: tk.StringVar, is_file: bool = False) -> None:
            ttk.Label(form, text=label, style="Body.TLabel", width=24).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)
            def choose() -> None:
                selected = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")]) if is_file else filedialog.askdirectory()
                if selected:
                    variable.set(selected)
            ttk.Button(form, text="Selecionar arquivo" if is_file else "Selecionar pasta", command=choose).grid(row=row, column=2, padx=(10, 0), pady=5, sticky="ew")

        path_row(0, "Diretório de entrada", self.input_var)
        path_row(1, "Diretório de saída", self.output_var)
        ttk.Label(form, text="Perfil de template", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        self.profiles_box = ttk.Combobox(form, textvariable=self.profile_var, state="readonly", values=[profile.id for profile in profiles(self.config_data)])
        self.profiles_box.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)
        self.profiles_box.current(0)
        path_row(3, "Arquivo base da view", self.dw_file_var, True)
        ttk.Label(form, text="Cobertura da base", style="Body.TLabel").grid(row=4, column=0, sticky="w", pady=5)
        coverage = ttk.Frame(form, style="Card.TFrame")
        coverage.grid(row=4, column=1, columnspan=2, sticky="w", pady=5)
        ttk.Entry(coverage, textvariable=self.coverage_start, width=13).pack(side="left")
        ttk.Label(coverage, text="até", style="Body.TLabel").pack(side="left", padx=8)
        ttk.Entry(coverage, textvariable=self.coverage_end, width=13).pack(side="left")
        ttk.Label(coverage, text="Opcional · DD/MM/AAAA", style="Hint.TLabel").pack(side="left", padx=10)

        tools = ttk.Frame(card, style="Card.TFrame")
        tools.pack(fill="x", pady=(12, 0))
        self.validate_btn = ttk.Button(tools, text="Validar arquivos", command=self.validate)
        self.validate_btn.pack(side="left", padx=(0, 8))
        ttk.Button(tools, text="Prévia do mapeamento", command=self.preview).pack(side="left", padx=(0, 8))
        self.validate_base_btn = ttk.Button(tools, text="Validar base", command=self.validate_dw_file)
        self.validate_base_btn.pack(side="left")

        actions = ttk.Frame(content, style="Page.TFrame")
        actions.pack(fill="x", pady=(14, 12))
        self.run_btn = ttk.Button(actions, text="Executar verificação", command=self.run, style="Primary.TButton")
        self.run_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left")
        self.open_report_btn = ttk.Button(actions, text="Abrir relatório", command=self.open_report, state="disabled")
        self.open_report_btn.pack(side="right")
        ttk.Button(actions, text="Abrir pasta de resultados", command=self.open_output).pack(side="right", padx=(0, 8))

        status = ttk.Frame(content, style="Page.TFrame")
        status.pack(fill="x")
        self.stage = tk.StringVar(value="Aguardando execução manual.")
        ttk.Label(status, textvariable=self.stage, style="Status.TLabel").pack(side="left", fill="x", expand=True)
        self.elapsed = tk.StringVar(value="Tempo decorrido: 00:00")
        ttk.Label(status, textvariable=self.elapsed, style="Status.TLabel").pack(side="right", padx=(12, 0))
        self.progress = ttk.Progressbar(content, mode="determinate", style="Brand.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(8, 14))
        log_card = ttk.Frame(content, style="Card.TFrame", padding=(16, 12))
        log_card.pack(fill="both", expand=True)
        ttk.Label(log_card, text="Acompanhamento da execução", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        log_frame = ttk.Frame(log_card, style="Card.TFrame")
        log_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.log = tk.Text(log_frame, height=8, state="disabled", wrap="word", font=(body, 10), foreground="#404040", background="#FAFAFA", relief="flat", padx=10, pady=10, yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.log.yview)

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
                message = f"{summary.status}. Letivas: {summary.letivas}; conflitos: {summary.conflicts}; sem conflito: {summary.no_conflicts}; não verificados: {summary.not_verified}. Relatório: {result.name}"
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
