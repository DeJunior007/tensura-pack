"""CA-T2 — licencas.py checar (offline), licenca_aberta e buscar com baixar falso."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import licencas
from _comum import LICENCAS_ABERTAS, licenca_aberta


@pytest.mark.parametrize("spdx", ["MIT", "GPL-3.0-or-later", "GPL-3.0-only", "LGPL-2.1+",
                                  "apache-2.0", "CC0-1.0", *sorted(LICENCAS_ABERTAS)])
def test_abertas(spdx):
    assert licenca_aberta(spdx)


@pytest.mark.parametrize("spdx", ["ARR", "LicenseRef-x", "LicenseRef-All-Rights-Reserved",
                                  "custom", "", None, "   ", "CC-BY-NC-4.0"])
def test_fechadas(spdx):
    assert not licenca_aberta(spdx)


def _lic(pack, mod_id, valor):
    p = pack / "meta/licencas.json"
    d = json.loads(p.read_text())
    if valor is None:
        d.pop(mod_id, None)
    else:
        d[mod_id] = {"licenca": valor, "fonte": "x", "consultadoEm": "2026-01-01T00:00:00+00:00"}
    p.write_text(json.dumps(d))


def test_fixture_ok(pack_ok, capsys):
    assert licencas.checar(pack_ok) == ([], [])
    assert licencas.main(["checar", "--pack", str(pack_ok)]) == 0


def test_a_com_arr_erro(pack_ok, capsys):
    _lic(pack_ok, "minecolonies", "ARR")
    erros, _ = licencas.checar(pack_ok)
    assert len(erros) == 1 and "minecolonies é classe A com licença fechada" in erros[0]
    assert licencas.main(["checar", "--pack", str(pack_ok)]) == 1


@pytest.mark.parametrize("valor", ["MIT", "GPL-3.0-or-later"])
def test_a_com_aberta_ok(pack_ok, valor):
    _lic(pack_ok, "minecolonies", valor)
    assert licencas.checar(pack_ok)[0] == []


def test_a_sem_licenca_erro(pack_ok):
    _lic(pack_ok, "minecolonies", None)
    assert licencas.checar(pack_ok)[0]


def test_meta_sobrepoe_licencas_json(pack_ok):
    _lic(pack_ok, "minecolonies", "ARR")
    t = (pack_ok / "meta/mods.toml").read_text()
    (pack_ok / "meta/mods.toml").write_text(t.replace('classe = "A"', 'classe = "A"\nlicenca = "MIT"'))
    assert licencas.checar(pack_ok)[0] == []


def test_ausente_no_zip_aviso(pack_ok, capsys):
    _lic(pack_ok, "jei", None)
    erros, avisos = licencas.checar(pack_ok)
    assert erros == [] and avisos == ["jei sem licença conhecida: fica fora do .zip"]
    assert licencas.main(["checar", "--pack", str(pack_ok)]) == 0
    assert "aviso: jei" in capsys.readouterr().err


class Relogio:
    def __init__(self):
        self.t = 100.0
        self.chamadas: list[float] = []  # instante de cada baixar

    def __call__(self):
        return self.t

    def dormir(self, s):
        assert s > 0
        self.t += s


def test_buscar_grava_licencas_e_respeita_1_req_s(pack_ok):
    (pack_ok / "meta/licencas.json").unlink()
    rel = Relogio()
    urls: list[str] = []
    respostas = {
        "https://api.modrinth.com/v2/project/LNytGWDc": {"license": {"id": "MIT"}},
        "https://api.modrinth.com/v2/project/u6dRKJwZ": {"license": {"id": "MIT"}},
        "https://api.modrinth.com/v2/project/NcUtCpym": {"license": {"id": "LicenseRef-All-Rights-Reserved"}},
        "https://api.modrinth.com/v2/project/aBcDeFgH": {"license": {"id": "CC-BY-4.0"}},
        "https://api.cfwidget.com/245506": {"license": "GNU General Public License v3.0"},
        "https://api.cfwidget.com/404465": {"license": "All Rights Reserved"},
    }

    def baixar(url: str) -> bytes:
        urls.append(url)
        rel.chamadas.append(rel.t)
        rel.t += 0.2  # a requisição "leva" 200 ms
        return json.dumps(respostas[url]).encode()

    agora = lambda: datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)  # noqa: E731
    res = licencas.buscar(pack_ok, baixar, relogio=rel, dormir=rel.dormir, agora=agora)

    assert sorted(urls) == sorted(respostas)
    gaps = [b - a for a, b in zip(rel.chamadas, rel.chamadas[1:])]
    assert all(g >= 1.0 - 1e-9 for g in gaps), gaps
    gravado = json.loads((pack_ok / "meta/licencas.json").read_text())
    assert gravado == res
    assert gravado["minecolonies"] == {"licenca": "GPL-3.0", "fonte": "cfwidget",
                                       "consultadoEm": "2026-10-17T12:00:00+00:00"}
    assert gravado["ftb-library"]["licenca"] == "ARR"
    assert gravado["create"]["fonte"] == "modrinth"
    assert set(gravado) == {"create", "jei", "xaeros-world-map", "slime-gui-pack",
                            "minecolonies", "ftb-library"}
    assert licencas.checar(pack_ok)[0] == []


def test_buscar_falha_mantem_anterior(pack_ok, capsys):
    antes = json.loads((pack_ok / "meta/licencas.json").read_text())
    rel = Relogio()

    def baixar(url):
        raise OSError("sem rede")

    res = licencas.buscar(pack_ok, baixar, relogio=rel, dormir=rel.dormir)
    assert res == antes
    assert "aviso: create" in capsys.readouterr().err
