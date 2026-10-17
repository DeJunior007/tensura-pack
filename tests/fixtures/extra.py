"""Ajudantes das fixtures da T1.2 (artefatos da release).

`pack-extra/` acrescenta ao `pack-ok/` um mod `server`-only (chunky) e um jar `client`
(mouse-tweaks), ambos Modrinth com licença aberta. Fica separado para não mudar o conjunto de
mods que os testes da T1.1 esperam. `montar_pack` copia `pack-ok` e mescla `pack-extra` por cima;
`montar_mrpack` gera um `.mrpack` sintético "bom" (como o `packwiz modrinth export` da cópia sem
classe B, spec §0.2) a partir do pack.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Callable

FIXTURES = Path(__file__).resolve().parent
PACK_OK = FIXTURES / "pack-ok"
PACK_EXTRA = FIXTURES / "pack-extra"

ENV = {
    "both": {"client": "required", "server": "required"},
    "client": {"client": "required", "server": "unsupported"},
    "server": {"client": "unsupported", "server": "required"},
}
PASTA_DO_TIPO = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}
DIR_OVERRIDES = {"both": "overrides", "client": "client-overrides", "server": "server-overrides"}


def conteudo_jar(mod_id: str) -> bytes:
    """Igual ao `conftest.conteudo_jar` (os hashes das fixtures batem com ele)."""
    return f"jar falso de {mod_id}\n".encode()


def montar_pack(tmp_path: Path) -> Path:
    """`pack-ok` + `pack-extra` numa pasta descartável."""
    destino = tmp_path / "pack"
    shutil.copytree(PACK_OK, destino)
    for p in sorted((PACK_EXTRA / "mods").glob("*.pw.toml")):
        shutil.copy2(p, destino / "mods" / p.name)
    meta = destino / "meta"
    with (meta / "mods.toml").open("a", encoding="utf-8") as f:
        f.write((PACK_EXTRA / "meta" / "mods.toml").read_text(encoding="utf-8"))
    with (meta / "lado-cliente.txt").open("a", encoding="utf-8") as f:
        f.write((PACK_EXTRA / "meta" / "lado-cliente.txt").read_text(encoding="utf-8"))
    lic = json.loads((meta / "licencas.json").read_text(encoding="utf-8"))
    lic.update(json.loads((PACK_EXTRA / "meta" / "licencas.json").read_text(encoding="utf-8")))
    (meta / "licencas.json").write_text(json.dumps(lic, indent=2) + "\n", encoding="utf-8")
    return destino


def montar_mrpack(
    pack_dir: Path,
    destino: Path,
    *,
    mexer_indice: Callable[[dict], None] | None = None,
    extras: dict[str, bytes] | None = None,
    lado_cf: dict[str, str] | None = None,
) -> Path:
    """`.mrpack` sintético a partir do pack (sem classe B/C).

    `mexer_indice` altera o `modrinth.index.json` antes de gravar; `extras` acrescenta entradas
    ao zip (caminho → bytes); `lado_cf` força o diretório de overrides de um jar CF (id → lado).
    """
    import _comum as c  # noqa: PLC0415 (pack/scripts já está no sys.path pelo conftest)

    meta = c.ler_meta(pack_dir)
    manuais = {m["id"] for m in c.ler_manual(pack_dir)}
    versao = c.ler_pack(pack_dir)["version"]
    arquivos: list[dict] = []
    entradas: dict[str, bytes] = {}
    for mod in c.ler_mods(pack_dir):
        classe = meta.get(mod.id, {}).get("classe")
        if classe in ("B", "C") or mod.id in manuais:
            continue
        dados = conteudo_jar(mod.id)
        caminho = f"{PASTA_DO_TIPO[mod.tipo]}/{mod.arquivo}"
        if mod.fonte == "modrinth":
            arquivos.append({
                "path": caminho,
                "hashes": {
                    "sha1": hashlib.sha1(dados).hexdigest(),
                    "sha512": hashlib.sha512(dados).hexdigest(),
                },
                "env": dict(ENV[mod.lado]),
                "downloads": [mod.url],
                "fileSize": len(dados),
            })
        else:
            lado = (lado_cf or {}).get(mod.id, mod.lado)
            entradas[f"{DIR_OVERRIDES[lado]}/{caminho}"] = dados
    for p in sorted((pack_dir / "config").rglob("*")):
        if p.is_file():
            entradas[f"overrides/{p.relative_to(pack_dir).as_posix()}"] = p.read_bytes()
    indice = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": versao,
        "name": "Tensura SMP",
        "dependencies": {"minecraft": "1.21.1", "neoforge": "21.1.262"},
        "files": arquivos,
    }
    if mexer_indice:
        mexer_indice(indice)
    entradas.update(extras or {})
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(indice, indent=1))
        for nome, dados in entradas.items():
            z.writestr(nome, dados)
    return destino
