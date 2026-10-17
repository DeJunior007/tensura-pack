"""Sobe a versão do pack (R3.1, R8.1; spec §3, §2.8).

Uso: versao.py patch|minor|major [--pack DIR]
Troca só a linha `version = "…"` do pack.toml, cria `## vX.Y.Z — <data SP>` no topo do
CHANGELOG.md e imprime a versão nova. Versão atual inválida → exit 1.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import _comum as c

_LINHA_VERSAO = re.compile(r'^(version\s*=\s*")([^"]*)(".*)$', re.M)
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class VersaoInvalida(ValueError):
    pass


def hoje_sp() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    except Exception:  # noqa: BLE001 - sem tzdata: SP é UTC-3 (sem horário de verão)
        return datetime.now(timezone(timedelta(hours=-3))).date()


def proxima(versao: str, nivel: str) -> str:
    m = _SEMVER.match(versao)
    if not m:
        raise VersaoInvalida(f"versão inválida no pack.toml: \"{versao}\" (esperado X.Y.Z)")
    ma, mi, pa = (int(x) for x in m.groups())
    if nivel == "major":
        return f"{ma + 1}.0.0"
    if nivel == "minor":
        return f"{ma}.{mi + 1}.0"
    if nivel == "patch":
        return f"{ma}.{mi}.{pa + 1}"
    raise ValueError(f"nível inválido: {nivel}")


def subir(pack_dir: Path, nivel: str, hoje: date | None = None) -> str:
    pack_dir = Path(pack_dir)
    pack_toml = pack_dir / "pack.toml"
    texto = pack_toml.read_text(encoding="utf-8")
    # só a linha de topo (antes da primeira tabela)
    topo = texto.split("\n[", 1)[0]
    m = _LINHA_VERSAO.search(topo)
    if not m:
        raise VersaoInvalida("pack.toml sem linha version = \"…\"")
    nova = proxima(m.group(2), nivel)
    texto = texto[: m.start()] + m.group(1) + nova + m.group(3) + texto[m.end():]
    pack_toml.write_text(texto, encoding="utf-8")

    d = hoje or hoje_sp()
    secao = f"## v{nova} — {d.isoformat()}\n\n"
    changelog = pack_dir / "CHANGELOG.md"
    atual = changelog.read_text(encoding="utf-8") if changelog.is_file() else "# Changelog\n\n"
    i = atual.find("\n## ")
    if atual.startswith("## "):
        atual = secao + atual
    elif i >= 0:
        atual = atual[: i + 1] + secao + atual[i + 1:]
    else:
        atual = atual.rstrip("\n") + "\n\n" + secao
    changelog.write_text(atual, encoding="utf-8")
    return nova


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sobe a versão do pack.")
    ap.add_argument("nivel", choices=["patch", "minor", "major"])
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    args = ap.parse_args(argv)
    try:
        nova = subir(args.pack, args.nivel)
    except (VersaoInvalida, FileNotFoundError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    print(nova)
    return 0


if __name__ == "__main__":
    sys.exit(main())
