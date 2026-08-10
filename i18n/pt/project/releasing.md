# Processo de Release

## Versionamento

Este projeto segue o [Semantic Versioning](https://semver.org/):

```
vMAJOR.MINOR.PATCH
```

- **Major**: mudanças que quebram a API
- **Minor**: novas funcionalidades, compatíveis com versões anteriores
- **Patch**: correções de bugs

## Nomes de Código (opcional)

Releases podem ter um nome de código associado à versão. A tag git é sempre `vX.Y.Z`
(legível por máquina). O título da release no GitHub inclui o nome de código (legível por
humanos).

Exemplos:

- `v0.2.0 "Tadini"` — capitão do time
- `v1.0.0 "CBR 2026"` — nome da competição
- `v1.1.0 "Mangalarga"` — nome de código interno

## Checklist de Release

### 1. PR de bump de versão

Crie um PR que atualiza a versão:

- `nectar/pyproject.toml` → `version = "X.Y.Z"`
- `nectar/package.xml` → `<version>X.Y.Z</version>`
- `CITATION.cff` → `version: X.Y.Z` e `date-released`

O CI roda `code-quality` (lint) e `pr-check` (build Docker Humble + `verify` +
`verify-functional`) no PR.

### 2. Merge para main

Depois da revisão, faça o merge do PR. O CI roda no push para `main`:

- `build-test-{humble,jazzy,kilted}` — build Docker + `verify` + `verify-functional` (+ RealSense onde habilitado; Humble também em amd64 e arm64)
- `docs.yml` — builda e faz deploy do site de documentação no GitHub Pages

Verifique a [aba Actions](https://github.com/Black-Bee-Drones/nectar-sdk/actions) — tudo
verde antes de prosseguir.

### 3. Crie a release no GitHub

- Vá para [Releases](https://github.com/Black-Bee-Drones/nectar-sdk/releases/new)
- Tag: `vX.Y.Z` (crie uma nova tag, apontando para `main`)
- Título: `vX.Y.Z "Nome de Código"`
- Inclua notas de migração de breaking changes quando aplicável (veja a descrição do PR de merge)
- Aponte para o [site de documentação](https://black-bee-drones.github.io/nectar-sdk/) no corpo da release
- Clique em "Generate release notes" para o changelog, depois publique

### 4. Automaticamente pelo CI

`docker-push.yml` é disparado ao publicar a release. Para cada distro (Humble, Jazzy,
Kilted) e arquitetura (amd64, arm64):

1. Builda a imagem Docker com RealSense e todos os drivers de drone (`INSTALL_DRONE=all`)
2. Roda `verify` + `verify-functional` + `realsense-verify`
3. **Somente se todos os checks passarem para aquela distro**: faz push dos manifests multi-arch para o Docker Hub

As distros são independentes — uma falha no Kilted não bloqueia o tagging de Humble/Jazzy.

Para republicar tags do Docker sem uma nova release no GitHub, rode
**Actions → Docker Push → Run workflow** com o `release_tag` desejado (por exemplo,
`v1.1.0`) e `distros`.

## Site de documentação (GitHub Pages)

- **URL:** [black-bee-drones.github.io/nectar-sdk](https://black-bee-drones.github.io/nectar-sdk/)
- **Fonte:** `website/` (páginas autorais), `docs/`, e os READMEs dos módulos, montados por `scripts/docs/sync_readmes.py`
- **Workflow:** `.github/workflows/docs.yml` — build no PR; build + deploy no push para `main`
- **Configuração do repositório (única):** Settings → Pages → Build and deployment → **GitHub Actions**
- **Preview local:** `make docs-install && make docs-serve`

## Docker Hub

As imagens são enviadas ao [Docker Hub](https://hub.docker.com/r/blackbeedrones/nectar-sdk)
em toda release.

| Padrão de tag | Exemplo | Conteúdo |
|---|---|---|
| `:<distro>` | `humble`, `jazzy`, `kilted` | Última release daquela distro |
| `:<distro>-vX.Y.Z` | `humble-v1.1.0` | Release específica |

Baixe e rode:

```bash
docker pull blackbeedrones/nectar-sdk:humble
docker run -it --rm --net=host blackbeedrones/nectar-sdk:humble
```

## Workflows de CI

| Workflow | Gatilho | Distros | O que faz |
|---|---|---|---|
| `code-quality.yml` | PR para `main` ou `dev` | — | Lint + format (~30s) |
| `pr-check.yml` | PR para `main` | Humble (amd64) | Build Docker + `verify` + `verify-functional` |
| `build-test-humble.yml` | Push para `main`, semanal (seg 05:00 UTC) | Humble (amd64 + arm64) | Build Docker + `verify` + `verify-functional` + RealSense |
| `build-test-jazzy.yml` | Push para `main`, semanal (seg 05:00 UTC) | Jazzy | Build Docker + `verify` + `verify-functional` + RealSense |
| `build-test-kilted.yml` | Push para `main`, semanal (seg 05:00 UTC) | Kilted | Build Docker + `verify` + `verify-functional` + RealSense |
| `docs.yml` | PR (build) / push para `main` (build + deploy) | — | Site Zensical; faz deploy no GitHub Pages |
| `docker-push.yml` | Release no GitHub / dispatch manual | Todas as 3 × amd64 + arm64 (independente por distro) | Build → `verify` + `verify-functional` + RealSense → push para o Docker Hub |

A lógica de build e verify do Docker é compartilhada via `_build-verify.yml` (workflow
reutilizável). O `docker-push.yml` espelha os mesmos passos de verificação antes de publicar
as imagens de release.
