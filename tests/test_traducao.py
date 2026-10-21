"""Tradução pt-BR: validador e montador do jar (traducao/)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "traducao"))
import montar_jar  # noqa: E402
import validar  # noqa: E402


def _amb(tmp_path, monkeypatch, en: dict, pt: dict | None):
    (tmp_path / "en").mkdir()
    (tmp_path / "pt_br").mkdir()
    (tmp_path / "en" / "x.json").write_text(json.dumps(en))
    if pt is not None:
        (tmp_path / "pt_br" / "x.json").write_text(json.dumps(pt, ensure_ascii=False))
    monkeypatch.setattr(validar, "AQUI", tmp_path)
    monkeypatch.setattr(montar_jar, "AQUI", tmp_path)


def test_valido(tmp_path, monkeypatch):
    _amb(tmp_path, monkeypatch, {"a": "Hello %s", "b": "§aGreen\\n%1$s and %2$s"},
         {"a": "Olá %s", "b": "§aVerde\\n%2$s e %1$s"})
    assert validar.validar("x") == []


def test_placeholder_perdido_e_chave_faltando(tmp_path, monkeypatch):
    _amb(tmp_path, monkeypatch, {"a": "Hello %s", "b": "Bye"}, {"a": "Olá"})
    erros = validar.validar("x")
    assert any("faltando" in e for e in erros) and any("códigos diferentes" in e for e in erros)


def test_jar_deterministico_e_lowcodefml(tmp_path, monkeypatch):
    _amb(tmp_path, monkeypatch, {"a": "Sword"}, {"a": "Espada"})
    j1, j2 = tmp_path / "1.jar", tmp_path / "2.jar"
    assert montar_jar.montar(j1)[:2] == (1, 1)
    montar_jar.montar(j2)
    assert j1.read_bytes() == j2.read_bytes()
    with zipfile.ZipFile(j1) as z:
        assert 'modLoader = "lowcodefml"' in z.read("META-INF/neoforge.mods.toml").decode()
        assert json.loads(z.read("assets/x/lang/pt_br.json")) == {"a": "Espada"}


def test_grupo_invalido_fica_fora_do_jar(tmp_path, monkeypatch):
    _amb(tmp_path, monkeypatch, {"a": "Hello %s"}, {"a": "Olá"})
    grupos, frases, pulados = montar_jar.montar(tmp_path / "j.jar")
    assert grupos == 0 and pulados == ["x"]
