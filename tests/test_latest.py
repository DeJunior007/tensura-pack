"""CA-T6 — latest.py (latest.json §4.4 + SHA256SUMS)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

import latest
from fixtures.extra import montar_pack

REPO = "pedro/tensura-pack"
AGORA = lambda: datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)  # noqa: E731
CAMPOS = ["schema", "versao", "tag", "publicadoEm", "minecraft", "neoforge", "arquivos",
          "modsJson", "manualJson", "packToml", "changelog", "notas"]


@pytest.fixture
def pack(tmp_path):
    return montar_pack(tmp_path)


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    d.mkdir()
    (d / "tensura-0.3.9.mrpack").write_bytes(b"mrpack" * 10)
    (d / "tensura-0.3.9.zip").write_bytes(b"zip" * 1000)
    (d / "mods.json").write_text("{}")
    (d / "manual.json").write_text("{}")
    return d


def test_campos_e_urls(pack, dist):
    doc = latest.gerar(dist, REPO, pack, AGORA)
    assert list(doc) == CAMPOS
    assert doc["schema"] == 1 and doc["versao"] == "0.3.9" and doc["tag"] == "pack-v0.3.9"
    assert doc["publicadoEm"] == "2026-10-20T15:00:00Z"
    assert (doc["minecraft"], doc["neoforge"]) == ("1.21.1", "21.1.222")
    base = "https://github.com/pedro/tensura-pack/releases/download/pack-v0.3.9"
    assert doc["arquivos"]["mrpack"]["url"] == f"{base}/tensura-0.3.9.mrpack"
    assert doc["arquivos"]["zip"]["url"] == f"{base}/tensura-0.3.9.zip"
    assert doc["modsJson"] == f"{base}/mods.json"
    assert doc["manualJson"] == f"{base}/manual.json"
    raw = "https://raw.githubusercontent.com/pedro/tensura-pack/pack-v0.3.9"
    assert doc["packToml"] == f"{raw}/pack.toml"
    assert doc["changelog"] == f"{raw}/CHANGELOG.md"


def test_bytes_e_sha256(pack, dist):
    doc = latest.gerar(dist, REPO, pack, AGORA)
    for chave, nome in (("mrpack", "tensura-0.3.9.mrpack"), ("zip", "tensura-0.3.9.zip")):
        a = doc["arquivos"][chave]
        dados = (dist / nome).read_bytes()
        assert a["nome"] == nome and a["bytes"] == len(dados)
        assert a["sha256"] == hashlib.sha256(dados).hexdigest()


def test_curseforge_null_sem_arquivo_e_presente_com(pack, dist):
    assert latest.gerar(dist, REPO, pack, AGORA)["arquivos"]["curseforge"] is None
    (dist / "tensura-0.3.9-curseforge.zip").write_bytes(b"cf")
    cf = latest.gerar(dist, REPO, pack, AGORA)["arquivos"]["curseforge"]
    assert cf["nome"] == "tensura-0.3.9-curseforge.zip" and cf["bytes"] == 2


def test_notas_da_secao(pack, dist):
    (pack / "CHANGELOG.md").write_text(
        "# Changelog\n\n## v0.3.9 — 2026-10-10\n\n- + Create\n- ~ Terralith só no servidor\n\n"
        "## v0.3.8 — 2026-10-01\n\n- + JEI\n", encoding="utf-8")
    doc = latest.gerar(dist, REPO, pack, AGORA)
    assert doc["notas"] == "- + Create\n- ~ Terralith só no servidor"


def test_falta_arquivo_obrigatorio(pack, dist):
    (dist / "tensura-0.3.9.zip").unlink()
    with pytest.raises(FileNotFoundError):
        latest.gerar(dist, REPO, pack, AGORA)
    assert latest.main(["--dist", str(dist), "--repo", REPO, "--pack", str(pack)]) == 1


def test_repo_invalido_sai_2(pack, dist):
    assert latest.main(["--dist", str(dist), "--repo", "x y", "--pack", str(pack)]) == 2


def test_cli_grava_e_sha256sums_confere(pack, dist):
    assert latest.main(["--dist", str(dist), "--repo", REPO, "--pack", str(pack)]) == 0
    doc = json.loads((dist / "latest.json").read_text())
    assert doc["notas"] == "- + Create\n- + MineColonies"
    linhas = (dist / "SHA256SUMS").read_text().splitlines()
    nomes = sorted(l.split("  ", 1)[1] for l in linhas)
    assert nomes == sorted(["latest.json", "manual.json", "mods.json",
                            "tensura-0.3.9.mrpack", "tensura-0.3.9.zip"])
    if shutil.which("sha256sum") is None:
        pytest.skip("sha256sum não instalado")
    r = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=dist, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    (dist / "mods.json").write_text("{ }")
    r = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=dist, capture_output=True, text=True)
    assert r.returncode != 0
