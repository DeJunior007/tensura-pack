"""Gera o `.zip` de instalação manual a partir do `.mrpack` (spec §3; ≠ design §3).

    zip_fallback.py ARQ.mrpack --saida dist/ [--pack DIR]

Lê o `modrinth.index.json`, baixa os `files` com `env.client != "unsupported"` cuja licença
(meta/mods.toml > meta/licencas.json) é aberta, conferindo sha1 (e sha512, se houver); copia
`overrides/` e `client-overrides/` (config, resourcepacks, jars classe A; `server-overrides/` fica
de fora); gera `LEIA-ME.txt` (NeoForge + lista "baixe à mão" com a página de cada mod fora do zip)
e grava `tensura-<v>.zip` com raiz relativa a `.minecraft/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable

import _comum as c

USER_AGENT = "tensura-pack/1.0 (contato no README)"


class ErroZip(Exception):
    pass


def baixar_http(url: str) -> bytes:  # pragma: no cover (rede)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _seguro(caminho: str) -> str:
    p = PurePosixPath(caminho)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ErroZip(f"caminho inválido no .mrpack: {caminho!r}")
    return p.as_posix()


def leia_me(versao: str, fora: list[tuple[str, str, str]]) -> str:
    linhas = [
        f"Tensura SMP {versao} — instalação manual",
        "",
        f"1. Instale o Minecraft {c.MC} com NeoForge {c.NEOFORGE} (instalador em https://neoforged.net/).",
        "2. Abra a pasta .minecraft da instância e extraia este zip nela (mods/, config/,",
        "   resourcepacks/ ficam lado a lado com as que já existem).",
        "3. Baixe à mão os mods abaixo (a licença não permite pôr no zip) e coloque cada um",
        "   na pasta indicada.",
        "",
        "Baixe à mão:",
    ]
    if fora:
        linhas += [f"- {nome} — {pag} (pasta: {pasta})" for nome, pag, pasta in fora]
    else:
        linhas.append("- (nenhum)")
    return "\n".join(linhas) + "\n"


def gerar_zip(
    mrpack: Path,
    saida: Path,
    pack_dir: Path = c.PACK_DIR,
    baixar: Callable[[str], bytes] = baixar_http,
) -> Path:
    """Grava `saida/tensura-<v>.zip` e devolve o caminho. Falha → ErroZip."""
    meta = c.ler_meta(pack_dir)
    licencas = c.ler_licencas(pack_dir)
    mods = c.ler_mods(pack_dir)
    por_arquivo = {m.arquivo: m for m in mods if m.arquivo}
    por_hash = {m.hash.lower(): m for m in mods if m.hash}

    with zipfile.ZipFile(mrpack) as z:
        indice = json.loads(z.read("modrinth.index.json"))
        versao = str(indice.get("versionId") or c.ler_pack(pack_dir)["version"])
        conteudo: dict[str, bytes] = {}
        fora: list[tuple[str, str, str]] = []

        for f in indice.get("files") or []:
            if (f.get("env") or {}).get("client") == "unsupported":
                continue  # só servidor: nem no zip nem no LEIA-ME
            caminho = _seguro(str(f.get("path", "")))
            nome_arq = PurePosixPath(caminho).name
            pasta = str(PurePosixPath(caminho).parent)
            hashes = {k: str(v).lower() for k, v in (f.get("hashes") or {}).items()}
            mod = por_arquivo.get(nome_arq) or next(
                (por_hash[h] for h in hashes.values() if h in por_hash), None
            )
            if mod is None:
                fora.append((nome_arq, "(página desconhecida)", pasta))
                continue
            lic = c.licenca_de(mod.id, meta, licencas)
            if not c.licenca_aberta(lic):
                nome = str(meta.get(mod.id, {}).get("nome") or mod.nome)
                fora.append((nome, c.pagina(mod, meta.get(mod.id, {})), pasta))
                continue
            urls = f.get("downloads") or []
            if not urls:
                raise ErroZip(f"{mod.id}: sem downloads no .mrpack")
            dados = baixar(str(urls[0]))
            if "sha1" not in hashes:
                raise ErroZip(f"{mod.id}: .mrpack sem sha1")
            for alg in ("sha1", "sha512"):
                if alg in hashes and hashlib.new(alg, dados).hexdigest() != hashes[alg]:
                    raise ErroZip(f"{mod.id}: {alg} divergente em {urls[0]}")
            conteudo[caminho] = dados

        # overrides/ primeiro, client-overrides/ por cima
        for prefixo in ("overrides/", "client-overrides/"):
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith(prefixo):
                    continue
                conteudo[_seguro(info.filename[len(prefixo):])] = z.read(info)

    for item in c.ler_manual(pack_dir):
        if str(item.get("lado", "both")) == "server":
            continue
        fora.append((str(item.get("nome") or item.get("id")), str(item.get("pagina") or ""),
                     str(item.get("pasta") or "mods")))
    fora.sort(key=lambda t: c.normalizar(t[0]))
    conteudo["LEIA-ME.txt"] = leia_me(versao, fora).encode("utf-8")

    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"tensura-{versao}.zip"
    tmp = destino.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for nome in sorted(conteudo):
            out.writestr(nome, conteudo[nome])
    tmp.replace(destino)
    return destino


def main(argv: list[str] | None = None, baixar: Callable[[str], bytes] = baixar_http) -> int:
    ap = argparse.ArgumentParser(description="Gera o .zip de instalação manual a partir do .mrpack.")
    ap.add_argument("mrpack", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    a = ap.parse_args(argv)
    if not a.mrpack.is_file():
        c.erro(f"erro: {a.mrpack} não existe")
        return 2
    try:
        destino = gerar_zip(a.mrpack, a.saida, a.pack, baixar)
    except (ErroZip, zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError) as e:
        c.erro(f"erro: {e}")
        return 1
    print(destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
