"""CA-T3 — mods_json.py (mods.json §4.2, manual.json §4.3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import mods_json
from fixtures.extra import montar_pack

AGORA = lambda: datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)  # noqa: E731
CAMPOS = ["id", "nome", "categoria", "lado", "tipo", "fonte", "pagina", "licenca", "manual", "nota"]


@pytest.fixture
def pack(tmp_path):
    return montar_pack(tmp_path)


def test_schema_exato(pack):
    doc, _ = mods_json.gerar(pack, AGORA)
    assert list(doc) == ["schema", "versao", "minecraft", "neoforge", "geradoEm", "total", "mods"]
    assert doc["schema"] == 1 and doc["versao"] == "0.3.9"
    assert (doc["minecraft"], doc["neoforge"]) == ("1.21.1", "21.1.262")
    assert doc["geradoEm"] == "2026-10-20T15:00:00Z"
    assert doc["total"] == len(doc["mods"]) == 9  # 8 .pw.toml + ftb-teams (C)
    for m in doc["mods"]:
        assert list(m) == CAMPOS
        assert m["lado"] in ("ambos", "cliente", "servidor")
        assert m["fonte"] in ("modrinth", "curseforge")
        assert isinstance(m["manual"], bool) and isinstance(m["nota"], str)


def test_lados_tipos_manual_e_licenca(pack):
    doc, _ = mods_json.gerar(pack, AGORA)
    por = {m["id"]: m for m in doc["mods"]}
    assert por["create"]["lado"] == "ambos"
    assert por["mouse-tweaks"]["lado"] == "cliente"
    assert por["chunky"]["lado"] == "servidor"
    assert por["slime-gui-pack"]["tipo"] == "resourcepack"
    assert por["slime-gui-pack"]["pagina"] == "https://modrinth.com/resourcepack/slime-gui-pack"
    assert por["create"]["pagina"] == "https://modrinth.com/mod/create"
    assert por["ftb-teams"]["manual"] is True and por["ftb-teams"]["fonte"] == "curseforge"
    assert por["ftb-library"]["manual"] is True
    assert por["minecolonies"]["manual"] is False
    assert por["create"]["licenca"] == "MIT"
    assert por["ftb-teams"]["licenca"] is None
    assert "curseforge.com" in por["ftb-teams"]["pagina"]


def test_ordem_categoria_e_nome(pack):
    doc, _ = mods_json.gerar(pack, AGORA)
    chaves = [(m["categoria"], mods_json._chave_nome(m["nome"])) for m in doc["mods"]]
    assert chaves == sorted(chaves)
    assert [m["id"] for m in doc["mods"]][:2] == ["ftb-library", "ftb-teams"]  # bibliotecas


def test_sem_url_hash_cdn(pack):
    doc, man = mods_json.gerar(pack, AGORA)
    texto = json.dumps(doc)
    for proibido in ("url", "hash", "filename", "cdn.modrinth.com", "forgecdn"):
        assert proibido not in texto, proibido
    assert mods_json.problemas(doc, man) == []


def test_problemas_pega_vazamento(pack):
    doc, man = mods_json.gerar(pack, AGORA)
    doc["mods"][0]["url"] = "https://cdn.modrinth.com/x.jar"
    assert len(mods_json.problemas(doc, man)) == 2


def test_manual_json(pack):
    _, man = mods_json.gerar(pack, AGORA)
    assert list(man) == ["schema", "versao", "mods"] and man["versao"] == "0.3.9"
    assert [m["id"] for m in man["mods"]] == ["ftb-library", "ftb-teams"]
    for m in man["mods"]:
        assert list(m) == ["id", "nome", "classe", "lado", "arquivo", "pagina", "sha1", "pasta"]
    assert man["mods"][1]["classe"] == "C"
    assert man["mods"][1]["sha1"] == "5283aa8a7ab394ea5834e380137bcc1557be92bf"


def test_cli_grava(pack, tmp_path):
    saida = tmp_path / "dist"
    assert mods_json.main(["--saida", str(saida), "--pack", str(pack)]) == 0
    doc = json.loads((saida / "mods.json").read_text())
    assert doc["total"] == 9
    assert json.loads((saida / "manual.json").read_text())["schema"] == 1


def test_cli_vazamento_sai_1(pack, tmp_path):
    t = (pack / "meta/mods.toml").read_text()
    (pack / "meta/mods.toml").write_text(t.replace(
        '[create]\nnome = "Create"', '[create]\nnome = "Create"\nnota = "baixe em cdn.modrinth.com"', 1
    ).replace('classe = "modrinth"\nnota = ""\n', 'classe = "modrinth"\n', 1))
    assert mods_json.main(["--saida", str(tmp_path / "d"), "--pack", str(pack)]) == 1
