"""CA-T7 — versao.py."""

from __future__ import annotations

from datetime import date

import pytest

import versao


@pytest.mark.parametrize(("nivel", "nova"), [("patch", "0.3.10"), ("minor", "0.4.0"),
                                             ("major", "1.0.0")])
def test_bump_a_partir_de_0_3_9(pack_ok, nivel, nova):
    toml_antes = (pack_ok / "pack.toml").read_text()
    assert versao.subir(pack_ok, nivel, hoje=date(2026, 10, 20)) == nova

    depois = (pack_ok / "pack.toml").read_text()
    la, ld = toml_antes.splitlines(), depois.splitlines()
    assert len(la) == len(ld)
    dif = [(a, b) for a, b in zip(la, ld) if a != b]
    assert dif == [('version = "0.3.9"', f'version = "{nova}"')]

    cl = (pack_ok / "CHANGELOG.md").read_text()
    assert cl.startswith(f"# Changelog\n\n## v{nova} — 2026-10-20\n\n## v0.3.9 — 2026-10-10\n")


def test_main_imprime_versao(pack_ok, capsys):
    assert versao.main(["minor", "--pack", str(pack_ok)]) == 0
    assert capsys.readouterr().out.strip() == "0.4.0"
    assert f"## v0.4.0 — {versao.hoje_sp().isoformat()}" in (pack_ok / "CHANGELOG.md").read_text()


@pytest.mark.parametrize("ruim", ["0.3", "v0.3.9", "0.3.9-beta", "01.2.3", ""])
def test_versao_invalida_sai_1(pack_ok, capsys, ruim):
    t = (pack_ok / "pack.toml").read_text()
    (pack_ok / "pack.toml").write_text(t.replace('version = "0.3.9"', f'version = "{ruim}"'))
    assert versao.main(["patch", "--pack", str(pack_ok)]) == 1
    assert "versão inválida" in capsys.readouterr().err
    assert "## v" in (pack_ok / "CHANGELOG.md").read_text()  # changelog intacto
    assert (pack_ok / "CHANGELOG.md").read_text().count("## v") == 1


def test_nivel_invalido_sai_2(pack_ok):
    with pytest.raises(SystemExit) as e:
        versao.main(["mega", "--pack", str(pack_ok)])
    assert e.value.code == 2


def test_changelog_ausente_e_criado(pack_ok):
    (pack_ok / "CHANGELOG.md").unlink()
    versao.subir(pack_ok, "patch", hoje=date(2026, 1, 2))
    assert (pack_ok / "CHANGELOG.md").read_text() == "# Changelog\n\n## v0.3.10 — 2026-01-02\n\n"
