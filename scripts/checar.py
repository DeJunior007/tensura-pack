"""Valida o pack (R3.1, R3.2, R3.5, R3.6; spec §2, §3).

Uso: checar.py [--pack DIR]   → exit 0 se ok, 1 com um erro por linha e o total.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _comum as c


def checar(pack_dir: Path) -> list[str]:
    pack_dir = Path(pack_dir)
    erros: list[str] = []
    if not (pack_dir / "pack.toml").is_file():
        return [f"pack.toml não encontrado em {pack_dir}"]

    # §2.1 — [versions] exatamente minecraft + neoforge
    versoes = c.ler_pack(pack_dir).get("versions", {})
    esperado = {"minecraft": c.MC, "neoforge": c.NEOFORGE}
    if versoes != esperado:
        erros.append(
            f"pack.toml: [versions] deve ser exatamente minecraft = \"{c.MC}\" e "
            f"neoforge = \"{c.NEOFORGE}\" (achei {versoes})"
        )

    mods = c.ler_mods(pack_dir)
    por_id = {m.id: m for m in mods}
    meta = c.ler_meta(pack_dir)
    manual = c.ler_manual(pack_dir)
    manual_por_id = {str(i.get("id", "")): i for i in manual}

    # R3.2 — side válido
    for m in mods:
        if m.lado not in c.LADOS:
            if not m.lado:
                erros.append(f"{m.id}.pw.toml sem side (use both, client ou server)")
            else:
                erros.append(f"{m.id}.pw.toml com side inválido \"{m.lado}\"")

    # R3.2 — lista de só-cliente
    for mod_id in c.ler_lado_cliente(pack_dir):
        m = por_id.get(mod_id)
        if m is None:
            erros.append(f"meta/lado-cliente.txt: {mod_id} não tem .pw.toml no pack")
        elif m.lado != "client":
            erros.append(
                f"{mod_id} está em meta/lado-cliente.txt mas tem side = \"{m.lado}\" (deve ser client)"
            )

    # R3.5 — nada do FORA.md no pack
    nomes_norm = {c.normalizar(m.nome): m.id for m in mods}
    for fora_id, fora_nome in c.ler_fora(pack_dir):
        if fora_id in por_id or fora_id in manual_por_id:
            achado = fora_id
        else:
            achado = nomes_norm.get(c.normalizar(fora_nome)) if fora_nome else None
        if achado:
            erros.append(f"{achado} está em FORA.md mas continua no pack")

    # §2.5 — entrada em meta/mods.toml para todo .pw.toml e todo item de manual.toml
    for m in mods:
        if m.id not in meta:
            erros.append(f"{m.id}.pw.toml sem entrada em meta/mods.toml")
    for mod_id in manual_por_id:
        if mod_id not in meta:
            erros.append(f"manual.toml: {mod_id} sem entrada em meta/mods.toml")

    # §2.6 — classes
    for m in mods:
        classe = str(meta.get(m.id, {}).get("classe", ""))
        if m.fonte == "curseforge" and classe not in ("A", "B"):
            if m.id in meta:
                erros.append(
                    f"{m.id} é CurseForge sem classe A ou B em meta/mods.toml "
                    f"(classe = \"{classe}\")"
                )
        if m.fonte != "curseforge" and classe in ("A", "B"):
            erros.append(f"{m.id} tem classe {classe} mas não é CurseForge")
        if classe == "C":
            erros.append(f"{m.id} é classe C mas tem .pw.toml (C fica só em manual.toml)")
        if classe == "B" and m.id not in manual_por_id:
            erros.append(f"{m.id} é classe B sem item em manual.toml")

    for mod_id, item in manual_por_id.items():
        classe_item = str(item.get("classe", ""))
        if classe_item not in ("B", "C"):
            erros.append(f"manual.toml: {mod_id} com classe \"{classe_item}\" (use B ou C)")
        classe_meta = meta.get(mod_id, {}).get("classe")
        if classe_meta is not None and str(classe_meta) != classe_item:
            erros.append(
                f"manual.toml: {mod_id} é classe {classe_item} mas meta/mods.toml diz {classe_meta}"
            )
        if classe_item == "B" and mod_id not in por_id:
            erros.append(f"manual.toml: {mod_id} é classe B sem .pw.toml")
        if classe_item == "C" and mod_id in por_id and str(classe_meta) != "C":
            erros.append(f"{mod_id} é classe C mas tem .pw.toml (C fica só em manual.toml)")

    for mod_id, entrada in meta.items():
        if str(entrada.get("classe", "")) == "C" and mod_id not in manual_por_id:
            erros.append(f"{mod_id} é classe C em meta/mods.toml sem item em manual.toml")

    return erros


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Valida o pack (versões, lados, classes).")
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    args = ap.parse_args(argv)
    erros = checar(args.pack)
    for e in erros:
        print(f"erro: {e}", file=sys.stderr)
    if erros:
        print(f"{len(erros)} erro(s).", file=sys.stderr)
        return 1
    print("pack ok: 0 erros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
