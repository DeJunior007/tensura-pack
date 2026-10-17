"""Leitura compartilhada do pack (spec §2, §3).

Só stdlib. Os scripts de `pack/scripts/` importam este módulo como `_comum`
(rodam com `uv run python pack/scripts/<x>.py` a partir da raiz).
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
MC, NEOFORGE = "1.21.1", "21.1.262"

# §2.6 — redistribuição permitida (SPDX, sem diferenciar -only/-or-later)
LICENCAS_ABERTAS: frozenset[str] = frozenset(
    {
        "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib",
        "Unlicense", "CC0-1.0", "MPL-2.0", "LGPL-2.1", "LGPL-3.0", "GPL-2.0",
        "GPL-3.0", "AGPL-3.0", "EUPL-1.2", "CC-BY-4.0", "CC-BY-SA-4.0",
    }
)
_ABERTAS_MINUSC = {x.lower(): x for x in LICENCAS_ABERTAS}

LADOS = ("both", "client", "server")
# pasta do pack -> tipo do Mod
PASTAS_TIPO = {"mods": "mod", "resourcepacks": "resourcepack", "shaderpacks": "shader"}


@dataclass(frozen=True)
class Mod:
    id: str
    nome: str
    arquivo: str
    lado: str  # "both" | "client" | "server" ("" se o .pw.toml não tiver side)
    fonte: str  # "modrinth" | "curseforge" | "url"
    tipo: str  # "mod" | "resourcepack" | "shader"
    projeto: str | None  # mod-id Modrinth ou project-id CF
    url: str | None  # só p/ uso interno; nunca vai a mods.json
    hash_formato: str
    hash: str


def _ler_toml(caminho: Path) -> dict:
    with caminho.open("rb") as f:
        return tomllib.load(f)


def ler_pack(pack_dir: Path = PACK_DIR) -> dict:
    """`pack.toml` como dict."""
    return _ler_toml(Path(pack_dir) / "pack.toml")


def _mod_de_pwtoml(caminho: Path, tipo: str) -> Mod:
    d = _ler_toml(caminho)
    download = d.get("download", {}) or {}
    update = d.get("update", {}) or {}
    if "modrinth" in update:
        fonte = "modrinth"
        projeto = update["modrinth"].get("mod-id")
    elif "curseforge" in update or str(download.get("mode", "")).endswith("curseforge"):
        fonte = "curseforge"
        projeto = (update.get("curseforge") or {}).get("project-id")
    else:
        fonte, projeto = "url", None
    mod_id = caminho.name[: -len(".pw.toml")]
    return Mod(
        id=mod_id,
        nome=str(d.get("name", mod_id)),
        arquivo=str(d.get("filename", "")),
        lado=str(d.get("side", "")),
        fonte=fonte,
        tipo=tipo,
        projeto=None if projeto is None else str(projeto),
        url=download.get("url"),
        hash_formato=str(download.get("hash-format", "")),
        hash=str(download.get("hash", "")),
    )


def ler_mods(pack_dir: Path = PACK_DIR) -> list[Mod]:
    """Todos os `*.pw.toml` de mods/, resourcepacks/ e shaderpacks/, ordenados por id."""
    mods: list[Mod] = []
    for pasta, tipo in PASTAS_TIPO.items():
        d = Path(pack_dir) / pasta
        if d.is_dir():
            mods.extend(_mod_de_pwtoml(p, tipo) for p in sorted(d.glob("*.pw.toml")))
    return sorted(mods, key=lambda m: m.id)


def ler_meta(pack_dir: Path = PACK_DIR) -> dict[str, dict]:
    """`meta/mods.toml` (uma tabela por id). Ausente → {}."""
    p = Path(pack_dir) / "meta" / "mods.toml"
    return _ler_toml(p) if p.is_file() else {}


def ler_manual(pack_dir: Path = PACK_DIR) -> list[dict]:
    """Itens `[[mod]]` de `manual.toml`. Ausente → []."""
    p = Path(pack_dir) / "manual.toml"
    return list(_ler_toml(p).get("mod", [])) if p.is_file() else []


def ler_licencas(pack_dir: Path = PACK_DIR) -> dict[str, dict]:
    """`meta/licencas.json` (gerado por `licencas.py buscar`). Ausente → {}."""
    p = Path(pack_dir) / "meta" / "licencas.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def licenca_de(mod_id: str, meta: dict[str, dict], licencas: dict[str, dict]) -> str | None:
    """Licença efetiva: `licenca` de meta/mods.toml sobrepõe meta/licencas.json."""
    m = meta.get(mod_id, {})
    if m.get("licenca"):
        return str(m["licenca"])
    lic = licencas.get(mod_id, {}).get("licenca")
    return str(lic) if lic else None


def ler_lado_cliente(pack_dir: Path = PACK_DIR) -> list[str]:
    """Ids de `meta/lado-cliente.txt` (um por linha; `#` comenta)."""
    p = Path(pack_dir) / "meta" / "lado-cliente.txt"
    if not p.is_file():
        return []
    ids = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            ids.append(linha)
    return ids


def ler_fora(pack_dir: Path = PACK_DIR) -> list[tuple[str, str]]:
    """Linhas da tabela de `FORA.md` → [(id, nome)].

    O id vem do primeiro trecho entre crases da coluna "Mod"
    (ex.: ``Create: Steam 'n' Rails (`create-steam-n-rails`)``); sem crases, o id é o nome
    normalizado com hífens.
    """
    p = Path(pack_dir) / "FORA.md"
    if not p.is_file():
        return []
    saida = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha.startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        if not celulas or not celulas[0]:
            continue
        primeira = celulas[0]
        if primeira.lower() == "mod" or set(primeira) <= set("-: "):
            continue
        m = re.search(r"`([^`]+)`", primeira)
        nome = re.sub(r"\s*\(?`[^`]*`\)?", "", primeira).strip()
        mod_id = m.group(1).strip() if m else slug(nome)
        saida.append((mod_id, nome))
    return saida


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, sem pontuação nem espaços (casamento por nome, §2.5)."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"['’]", "", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def licenca_aberta(spdx: str | None) -> bool:
    """True se a licença está na lista aberta do §2.6 (ignora -only/-or-later/+ e caixa)."""
    if not spdx:
        return False
    s = spdx.strip()
    s = re.sub(r"(-only|-or-later|\+)$", "", s, flags=re.I)
    return s.lower() in _ABERTAS_MINUSC


_PAGINA_MODRINTH = {"mod": "mod", "resourcepack": "resourcepack", "shader": "shader"}


def pagina(mod: Mod, meta: dict) -> str:
    """Página pública do mod. `meta` = a entrada do mod em meta/mods.toml (ou {}).

    Modrinth → modrinth.com/<tipo>/<id>; CF/url → `pagina` do meta, senão a página CF pelo id.
    """
    if mod.fonte == "modrinth":
        return f"https://modrinth.com/{_PAGINA_MODRINTH.get(mod.tipo, 'mod')}/{mod.id}"
    if meta.get("pagina"):
        return str(meta["pagina"])
    return f"https://www.curseforge.com/minecraft/mc-mods/{mod.id}"


def erro(msg: str) -> None:
    print(msg, file=sys.stderr)
