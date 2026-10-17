# Pack Tensura SMP (packwiz)

Minecraft 1.21.1, NeoForge 21.1.262. Fonte do `.mrpack`/`.zip` publicados e do servidor
(packwiz-installer no itzg). Detalhes: `specs/tensura-site/spec.md` §2–§4.

## Ferramenta

`packwiz` em `~/.local/bin/packwiz`, build do workflow `Go` em `main`, commit **`170b22d`**
(spec §0.2). Nada de binário dentro do repo.

## Estrutura

- `pack.toml`, `index.toml`, `mods/*.pw.toml`, `resourcepacks/*.pw.toml` — o pack (só o packwiz mexe; o `<id>` = nome do arquivo é a chave em tudo).
- `meta/mods.toml` — nome, categoria, classe (`modrinth`/`A`/`B`/`C`), licença e nota de cada mod (lista do site).
- `meta/licencas.json` — gerado por `licencas.py buscar`; `meta/lado-cliente.txt` — ids `side = "client"` do relatório.
- `manual.toml` — classes B (também têm `.pw.toml`) e C (só aqui; distribuição bloqueada no CurseForge).
- `FORA.md` — o que não entra e por quê. `CHANGELOG.md` — notas por versão.

## Adicionar um mod

1. **Modrinth primeiro**, mesmo se o mod também estiver na CurseForge:
   `packwiz -y modrinth add <slug>` (dentro de `pack/`). Só na falta, CurseForge por id exato:
   `packwiz curseforge add --addon-id <projectID>` (a busca por nome não é confiável).
2. Dependências: o `add` só resolve **1 nível** e usa a mesma fonte do mod pai. No CurseForge,
   responda `n` às dependências que existem no Modrinth e adicione-as pelo Modrinth antes.
3. Confira o `side` (spec §2.4); ajuste à mão no `.pw.toml` se preciso.
4. Entrada em `meta/mods.toml` (`classe`; para CF, A ou B conforme a licença, §2.6). Classe B
   também ganha item em `manual.toml` (`arquivo`, `pagina`, `sha1` do `.pw.toml`).
5. `packwiz refresh`, `uv run python pack/scripts/licencas.py buscar`, depois
   `uv run python pack/scripts/checar.py` e `licencas.py checar` (raiz do repo).
6. Anote no topo do `CHANGELOG.md` (logo abaixo de `# Changelog`): `- + Mod`, `- − Mod`, `- ~ ajuste`.

## Release

```
pack/scripts/release patch|minor|major --dry-run      # tudo em cópia temporária, artefatos em pack/dist/
PACK_REPO=<org>/tensura-pack pack/scripts/release minor
```

Antes: árvore de `pack/` limpa e as notas no topo do `CHANGELOG.md` comitadas. A release roda
`refresh`, `checar.py`, `licencas.py checar`, sobe a versão, gera `.mrpack` (sem as B), `.zip`,
`-curseforge.zip` (B + C > 3), `mods.json`, `manual.json`, `latest.json`, `SHA256SUMS`, faz o
commit `pack vX.Y.Z`, `git subtree split` + tag e publica a GitHub Release. `pack/dist/` não vai
para o git. Instale o `git-subtree` antes da 1ª release real.
