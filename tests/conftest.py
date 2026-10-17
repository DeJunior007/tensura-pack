"""Fixtures do pack (spec §9, "Pack").

`fixtures/pack-ok/` é um mini-pack feito à mão (sem packwiz): 6 `.pw.toml` — create e jei
(Modrinth MIT), xaeros-world-map (Modrinth ARR), minecolonies (CF classe A, GPL-3.0-or-later),
ftb-library (CF classe B, ARR), slime-gui-pack (resourcepack Modrinth, side client) — mais
`manual.toml` (ftb-library B + ftb-teams C), `meta/`, `FORA.md` e `CHANGELOG.md` (v0.3.9).
Os hashes dos `.pw.toml`/`manual.toml` são de `conteudo_jar(id)`.
"""

from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
FIXTURES = TESTS / "fixtures"
PACK_OK = FIXTURES / "pack-ok"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def conteudo_jar(mod_id: str) -> bytes:
    """Bytes do "jar" falso de cada mod da fixture (os hashes batem com eles)."""
    return f"jar falso de {mod_id}\n".encode()


@pytest.fixture
def pack_ok(tmp_path: Path) -> Path:
    """Cópia descartável do mini-pack válido."""
    destino = tmp_path / "pack"
    shutil.copytree(PACK_OK, destino)
    return destino


@pytest.fixture(autouse=True)
def _sem_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste do pack abre conexão de rede."""

    def bloqueado(*a, **k):
        raise RuntimeError("rede proibida nos testes do pack")

    monkeypatch.setattr(socket, "create_connection", bloqueado)
    monkeypatch.setattr(socket.socket, "connect", bloqueado)
