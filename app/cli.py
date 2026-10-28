from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config, profiles
from .logging_config import configure_logging
from .models import CancellationToken, Coverage
from .normalize import parse_date
from .orchestrator import Processor


def main():
    parser = argparse.ArgumentParser(description="Consolida Eventos Avulsos e verifica conflitos.")
    parser.add_argument("--entrada", required=True); parser.add_argument("--saida", required=True); parser.add_argument("--perfil", default="novo_evento_avulso")
    parser.add_argument("--fonte", choices=["none", "file", "sql"], default="none"); parser.add_argument("--arquivo-dw")
    parser.add_argument("--cobertura-inicio"); parser.add_argument("--cobertura-fim")
    args = parser.parse_args(); config = load_config(); profile = next(p for p in profiles(config) if p.id == args.perfil)
    logger = configure_logging(Path(args.saida) / "logs", "cli")
    coverage = Coverage(bool(args.cobertura_inicio and args.cobertura_fim), parse_date(args.cobertura_inicio), parse_date(args.cobertura_fim))
    output = Processor(config, logger, lambda stage, pct, item: print(f"{pct:3}% {stage} {item or ''}")).run(Path(args.entrada), Path(args.saida), profile, args.fonte, Path(args.arquivo_dw) if args.arquivo_dw else None, coverage, CancellationToken())
    print(output)

if __name__ == "__main__": main()
