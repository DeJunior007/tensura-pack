"""Gera `latest.json` (spec §4.4) e `SHA256SUMS` a partir dos arquivos em `dist/`.

    latest.py --dist dist/ --repo <org>/tensura-pack [--pack DIR]

A versão vem do `pack.toml`; `notas` = corpo da seção `## vX.Y.Z` do `CHANGELOG.md`.
Exige `tensura-<v>.mrpack`, `tensura-<v>.zip`, `mods.json` e `manual.json` em `dist/`;
`tensura-<v>-curseforge.zip` é opcional (`curseforge: null` sem ele). `SHA256SUMS` cobre todos
os arquivos de `dist/` (inclusive `latest.json`) menos ele mesmo, no formato do `sha256sum`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import _comum as c


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def notas(changelog: Path, versao: str) -> str:
    """Corpo da seção `## v<versao>` (até a próxima `## `), sem espaços nas pontas."""
    if not changelog.is_file():
        return ""
    texto = changelog.read_text(encoding="utf-8")
    m = re.search(rf"(?m)^## v{re.escape(versao)}(?:\s.*)?$", texto)
    if not m:
        return ""
    resto = texto[m.end():]
    fim = re.search(r"(?m)^## ", resto)
    return (resto[: fim.start()] if fim else resto).strip()


def gerar(
    dist: Path, repo: str, pack_dir: Path = c.PACK_DIR, agora: Callable[[], datetime] = _agora_utc
) -> dict:
    pack = c.ler_pack(pack_dir)
    versao = str(pack["version"])
    versoes = pack.get("versions", {})
    tag = f"pack-v{versao}"
    base = f"https://github.com/{repo}/releases/download/{tag}"
    raw = f"https://raw.githubusercontent.com/{repo}/{tag}"

    def arquivo(nome: str, obrigatorio: bool) -> dict | None:
        p = dist / nome
        if not p.is_file():
            if obrigatorio:
                raise FileNotFoundError(f"{p} não existe")
            return None
        return {"nome": nome, "url": f"{base}/{nome}", "bytes": p.stat().st_size,
                "sha256": _sha256(p)}

    for nome in ("mods.json", "manual.json"):
        if not (dist / nome).is_file():
            raise FileNotFoundError(f"{dist / nome} não existe")
    return {
        "schema": 1,
        "versao": versao,
        "tag": tag,
        "publicadoEm": _iso_z(agora()),
        "minecraft": str(versoes.get("minecraft", c.MC)),
        "neoforge": str(versoes.get("neoforge", c.NEOFORGE)),
        "arquivos": {
            "mrpack": arquivo(f"tensura-{versao}.mrpack", True),
            "zip": arquivo(f"tensura-{versao}.zip", True),
            "curseforge": arquivo(f"tensura-{versao}-curseforge.zip", False),
        },
        "modsJson": f"{base}/mods.json",
        "manualJson": f"{base}/manual.json",
        "packToml": f"{raw}/pack.toml",
        "changelog": f"{raw}/CHANGELOG.md",
        "notas": notas(pack_dir / "CHANGELOG.md", versao),
    }


def gravar_sha256sums(dist: Path) -> Path:
    linhas = [f"{_sha256(p)}  {p.name}\n" for p in sorted(dist.iterdir())
              if p.is_file() and p.name != "SHA256SUMS"]
    destino = dist / "SHA256SUMS"
    destino.write_text("".join(linhas), encoding="utf-8")
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera latest.json e SHA256SUMS (spec §4.4).")
    ap.add_argument("--dist", type=Path, required=True)
    ap.add_argument("--repo", required=True, help="<org>/tensura-pack")
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", a.repo):
        c.erro(f"erro: --repo inválido: {a.repo!r} (use <org>/<repo>)")
        return 2
    try:
        doc = gerar(a.dist, a.repo, a.pack)
    except FileNotFoundError as e:
        c.erro(f"erro: {e}")
        return 1
    if not doc["notas"]:
        c.erro(f"aviso: seção v{doc['versao']} do CHANGELOG.md vazia ou ausente")
    (a.dist / "latest.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    gravar_sha256sums(a.dist)
    print(a.dist / "latest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
