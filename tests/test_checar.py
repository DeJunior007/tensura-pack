"""CA-T1 — checar.py."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import checar
TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
PACK_OK = TESTS / "fixtures" / "pack-ok"


def _troca(arq: Path, antes: str, depois: str) -> None:
    t = arq.read_text(encoding="utf-8")
    assert antes in t, antes
    arq.write_text(t.replace(antes, depois), encoding="utf-8")


def test_fixture_valida_sai_0(pack_ok, capsys):
    assert checar.checar(pack_ok) == []
    assert checar.main(["--pack", str(pack_ok)]) == 0


def test_cli_real_sai_0_na_fixture():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "checar.py"), "--pack", str(PACK_OK)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def _sem_side(p):
    _troca(p / "mods/jei.pw.toml", 'side = "both"\n', "")


def _cliente_both(p):
    _troca(p / "resourcepacks/slime-gui-pack.pw.toml", 'side = "client"', 'side = "both"')


def _fora_presente(p):
    (p / "mods/create-steam-n-rails.pw.toml").write_text(
        (p / "mods/create.pw.toml").read_text().replace('"Create"', "\"Create: Steam 'n' Rails\"")
    )
    with (p / "meta/mods.toml").open("a") as f:
        f.write('\n[create-steam-n-rails]\nnome = "Steam n Rails"\nclasse = "modrinth"\n')


def _sem_meta(p):
    _troca(p / "meta/mods.toml", "[jei]", "[jei-velho]")


def _cf_sem_classe(p):
    _troca(p / "meta/mods.toml", 'classe = "A"', 'classe = "modrinth"')


def _b_sem_manual(p):
    t = (p / "manual.toml").read_text()
    (p / "manual.toml").write_text(t[t.index('[[mod]]\nid = "ftb-teams"'):])


def _c_com_pwtoml(p):
    (p / "mods/ftb-teams.pw.toml").write_text(
        (p / "mods/ftb-library.pw.toml").read_text().replace("FTB Library", "FTB Teams")
    )


def _versoes(p):
    _troca(p / "pack.toml", 'neoforge = "21.1.262"', 'neoforge = "21.1.200"')


def _versoes_extra(p):
    _troca(p / "pack.toml", 'neoforge = "21.1.262"', 'neoforge = "21.1.262"\nfabric = "0.16.0"')


@pytest.mark.parametrize(
    ("defeito", "mensagem"),
    [
        (_sem_side, r"jei\.pw\.toml sem side"),
        (_cliente_both, r"slime-gui-pack está em meta/lado-cliente\.txt .*side = \"both\""),
        (_fora_presente, r"create-steam-n-rails está em FORA\.md"),
        (_sem_meta, r"jei\.pw\.toml sem entrada em meta/mods\.toml"),
        (_cf_sem_classe, r"minecolonies é CurseForge sem classe A ou B"),
        (_b_sem_manual, r"ftb-library é classe B sem item em manual\.toml"),
        (_c_com_pwtoml, r"ftb-teams é classe C mas tem \.pw\.toml"),
        (_versoes, r"\[versions\] deve ser exatamente"),
        (_versoes_extra, r"\[versions\] deve ser exatamente"),
    ],
    ids=lambda x: getattr(x, "__name__", "msg"),
)
def test_cada_defeito_sai_1_com_mensagem(pack_ok, capsys, defeito, mensagem):
    defeito(pack_ok)
    assert checar.main(["--pack", str(pack_ok)]) == 1
    err = capsys.readouterr().err
    assert re.search(mensagem, err), err
    assert re.search(r"^\d+ erro\(s\)\.$", err, re.M)


def test_fora_casado_por_nome_sem_crases(pack_ok, capsys):
    (pack_ok / "FORA.md").write_text("| Mod | Motivo | Troca sugerida |\n|---|---|---|\n"
                                      "| Just Enough Items | teste | EMI |\n")
    erros = checar.checar(pack_ok)
    assert erros == ["jei está em FORA.md mas continua no pack"]


def test_uso_errado_sai_2():
    with pytest.raises(SystemExit) as e:
        checar.main(["--nao-existe"])
    assert e.value.code == 2
