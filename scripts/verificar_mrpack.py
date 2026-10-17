"""Confere o `.mrpack` gerado pelo `packwiz modrinth export` (spec §3, CA-T4).

    verificar_mrpack.py ARQ.mrpack [--pack DIR]

- `dependencies` = {minecraft: 1.21.1, neoforge: 21.1.262}; `versionId` = versão do pack.toml;
- nenhum arquivo de classe B/C (por nome ou sha1) em `files` nem em `overrides/`,
  `client-overrides/`, `server-overrides/`;
- mod Modrinth `client` com `env.server = "unsupported"`, `server` com `env.client = "unsupported"`,
  todo mod Modrinth presente em `files`;
- jar CF (classe A) embutido no diretório do seu lado (both → overrides/, client →
  client-overrides/, server → server-overrides/, §0.2).

Imprime um erro por linha e o total; sai 1 se houver erro.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

import _comum as c

DIR_LADO = {"both": "overrides", "client": "client-overrides", "server": "server-overrides"}
PASTA_TIPO = {v: k for k, v in c.PASTAS_TIPO.items()}  # tipo → pasta


def _nome(caminho: str) -> str:
    return PurePosixPath(caminho).name


def verificar(mrpack: Path, pack_dir: Path = c.PACK_DIR) -> list[str]:
    erros: list[str] = []
    try:
        z = zipfile.ZipFile(mrpack)
    except (OSError, zipfile.BadZipFile) as e:
        return [f"{mrpack}: não é um zip legível ({e})"]
    with z:
        try:
            indice = json.loads(z.read("modrinth.index.json"))
        except KeyError:
            return [f"{mrpack}: sem modrinth.index.json"]
        except json.JSONDecodeError as e:
            return [f"{mrpack}: modrinth.index.json inválido ({e})"]
        entradas = {i.filename: i for i in z.infolist() if not i.is_dir()}

        def sha1_entrada(nome: str) -> str:
            return hashlib.sha1(z.read(nome)).hexdigest()

        esperado = {"minecraft": c.MC, "neoforge": c.NEOFORGE}
        deps = indice.get("dependencies")
        if deps != esperado:
            erros.append(f"dependencies = {deps!r}, esperado {esperado!r}")
        versao = str(c.ler_pack(pack_dir).get("version", ""))
        if str(indice.get("versionId", "")) != versao:
            erros.append(f"versionId = {indice.get('versionId')!r}, esperado {versao!r} (pack.toml)")

        meta = c.ler_meta(pack_dir)
        mods = c.ler_mods(pack_dir)
        manual = c.ler_manual(pack_dir)
        manuais = {str(m.get("id")) for m in manual}
        fora_nomes: dict[str, str] = {}  # nome de arquivo → id
        fora_sha1: dict[str, str] = {}
        for m in manual:
            if m.get("arquivo"):
                fora_nomes[str(m["arquivo"])] = str(m["id"])
            if m.get("sha1"):
                fora_sha1[str(m["sha1"]).lower()] = str(m["id"])
        bc = {m.id for m in mods if meta.get(m.id, {}).get("classe") in ("B", "C")} | manuais
        for m in mods:
            if m.id in bc:
                if m.arquivo:
                    fora_nomes[m.arquivo] = m.id
                if m.hash_formato == "sha1" and m.hash:
                    fora_sha1[m.hash.lower()] = m.id

        arquivos = indice.get("files") or []
        por_nome = {}
        for f in arquivos:
            caminho = str(f.get("path", ""))
            nome = _nome(caminho)
            por_nome[nome] = f
            sha1 = str((f.get("hashes") or {}).get("sha1", "")).lower()
            alvo = fora_nomes.get(nome) or fora_sha1.get(sha1)
            if alvo:
                erros.append(f"files: {caminho} é do mod {alvo} (classe B/C) e não pode estar no .mrpack")

        for nome_ent in sorted(entradas):
            raiz = nome_ent.split("/", 1)[0]
            if raiz not in DIR_LADO.values():
                continue
            alvo = fora_nomes.get(_nome(nome_ent))
            if not alvo and nome_ent.endswith((".jar", ".zip")):
                alvo = fora_sha1.get(sha1_entrada(nome_ent))
            if alvo:
                erros.append(f"{nome_ent} é do mod {alvo} (classe B/C) e não pode estar no .mrpack")

        for m in mods:
            if m.id in bc:
                continue
            pasta = PASTA_TIPO.get(m.tipo, "mods")
            if m.fonte == "modrinth":
                f = por_nome.get(m.arquivo)
                if f is None:
                    erros.append(f"{m.id}: {m.arquivo} ausente de files")
                    continue
                env = f.get("env") or {}
                if m.lado == "client" and env.get("server") != "unsupported":
                    erros.append(f"{m.id} é client mas env.server = {env.get('server')!r} (esperado 'unsupported')")
                if m.lado == "server" and env.get("client") != "unsupported":
                    erros.append(f"{m.id} é server mas env.client = {env.get('client')!r} (esperado 'unsupported')")
            elif m.fonte == "curseforge":
                certo = f"{DIR_LADO.get(m.lado, 'overrides')}/{pasta}/{m.arquivo}"
                if certo in entradas:
                    continue
                outros = [f"{d}/{pasta}/{m.arquivo}" for d in DIR_LADO.values()]
                achado = [o for o in outros if o in entradas]
                if achado:
                    erros.append(f"{m.id} ({m.lado}) embutido em {achado[0]}, esperado {certo}")
                else:
                    erros.append(f"{m.id}: jar CF {m.arquivo} não está embutido ({certo})")
    return erros


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Confere o .mrpack gerado (spec §3, CA-T4).")
    ap.add_argument("mrpack", type=Path)
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    a = ap.parse_args(argv)
    if not a.mrpack.is_file():
        c.erro(f"erro: {a.mrpack} não existe")
        return 2
    erros = verificar(a.mrpack, a.pack)
    for e in erros:
        c.erro(e)
    if erros:
        c.erro(f"{len(erros)} erro(s) no .mrpack")
        return 1
    print(f"{a.mrpack.name}: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
