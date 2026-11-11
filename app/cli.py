from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config, profiles
from .logging_config import configure_logging
from .models import CancellationToken
from .orchestrator import Processor


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida solicitações de Eventos Avulsos.")
    parser.add_argument("--entrada", required=True)
    parser.add_argument("--saida", required=True)
    parser.add_argument("--perfil", default="novo_evento_avulso")
    args = parser.parse_args()
    config = load_config()
    profile = next(profile for profile in profiles(config) if profile.id == args.perfil)
    logger = configure_logging(Path(args.saida) / "logs", "cli")
    output = Processor(config, logger, lambda stage, percentage, item: print(f"{percentage if percentage is not None else '?':>3}% {stage} {item or ''}")).run(Path(args.entrada), Path(args.saida), profile, CancellationToken())
    print(output)


if __name__ == "__main__":
    main()
