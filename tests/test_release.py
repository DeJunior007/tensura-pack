"""CA-T8 — `pack/scripts/release` com `packwiz`/`gh` falsos (pack/tests/fakes/) e remote git local.

Cada teste monta um repo git temporário com `pack/` (fixture pack-ok + pack-extra e uma cópia
de `pack/scripts/`) e o remote `pack-publico` apontando para um bare repo local.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures.extra import montar_pack

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
FAKES = TESTS / "fakes"
RAIZ_REAL = TESTS.parents[1]

PREAMBULO = "- + Chunky\n- + Mouse Tweaks\n\n"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return r.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    pack = montar_pack(raiz)
    shutil.copytree(SCRIPTS, pack / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(RAIZ_REAL / ".gitignore", raiz / ".gitignore")
    ch = pack / "CHANGELOG.md"
    ch.write_text(ch.read_text(encoding="utf-8").replace(
        "# Changelog\n\n", "# Changelog\n\n" + PREAMBULO, 1), encoding="utf-8")
    _git(raiz, "init", "-q", "-b", "main")
    for k, v in {"user.name": "Teste", "user.email": "teste@example.invalid",
                 "commit.gpgsign": "false", "tag.gpgsign": "false"}.items():
        _git(raiz, "config", k, v)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicial")
    bare = tmp_path / "publico.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(raiz, "remote", "add", "pack-publico", str(bare))
    return raiz


def _rodar(repo: Path, *args: str, **env_extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PACK_REPO", "PACK_REMOTE")}
    env.update({
        "PATH": os.pathsep.join([str(FAKES), str(Path(sys.executable).parent), env["PATH"]]),
        "PY": sys.executable,
        "FAKE_LOG": str(repo.parent / "chamadas.log"),
        "FAKE_JARS": str(repo.parent / "jars"),
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    env.pop("FAKE_MANUAL", None)
    env.update(env_extra)
    return subprocess.run([str(repo / "pack" / "scripts" / "release"), *args], cwd=repo,
                          env=env, capture_output=True, text=True, timeout=120)


def _chamadas(repo: Path) -> list[str]:
    log = repo.parent / "chamadas.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _refs(bare: Path) -> str:
    return _git(bare, "for-each-ref", "--format=%(refname)")


def _passos(saida: str) -> list[str]:
    return [l[4:].split(".")[0] for l in saida.splitlines() if l.startswith("==> ")]


def test_dry_run(repo: Path):
    pack_toml = (repo / "pack" / "pack.toml").read_bytes()
    changelog = (repo / "pack" / "CHANGELOG.md").read_bytes()
    r = _rodar(repo, "minor", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _passos(r.stdout) == ["1", "2", "3", "4", "5", "6", "7–8", "9"]
    assert "versão nova: 0.4.0" in r.stdout
    # pack.toml/CHANGELOG reais intactos, sem commit, tag, push nem release
    assert (repo / "pack" / "pack.toml").read_bytes() == pack_toml
    assert (repo / "pack" / "CHANGELOG.md").read_bytes() == changelog
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "tag") == ""
    assert len(_git(repo, "log", "--oneline").splitlines()) == 1
    assert _refs(repo.parent / "publico.git") == ""
    chamadas = _chamadas(repo)
    assert not any(c.startswith("gh ") for c in chamadas)
    # ordem do packwiz: refresh (2), refresh (4), refresh na cópia sem B, export (5)
    cmds = [c.split("\t")[0] for c in chamadas]
    assert cmds == ["packwiz refresh"] * 3 + [
        f"packwiz modrinth export -o {repo}/pack/dist/tensura-0.4.0.mrpack"]
    dirs = [c.split("\t")[1] for c in chamadas]
    assert all(not d.startswith(str(repo)) for d in dirs)  # tudo na cópia temporária
    dist = repo / "pack" / "dist"
    assert sorted(p.name for p in dist.iterdir()) == [
        "SHA256SUMS", "latest.json", "manual.json", "mods.json",
        "tensura-0.4.0.mrpack", "tensura-0.4.0.zip"]


def test_manual_download_fora_do_manual_toml(repo: Path):
    r = _rodar(repo, "patch", "--dry-run",
               FAKE_MANUAL="Mod Sumido (mod-sumido) requires manual download")
    assert r.returncode == 1
    assert "mod-sumido" in r.stderr
    assert not (repo / "pack" / "dist" / "tensura-0.3.10.zip").exists()


def test_manual_download_formato_real_lista_o_mod(repo: Path):
    # texto real do packwiz (spec §0.1): cabeçalho sem id + uma linha por mod
    saida = (
        "Found 1 manual downloads; these mods are unable to be downloaded by packwiz "
        "(due to API limitations) and must be manually downloaded:\n"
        "Mod Sumido (mod-sumido-1.0.jar) from "
        "https://www.curseforge.com/minecraft/mc-mods/mod-sumido/files/123\n"
        "Once you have done so, place these files in /cache/import and re-run this command."
    )
    r = _rodar(repo, "patch", "--dry-run", FAKE_MANUAL=saida)
    assert r.returncode == 1
    assert "mod-sumido-1.0.jar" in r.stderr
    assert "Found 1 manual downloads" not in r.stderr


def test_manual_download_de_id_do_manual_toml_passa(repo: Path):
    r = _rodar(repo, "patch", "--dry-run",
               FAKE_MANUAL="FTB Library (ftb-library) requires manual download")
    assert r.returncode == 0, r.stdout + r.stderr


def test_changelog_vazio(repo: Path):
    ch = repo / "pack" / "CHANGELOG.md"
    ch.write_text(ch.read_text(encoding="utf-8").replace(PREAMBULO, ""), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "sem notas")
    r = _rodar(repo, "patch", "--dry-run")
    assert r.returncode == 1
    assert "CHANGELOG" in r.stderr
    assert _passos(r.stdout)[-1] == "3"
    # fora do --dry-run, pack.toml e CHANGELOG voltam ao commit
    r = _rodar(repo, "patch", "--sem-publicar", PACK_REPO="pedro/tensura-pack")
    assert r.returncode == 1
    assert _git(repo, "status", "--porcelain") == ""


def test_curseforge_com_mais_de_3_manuais(repo: Path):
    pack = repo / "pack"
    with (pack / "manual.toml").open("a", encoding="utf-8") as f:
        for i in (1, 2):
            f.write(f'\n[[mod]]\nid = "extra-{i}"\nnome = "Extra {i}"\nclasse = "C"\n'
                    f'lado = "both"\narquivo = "extra-{i}.jar"\n'
                    f'pagina = "https://www.curseforge.com/minecraft/mc-mods/extra-{i}"\n'
                    f'sha1 = "{"0" * 40}"\npasta = "mods"\n')
    with (pack / "meta" / "mods.toml").open("a", encoding="utf-8") as f:
        for i in (1, 2):
            f.write(f'\n[extra-{i}]\nnome = "Extra {i}"\ncategoria = "bibliotecas"\n'
                    f'planilha = "Bibliotecas"\nclasse = "C"\nnota = ""\n')
    _git(repo, "commit", "-q", "-am", "mais manuais")
    r = _rodar(repo, "patch", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert any("curseforge export" in c for c in _chamadas(repo))
    assert (pack / "dist" / "tensura-0.3.10-curseforge.zip").is_file()


def test_publica_no_bare_local(repo: Path):
    r = _rodar(repo, "minor", PACK_REPO="pedro/tensura-pack")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _passos(r.stdout) == ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    assert "PACK_VERSION=0.4.0" in r.stdout
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "log", "-1", "--format=%s") == "pack v0.4.0\n"
    assert 'version = "0.4.0"' in (repo / "pack" / "pack.toml").read_text(encoding="utf-8")
    bare = repo.parent / "publico.git"
    assert set(_refs(bare).split()) == {"refs/heads/main", "refs/tags/pack-v0.4.0"}
    arvore = _git(bare, "ls-tree", "--name-only", "main").split()
    assert "pack.toml" in arvore and "mods" in arvore and "dist" not in arvore
    assert 'version = "0.4.0"' in _git(bare, "show", "pack-v0.4.0:pack.toml")
    gh = [c.split("\t")[0] for c in _chamadas(repo) if c.startswith("gh ")]
    assert len(gh) == 1
    assert gh[0].startswith("gh release create pack-v0.4.0 --repo pedro/tensura-pack "
                            "--title Tensura SMP v0.4.0 --notes-file ")
    assert "--latest" in gh[0] and "tensura-0.4.0.mrpack" in gh[0] and "latest.json" in gh[0]
    ch = repo / "pack" / "CHANGELOG.md"
    texto = ch.read_text(encoding="utf-8")
    assert texto.startswith("# Changelog\n\n## v0.4.0 — ")
    assert texto.split("\n", 3)[3].startswith("\n" + PREAMBULO + "## v0.3.9 — ")
    # segunda release: push fast-forward sobre o split anterior
    ch.write_text(texto.replace("# Changelog\n\n", "# Changelog\n\n- correção\n\n", 1),
                  encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "notas 0.4.1")
    r = _rodar(repo, "patch", PACK_REPO="pedro/tensura-pack")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "refs/tags/pack-v0.4.1" in _refs(bare)
    assert 'version = "0.4.1"' in _git(bare, "show", "main:pack.toml")


def test_sem_publicar(repo: Path):
    r = _rodar(repo, "patch", "--sem-publicar", PACK_REPO="pedro/tensura-pack")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _git(repo, "tag") == "pack-v0.3.10\n"
    assert _refs(repo.parent / "publico.git") == ""
    assert not any(c.startswith("gh ") for c in _chamadas(repo))


def test_arvore_suja(repo: Path):
    (repo / "pack" / "mods" / "novo.pw.toml").write_text("x\n", encoding="utf-8")
    r = _rodar(repo, "patch", PACK_REPO="pedro/tensura-pack")
    assert r.returncode == 1
    assert _chamadas(repo) == []


@pytest.mark.parametrize("args, env", [
    (("patch",), {}),  # sem PACK_REPO fora do --dry-run
    (("--dry-run",), {}),
    (("enorme", "--dry-run"), {}),
    (("patch", "--dry-run", "--xyz"), {}),
])
def test_uso_errado(repo: Path, args, env):
    r = _rodar(repo, *args, **env)
    assert r.returncode == 2
    assert _chamadas(repo) == []
