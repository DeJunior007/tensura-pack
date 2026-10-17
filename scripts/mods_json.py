"""Gera `mods.json` (lista pública, spec §4.2) e `manual.json` ("baixe à mão", §4.3).

    mods_json.py --saida dist/ [--pack DIR]

`mods.json` nunca leva `url`, `download`, `hash`, `filename` nem links de CDN (R6.3): a saída é
conferida antes de gravar e o script sai 1 se algo escapar.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import _comum as c

LADO_PT = {"both": "ambos", "client": "cliente", "server": "servidor"}
CHAVES_PROIBIDAS = ("url", "download", "hash", "filename")
TEXTOS_PROIBIDOS = ("cdn.modrinth.com", "forgecdn")
CAMPOS_MANUAL = ("id", "nome", "classe", "lado", "arquivo", "pagina", "sha1", "pasta")


def _chave_nome(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome)
    return "".join(ch for ch in t if not unicodedata.combining(ch)).lower()


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def gerar(
    pack_dir: Path = c.PACK_DIR, agora: Callable[[], datetime] = _agora_utc
) -> tuple[dict, dict]:
    """Devolve (mods.json, manual.json) como dicts."""
    pack = c.ler_pack(pack_dir)
    versao = str(pack["version"])
    versoes = pack.get("versions", {})
    meta = c.ler_meta(pack_dir)
    licencas = c.ler_licencas(pack_dir)
    manual = c.ler_manual(pack_dir)
    manual_por_id = {str(m["id"]): m for m in manual if m.get("id")}

    def item(mod_id: str, nome: str, lado: str, tipo: str, fonte: str, pag: str) -> dict:
        m = meta.get(mod_id, {})
        classe = str(m.get("classe") or manual_por_id.get(mod_id, {}).get("classe") or "")
        return {
            "id": mod_id,
            "nome": str(m.get("nome") or nome),
            "categoria": str(m.get("categoria") or "outros"),
            "lado": LADO_PT.get(lado, lado),
            "tipo": tipo,
            "fonte": fonte,
            "pagina": pag,
            "licenca": c.licenca_de(mod_id, meta, licencas),
            "manual": classe in ("B", "C") or mod_id in manual_por_id,
            "nota": str(m.get("nota") or ""),
        }

    lista = []
    vistos = set()
    for mod in c.ler_mods(pack_dir):
        m = meta.get(mod.id, {})
        pag = c.pagina(mod, m)
        if mod.fonte != "modrinth" and not m.get("pagina") and mod.id in manual_por_id:
            pag = str(manual_por_id[mod.id].get("pagina") or pag)
        lista.append(item(mod.id, mod.nome, mod.lado, mod.tipo, mod.fonte, pag))
        vistos.add(mod.id)
    for mid, it in manual_por_id.items():  # classe C (só manual.toml)
        if mid in vistos:
            continue
        pag = str(meta.get(mid, {}).get("pagina") or it.get("pagina") or "")
        lista.append(item(mid, str(it.get("nome") or mid), str(it.get("lado") or "both"),
                          "mod", "curseforge", pag))
    lista.sort(key=lambda x: (x["categoria"], _chave_nome(x["nome"]), x["id"]))

    mods_json = {
        "schema": 1,
        "versao": versao,
        "minecraft": str(versoes.get("minecraft", c.MC)),
        "neoforge": str(versoes.get("neoforge", c.NEOFORGE)),
        "geradoEm": _iso_z(agora()),
        "total": len(lista),
        "mods": lista,
    }
    manual_json = {
        "schema": 1,
        "versao": versao,
        "mods": [{k: it.get(k, "") for k in CAMPOS_MANUAL} for it in manual],
    }
    return mods_json, manual_json


def problemas(mods_json: dict, manual_json: dict) -> list[str]:
    """R6.3: chaves e textos que nunca podem sair na lista pública."""
    erros = []
    for mod in mods_json.get("mods", []):
        for k in mod:
            if any(p in k.lower() for p in CHAVES_PROIBIDAS):
                erros.append(f"mods.json: chave proibida {k!r} em {mod.get('id')}")
    for nome, doc in (("mods.json", mods_json), ("manual.json", manual_json)):
        texto = json.dumps(doc, ensure_ascii=False).lower()
        for t in TEXTOS_PROIBIDOS:
            if t in texto:
                erros.append(f"{nome}: contém {t!r} (link direto de jar é proibido)")
    return erros


def _gravar(caminho: Path, doc: dict) -> None:
    caminho.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera mods.json e manual.json (spec §4.2, §4.3).")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    a = ap.parse_args(argv)
    if not (a.pack / "pack.toml").is_file():
        c.erro(f"erro: {a.pack} não tem pack.toml")
        return 1
    mods_json, manual_json = gerar(a.pack)
    erros = problemas(mods_json, manual_json)
    if erros:
        for e in erros:
            c.erro(e)
        return 1
    a.saida.mkdir(parents=True, exist_ok=True)
    _gravar(a.saida / "mods.json", mods_json)
    _gravar(a.saida / "manual.json", manual_json)
    print(f"mods.json: {mods_json['total']} mods; manual.json: {len(manual_json['mods'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
