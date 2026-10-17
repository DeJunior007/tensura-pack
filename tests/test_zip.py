"""CA-T5 — zip_fallback.py com `baixar` falso."""

from __future__ import annotations

import zipfile

import pytest

import zip_fallback as zf
from fixtures.extra import conteudo_jar, montar_mrpack, montar_pack

# URL → id (a fixture usa o mesmo filename na URL)
def _baixar_falso(pack, chamadas):
    import _comum as c
    por_url = {m.url: m.id for m in c.ler_mods(pack) if m.url}

    def baixar(url):
        chamadas.append(url)
        return conteudo_jar(por_url[url])
    return baixar


@pytest.fixture
def pack(tmp_path):
    return montar_pack(tmp_path)


@pytest.fixture
def gerado(pack, tmp_path):
    mr = montar_mrpack(pack, tmp_path / "t.mrpack")
    chamadas: list[str] = []
    arq = zf.gerar_zip(mr, tmp_path / "dist", pack, _baixar_falso(pack, chamadas))
    with zipfile.ZipFile(arq) as z:
        nomes = set(z.namelist())
        leia = z.read("LEIA-ME.txt").decode()
        dados = {n: z.read(n) for n in nomes}
    return arq, nomes, leia, dados, chamadas


def test_nome_e_estrutura(gerado):
    arq, nomes, _, _, _ = gerado
    assert arq.name == "tensura-0.3.9.zip"
    assert nomes == {
        "LEIA-ME.txt",
        "config/exemplo.toml",
        "mods/create-1.21.1-6.0.6.jar",
        "mods/jei-1.21.1-neoforge-19.21.0.247.jar",
        "mods/MouseTweaks-neoforge-mc1.21-2.26.1.jar",
        "mods/minecolonies-1.1.900-1.21.1.jar",  # classe A (overrides/)
        "resourcepacks/Slime-GUI-Pack-1.21.zip",
    }


def test_so_licenca_aberta_e_classe_a(gerado):
    _, nomes, _, dados, chamadas = gerado
    assert not any("Xaeros" in n for n in nomes)  # ARR
    assert not any("ftb" in n for n in nomes)  # B/C
    assert dados["mods/minecolonies-1.1.900-1.21.1.jar"] == conteudo_jar("minecolonies")
    assert not any("Xaeros" in u or "Chunky" in u for u in chamadas)


def test_sem_server_only(gerado):
    _, nomes, leia, _, chamadas = gerado
    assert not any("Chunky" in n for n in nomes)
    assert "Chunky" not in leia


def test_server_overrides_fica_fora(pack, tmp_path):
    mr = montar_mrpack(pack, tmp_path / "t.mrpack",
                       extras={"server-overrides/mods/so-servidor.jar": b"x",
                               "client-overrides/config/cliente.toml": b"y"})
    arq = zf.gerar_zip(mr, tmp_path / "dist", pack, _baixar_falso(pack, []))
    nomes = zipfile.ZipFile(arq).namelist()
    assert "mods/so-servidor.jar" not in nomes
    assert "config/cliente.toml" in nomes


def test_leia_me(gerado):
    _, _, leia, _, _ = gerado
    assert "NeoForge 21.1.222" in leia and "1.21.1" in leia
    assert "- Xaero's World Map — https://modrinth.com/mod/xaeros-world-map (pasta: mods)" in leia
    assert "- FTB Library — https://www.curseforge.com/minecraft/mc-mods/ftb-library-forge/files/5999999" in leia
    assert "- FTB Teams — https://www.curseforge.com/minecraft/mc-mods/ftb-teams-forge/files/5888888" in leia
    assert "Create" not in leia.split("Baixe à mão:")[1]


def test_sha1_divergente(pack, tmp_path):
    mr = montar_mrpack(pack, tmp_path / "t.mrpack")
    with pytest.raises(zf.ErroZip, match="sha1 divergente"):
        zf.gerar_zip(mr, tmp_path / "dist", pack, lambda url: b"adulterado")
    assert not (tmp_path / "dist/tensura-0.3.9.zip").exists()
    assert zf.main([str(mr), "--saida", str(tmp_path / "d"), "--pack", str(pack)],
                   baixar=lambda url: b"adulterado") == 1


def test_cli_ok(pack, tmp_path, capsys):
    mr = montar_mrpack(pack, tmp_path / "t.mrpack")
    assert zf.main([str(mr), "--saida", str(tmp_path / "d"), "--pack", str(pack)],
                   baixar=_baixar_falso(pack, [])) == 0
    assert (tmp_path / "d/tensura-0.3.9.zip").is_file()


def test_licenca_do_meta_sobrepoe(pack, tmp_path):
    t = (pack / "meta/mods.toml").read_text()
    (pack / "meta/mods.toml").write_text(t.replace(
        '[jei]\nnome = "Just Enough Items"', '[jei]\nlicenca = "ARR"\nnome = "Just Enough Items"'))
    mr = montar_mrpack(pack, tmp_path / "t.mrpack")
    arq = zf.gerar_zip(mr, tmp_path / "dist", pack, _baixar_falso(pack, []))
    z = zipfile.ZipFile(arq)
    assert not any("jei" in n for n in z.namelist())
    assert "https://modrinth.com/mod/jei" in z.read("LEIA-ME.txt").decode()
