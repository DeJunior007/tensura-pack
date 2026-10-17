"""Licenças dos mods (D5, spec §2.6, §3).

Uso:
  licencas.py buscar [--pack DIR]   (rede) Modrinth + CFWidget → meta/licencas.json, 1 req/s
  licencas.py checar [--pack DIR]   (offline) classe A com licença fechada → erro;
                                    licença ausente p/ mod que iria ao .zip → aviso
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import _comum as c

USER_AGENT = "tensura-pack/1.0 (contato no README)"
MODRINTH_API = "https://api.modrinth.com/v2/project/{id}"
CFWIDGET_API = "https://api.cfwidget.com/{id}"
INTERVALO = 1.0  # segundos entre requisições

# CFWidget devolve o nome da licença (não SPDX); nomes desconhecidos ficam como vieram (= fechada).
_CF_NOMES = {
    "all rights reserved": "ARR",
    "mit license": "MIT",
    "mit": "MIT",
    "apache license 2.0": "Apache-2.0",
    "apache license version 2.0": "Apache-2.0",
    "bsd 2-clause license": "BSD-2-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "isc license": "ISC",
    "zlib license": "Zlib",
    "the unlicense": "Unlicense",
    "creative commons zero v1.0 universal": "CC0-1.0",
    "mozilla public license 2.0": "MPL-2.0",
    "gnu lesser general public license v2.1": "LGPL-2.1",
    "gnu lesser general public license v3.0": "LGPL-3.0",
    "gnu lesser general public license version 3 (lgplv3)": "LGPL-3.0",
    "gnu general public license v2.0": "GPL-2.0",
    "gnu general public license version 2 (gplv2)": "GPL-2.0",
    "gnu general public license v3.0": "GPL-3.0",
    "gnu general public license version 3 (gplv3)": "GPL-3.0",
    "gnu affero general public license v3.0": "AGPL-3.0",
    "european union public licence 1.2": "EUPL-1.2",
    "creative commons attribution 4.0": "CC-BY-4.0",
    "creative commons attribution-sharealike 4.0": "CC-BY-SA-4.0",
}


def spdx_cf(nome: str | None) -> str:
    if not nome:
        return ""
    return _CF_NOMES.get(nome.strip().lower(), nome.strip())


def baixar_http(url: str) -> bytes:  # pragma: no cover - rede
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def buscar(
    pack_dir: Path,
    baixar: Callable[[str], bytes],
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, dict]:
    """Consulta a licença de cada `.pw.toml` Modrinth/CF e grava `meta/licencas.json`.

    Mantém a entrada anterior se a consulta falhar (com aviso no stderr).
    """
    pack_dir = Path(pack_dir)
    destino = pack_dir / "meta" / "licencas.json"
    resultado = dict(c.ler_licencas(pack_dir))
    ultimo: float | None = None
    for mod in c.ler_mods(pack_dir):
        if mod.fonte == "modrinth":
            url, fonte = MODRINTH_API.format(id=mod.projeto or mod.id), "modrinth"
        elif mod.fonte == "curseforge" and mod.projeto:
            url, fonte = CFWIDGET_API.format(id=mod.projeto), "cfwidget"
        else:
            continue
        if ultimo is not None:
            espera = INTERVALO - (relogio() - ultimo)
            if espera > 0:
                dormir(espera)
        ultimo = relogio()
        try:
            dados = json.loads(baixar(url))
            if fonte == "modrinth":
                lic = ((dados.get("license") or {}).get("id")) or ""
            else:
                bruto = dados.get("license")
                if isinstance(bruto, dict):
                    bruto = bruto.get("id") or bruto.get("name")
                lic = spdx_cf(bruto)
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede/JSON vira aviso
            print(f"aviso: {mod.id}: falha ao consultar {url}: {e}", file=sys.stderr)
            continue
        resultado[mod.id] = {
            "licenca": lic,
            "fonte": fonte,
            "consultadoEm": agora().isoformat(timespec="seconds"),
        }
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(dict(sorted(resultado.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resultado


def checar(pack_dir: Path) -> tuple[list[str], list[str]]:
    """→ (erros, avisos)."""
    pack_dir = Path(pack_dir)
    meta = c.ler_meta(pack_dir)
    licencas = c.ler_licencas(pack_dir)
    erros: list[str] = []
    avisos: list[str] = []
    for mod in c.ler_mods(pack_dir):
        entrada = meta.get(mod.id, {})
        classe = str(entrada.get("classe", ""))
        lic = c.licenca_de(mod.id, meta, licencas)
        if classe == "A" and not c.licenca_aberta(lic):
            erros.append(
                f"{mod.id} é classe A com licença fechada ou ausente (\"{lic or ''}\"): "
                f"mude para B ou corrija a licença"
            )
        # vai ao .zip: modrinth/A que não é só-servidor
        vai_ao_zip = mod.lado != "server" and classe in ("modrinth", "A", "")
        if vai_ao_zip and classe != "A" and not lic:
            avisos.append(f"{mod.id} sem licença conhecida: fica fora do .zip")
    return erros, avisos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Licenças dos mods (buscar | checar).")
    ap.add_argument("acao", choices=["buscar", "checar"])
    ap.add_argument("--pack", type=Path, default=c.PACK_DIR)
    args = ap.parse_args(argv)
    if args.acao == "buscar":  # pragma: no cover - rede
        res = buscar(args.pack, baixar_http)
        print(f"{len(res)} licença(s) em meta/licencas.json")
        return 0
    erros, avisos = checar(args.pack)
    for a in avisos:
        print(f"aviso: {a}", file=sys.stderr)
    for e in erros:
        print(f"erro: {e}", file=sys.stderr)
    if erros:
        print(f"{len(erros)} erro(s).", file=sys.stderr)
        return 1
    print(f"licenças ok ({len(avisos)} aviso(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
