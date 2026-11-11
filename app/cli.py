from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config, profiles
from .logging_config import configure_logging
from .models import CancellationToken, Coverage
from .normalize import parse_date
from .orchestrator import Processor


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida Eventos Avulsos e verifica conflitos contra uma base Excel local.")
    parser.add_argument("--entrada", required=True)
    parser.add_argument("--saida", required=True)
    parser.add_argument("--perfil", default="novo_evento_avulso")
    parser.add_argument("--arquivo-dw", required=True)
    parser.add_argument("--cobertura-inicio")
    parser.add_argument("--cobertura-fim")
    args = parser.parse_args()
    start, end = parse_date(args.cobertura_inicio), parse_date(args.cobertura_fim)
    if bool(start) != bool(end):
        parser.error("Informe --cobertura-inicio e --cobertura-fim juntos, ou omita os dois.")
    config = load_config()
    profile = next(profile for profile in profiles(config) if profile.id == args.perfil)
    logger = configure_logging(Path(args.saida) / "logs", "cli")
    output = Processor(config, logger, lambda stage, percentage, item: print(f"{percentage if percentage is not None else '?':>3}% {stage} {item or ''}")).run(Path(args.entrada), Path(args.saida), profile, Path(args.arquivo_dw), Coverage(bool(start and end), start, end), CancellationToken())
    print(output)


if __name__ == "__main__":
    main()
