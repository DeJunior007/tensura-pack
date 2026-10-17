"""CA-T4 — copiar_sem.py + verificar_mrpack.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import copiar_sem
import verificar_mrpack as vm
from fixtures.extra import PACK_OK, conteudo_jar, montar_mrpack, montar_pack

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pack(tmp_path):
    return montar_pack(tmp_path)


# copiar_sem

def test_copia_sem_classe_b(pack, tmp_path):
    destino = tmp_path / "copia"
    destino.mkdir()  # como o mktemp -d da release
    assert copiar_sem.copiar_sem(pack, destino, {"B"}) == ["ftb-library"]
    assert not (destino / "mods/ftb-library.pw.toml").exists()
    for i in ("create", "jei", "minecolonies", "chunky", "mouse-tweaks", "xaeros-world-map"):
        assert (destino / f"mods/{i}.pw.toml").is_file()
    assert (destino / "resourcepacks/slime-gui-pack.pw.toml").is_file()
    assert (destino / "config/exemplo.toml").is_file()
    assert (destino / "manual.toml").is_file()
    idx = (destino / "index.toml").read_text()
    assert "ftb-library" not in idx and "mods/create.pw.toml" in idx
    assert (pack / "mods/ftb-library.pw.toml").is_file()  # origem intacta


def test_copia_ignora_dist_e_destino_cheio(pack, tmp_path):
    (pack / "dist").mkdir()
    (pack / "dist/velho.mrpack").write_text("x")
    destino = tmp_path / "copia"
    copiar_sem.copiar_sem(pack, destino, {"B"})
    assert not (destino / "dist").exists()
    with pytest.raises(ValueError):
        copiar_sem.copiar_sem(pack, destino, {"B"})


def test_copiar_sem_cli(tmp_path):
    destino = tmp_path / "c"
    r = subprocess.run([sys.executable, str(SCRIPTS / "copiar_sem.py"), str(PACK_OK), str(destino),
                        "--classes", "B"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["ftb-library"]
    r = subprocess.run([sys.executable, str(SCRIPTS / "copiar_sem.py"), str(PACK_OK),
                        str(tmp_path / "d"), "--classes", "Z"], capture_output=True, text=True)
    assert r.returncode == 2


# verificar_mrpack

def test_mrpack_bom_sai_0(pack, tmp_path):
    arq = montar_mrpack(pack, tmp_path / "bom.mrpack")
    assert vm.verificar(arq, pack) == []
    assert vm.main([str(arq), "--pack", str(pack)]) == 0


def test_cli_real(pack, tmp_path):
    arq = montar_mrpack(pack, tmp_path / "bom.mrpack")
    r = subprocess.run([sys.executable, str(SCRIPTS / "verificar_mrpack.py"), str(arq),
                        "--pack", str(pack)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _erros(pack, tmp_path, **kw):
    arq = montar_mrpack(pack, tmp_path / "ruim.mrpack", **kw)
    erros = vm.verificar(arq, pack)
    assert vm.main([str(arq), "--pack", str(pack)]) == 1
    return erros


@pytest.mark.parametrize("pasta", ["overrides", "client-overrides", "server-overrides"])
def test_jar_b_embutido(pack, tmp_path, pasta):
    extras = {f"{pasta}/mods/ftb-library-neoforge-2101.1.10.jar": conteudo_jar("ftb-library")}
    erros = _erros(pack, tmp_path, extras=extras)
    assert len(erros) == 1 and "ftb-library" in erros[0]


def test_jar_c_renomeado_pego_pelo_sha1(pack, tmp_path):
    erros = _erros(pack, tmp_path, extras={"overrides/mods/outro-nome.jar": conteudo_jar("ftb-teams")})
    assert len(erros) == 1 and "ftb-teams" in erros[0]


def test_jar_b_em_files(pack, tmp_path):
    def mexer(i):
        i["files"].append({"path": "mods/ftb-library-neoforge-2101.1.10.jar", "hashes": {},
                           "env": {"client": "required", "server": "required"}, "downloads": []})
    erros = _erros(pack, tmp_path, mexer_indice=mexer)
    assert any("files" in e and "ftb-library" in e for e in erros)


def test_neoforge_errado(pack, tmp_path):
    erros = _erros(pack, tmp_path, mexer_indice=lambda i: i["dependencies"].update(neoforge="21.1.238"))
    assert len(erros) == 1 and "dependencies" in erros[0]


def _env(caminho, lado, valor):
    def mexer(i):
        for f in i["files"]:
            if f["path"] == caminho:
                f["env"][lado] = valor
    return mexer


def test_client_sem_server_unsupported(pack, tmp_path):
    erros = _erros(pack, tmp_path, mexer_indice=_env(
        "mods/MouseTweaks-neoforge-mc1.21-2.26.1.jar", "server", "optional"))
    assert len(erros) == 1 and "mouse-tweaks" in erros[0] and "env.server" in erros[0]


def test_resourcepack_client_sem_server_unsupported(pack, tmp_path):
    erros = _erros(pack, tmp_path, mexer_indice=_env(
        "resourcepacks/Slime-GUI-Pack-1.21.zip", "server", "required"))
    assert len(erros) == 1 and "slime-gui-pack" in erros[0]


def test_server_sem_client_unsupported(pack, tmp_path):
    erros = _erros(pack, tmp_path, mexer_indice=_env(
        "mods/Chunky-NeoForge-1.4.23.jar", "client", "optional"))
    assert len(erros) == 1 and "chunky" in erros[0] and "env.client" in erros[0]


def test_version_id_errado(pack, tmp_path):
    erros = _erros(pack, tmp_path, mexer_indice=lambda i: i.update(versionId="0.3.8"))
    assert len(erros) == 1 and "versionId" in erros[0]


def test_cf_no_diretorio_errado(pack, tmp_path):
    erros = _erros(pack, tmp_path, lado_cf={"minecolonies": "client"})
    assert len(erros) == 1 and "client-overrides" in erros[0] and "minecolonies" in erros[0]


def test_mod_modrinth_ausente(pack, tmp_path):
    def mexer(i):
        i["files"] = [f for f in i["files"] if "create" not in f["path"]]
    erros = _erros(pack, tmp_path, mexer_indice=mexer)
    assert len(erros) == 1 and "create" in erros[0]


def test_arquivo_inexistente_sai_2(tmp_path):
    assert vm.main([str(tmp_path / "nada.mrpack")]) == 2
