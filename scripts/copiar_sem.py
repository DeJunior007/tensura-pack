"""Copia o pack sem os `.pw.toml` das classes dadas (spec §3; para o `packwiz modrinth export`).

    copiar_sem.py ORIGEM DESTINO --classes B

A classe de cada mod vem de `meta/mods.toml` (`classe`) e, para B/C, também de `manual.toml`.
`DESTINO` pode não existir ou já existir vazio (ex.: `mktemp -d`). `dist/` e `.git/` não são
copiados. As entradas removidas também saem do `index.toml` (o `packwiz refresh` da release
regrava o índice de qualquer forma). Imprime um id removido por linha.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import _comum as c

_IGNORAR = shutil.ignore_patterns("dist", ".git", "__pycache__")


def classes_do_pack(pack_dir: Path) -> dict[str, str]:
    """id → classe (meta/mods.toml, completado por manual.toml)."""
    classes = {i: str(m.get("classe", "")) for i, m in c.ler_meta(pack_dir).items()}
    for item in c.ler_manual(pack_dir):
        if item.get("id") and item.get("classe"):
            classes.setdefault(str(item["id"]), str(item["classe"]))
    return classes


def _limpar_indice(indice: Path, removidos: set[str]) -> None:
    if not indice.is_file() or not removidos:
        return
    texto = indice.read_text(encoding="utf-8")
    blocos = re.split(r"(?m)^(?=\[\[files\]\])", texto)
    manter = []
    for b in blocos:
        m = re.search(r'(?m)^file\s*=\s*"([^"]+)"', b) if b.startswith("[[files]]") else None
        if m and m.group(1) in removidos:
            continue
        manter.append(b)
    indice.write_text("".join(manter), encoding="utf-8")


def copiar_sem(origem: Path, destino: Path, classes: set[str]) -> list[str]:
    """Copia `origem` → `destino` e apaga os `.pw.toml` das `classes`. Devolve os ids removidos."""
    origem, destino = Path(origem), Path(destino)
    if destino.exists() and any(destino.iterdir()):
        raise ValueError(f"destino não está vazio: {destino}")
    shutil.copytree(origem, destino, ignore=_IGNORAR, dirs_exist_ok=True)
    da_classe = {i for i, k in classes_do_pack(origem).items() if k in classes}
    removidos: list[str] = []
    caminhos: set[str] = set()
    for pasta in c.PASTAS_TIPO:
        for p in sorted((destino / pasta).glob("*.pw.toml")):
            mod_id = p.name[: -len(".pw.toml")]
            if mod_id in da_classe:
                p.unlink()
                removidos.append(mod_id)
                caminhos.add(f"{pasta}/{p.name}")
    _limpar_indice(destino / "index.toml", caminhos)
    return sorted(removidos)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copia o pack sem os .pw.toml das classes dadas.")
    ap.add_argument("origem", type=Path)
    ap.add_argument("destino", type=Path)
    ap.add_argument("--classes", required=True, help='ex.: "B" ou "B,C"')
    a = ap.parse_args(argv)
    classes = {x.strip() for x in a.classes.split(",") if x.strip()}
    if not classes or not classes <= {"modrinth", "A", "B", "C"}:
        c.erro(f"erro: --classes inválido: {a.classes!r} (use A, B, C ou modrinth)")
        return 2
    if not (a.origem / "pack.toml").is_file():
        c.erro(f"erro: {a.origem} não tem pack.toml")
        return 1
    try:
        removidos = copiar_sem(a.origem, a.destino, classes)
    except ValueError as e:
        c.erro(f"erro: {e}")
        return 1
    for i in removidos:
        print(i)
    return 0


if __name__ == "__main__":
    sys.exit(main())
