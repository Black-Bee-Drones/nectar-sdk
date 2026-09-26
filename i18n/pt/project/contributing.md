# Contribuindo com o Nectar SDK

Discuta mudanças significativas via [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues)
ou [Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) antes de
implementar, e leia primeiro o [Código de Conduta](code-of-conduct.md).

## Issues e Pedidos de Funcionalidade

### Relatando Bugs

Crie relatos de bug que sejam:

- **Reproduzíveis**: inclua os passos para reproduzir o problema
- **Específicos**: números de versão, SO, detalhes de hardware
- **Únicos**: procure primeiro nas issues existentes
- **Delimitados**: um bug por relato

### Pedidos de Funcionalidade

Verifique as [Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) por
conversas em andamento antes de abrir um novo pedido.

## Configuração de Desenvolvimento

### Git LFS

Este repositório usa o [Git LFS](https://git-lfs.github.com/) para rastrear arquivos
binários grandes (imagens, vídeos, pesos de modelo etc.). Instale o Git LFS antes de clonar:

```bash
git lfs install

git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
```

O Git LFS trata automaticamente os arquivos grandes definidos em `.gitattributes`. Ao
adicionar imagens, vídeos ou outros arquivos grandes, eles são automaticamente rastreados
pelo LFS.

**Nota:** se você clonou antes do Git LFS ser configurado, talvez precise baixar os
arquivos LFS:

```bash
git lfs pull
```

### Ambiente Python

O SDK instala as dependências Python com [uv](https://github.com/astral-sh/uv) em uma venv
compartilhada do workspace (`$WORKSPACE/.venv`), reutilizada por todos os pacotes do
workspace. Veja o [guia de instalação](../setup/index.md#ambiente-python).

### Hooks de Pre-commit

Instale os hooks do [pre-commit](https://pre-commit.com/) (configuração única):

```bash
pip install pre-commit
pre-commit install
```

Depois de `pre-commit install`, os hooks rodam **automaticamente em todo `git commit`** —
eles verificam somente os arquivos staged, corrigem automaticamente o que puderem, e abortam
o commit se alguma alteração foi feita. Basta `git add` nas correções e commitar de novo.

### Antes de Fazer Push

Sempre rode o check completo antes de fazer push (o mesmo comando que o CI roda):

```bash
make check

# or equivalently: pre-commit run --all-files

```

Isso valida **todos os arquivos** (Python, Markdown, YAML, shell scripts) quanto a:

- Espaços em branco no final da linha e newlines ausentes no final do arquivo
- Erros de lint do Python (imports não usados, nomes indefinidos)
- Ordenação de imports
- Formatação de código

### Comandos Rápidos

```bash
make check       # run all checks (same as CI)
make lint        # Python lint only (ruff check)
make lint-fix    # Python lint + auto-fix (ruff check --fix)
make format      # Python format only (ruff format)
```

Use `make lint` / `make format` durante o desenvolvimento para feedback rápido em arquivos
Python. Use `make check` antes de fazer push para garantir que o CI vai passar.

## Processo de Pull Request

### 1. Faça um Fork e Clone

```bash

# Fork via GitHub UI, then:

git clone git@github.com:YOUR_USERNAME/nectar-sdk.git
cd nectar-sdk
git remote add upstream git@github.com:Black-Bee-Drones/nectar-sdk.git
```

### 2. Crie uma Branch de Feature

```bash
git checkout -b feat/your-feature-name

# or

git checkout -b fix/bug-description
```

**Nomenclatura de Branches**:

- `feat/` - Novas funcionalidades
- `fix/` - Correções de bugs
- `docs/` - Somente documentação
- `refactor/` - Refatoração de código
- `test/` - Adições/correções de testes

### 3. Faça as Alterações

Siga o estilo de código do projeto:

- **Python**: siga o [PEP 8](https://peps.python.org/pep-0008/)
- **Docstrings**: use o [estilo NumPy](https://numpydoc.readthedocs.io/en/latest/format.html)
- **Type hints**: inclua anotações de tipo para APIs públicas

### 4. Faça Commit com Conventional Commits

Seguimos o [Conventional Commits](https://www.conventionalcommits.org):

```bash

# Format: type(scope): description

git commit -m "feat(control): add obstacle avoidance strategy"
git commit -m "fix(vision): resolve camera initialization race condition"
git commit -m "docs(readme): update installation instructions"
```

**Tipos**:

| Tipo | Descrição |
|------|-------------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Documentação |
| `style` | Formatação (sem alteração de código) |
| `refactor` | Reestruturação de código |
| `test` | Adições de teste |
| `chore` | Build/ferramental |

### 5. Faça Push e Crie o PR

```bash
git push origin feat/your-feature-name
```

Depois abra um Pull Request no GitHub usando nosso
[template de PR](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/.github/PULL_REQUEST_TEMPLATE.md).

## Diretrizes de Código

### Documentação

- Atualize o README.md do módulo ao adicionar funcionalidades
- Adicione docstrings às classes e métodos públicos
- Inclua exemplos de uso para novas APIs

**Convenções de README** (padrão de excelência: [`control/mavros/README.md`](../modules/control/mavros.md)):

- **Estrutura (progressive disclosure)**: comece com um propósito de uma linha, depois um snippet executável de **visão rápida** (o caso comum), depois **Conceitos** (prosa curta + um diagrama de nível médio), depois um **Uso** orientado a tarefas, depois uma seção de **Referência** para tabelas exaustivas (tópicos/serviços/parâmetros/tipos). O Uso vem antes do diagrama de classes detalhado, nunca depois de uma parede dele. Mantenha a prosa concisa e técnica — sem buzzwords, sem repetição.
- **Fonte única de verdade**: documente a lógica compartilhada uma única vez e aponte para ela; não repita a mesma coisa em dois READMEs. A lógica de voo compartilhada vive em [Vehicle core](../modules/control/vehicle.md) (especificidades do ArduPilot em [ArduPilot](../modules/control/ardupilot.md)); o VSLAM indoor em [Localization](../modules/control/localization/index.md); a instalação no [Guia de instalação](../setup/index.md); o Docker no [Guia Docker](../setup/docker.md); a simulação em [Simulation](../modules/simulation.md). Os READMEs dos módulos concentram a profundidade técnica; o [site de documentação](https://black-bee-drones.github.io/nectar-sdk/) os espelha por meio de `scripts/docs/sync_readmes.py`. O **README raiz** é uma landing page curta do GitHub — aponte para o site, não duplique tabelas de instalação, diagramas de arquitetura ou índices de módulo ali.
- **Diagramas (Mermaid)**: mantenha um diagrama por README, em uma seção **Conceitos** *depois* do uso de visão rápida. O Zensical renderiza Mermaid no lado do cliente e adapta fontes/cores ao esquema claro/escuro ativo, e todo diagrama tem clique para zoom/pan (veja `website/javascripts/`). Para os diagramas **técnicos** (classe, sequência, estado), confie no tema — **não** defina cores, para que fiquem legíveis nos dois esquemas. Reserve cores para o diagrama de alto nível de **arquitetura/visão geral**, onde uma paleta `classDef` curada (`fill:` em tom médio com um `color:` de texto explícito) ajuda a compreensão e funciona nos dois esquemas. Use o layout **ELK** (`config: { layout: elk }` no frontmatter do diagrama) somente para fluxogramas densos no **site** — o Mermaid do GitHub não tem ELK, então nunca coloque `layout: elk` em um README que também deve renderizar no GitHub. Evite envolver o Mermaid em `<details>`/colapsáveis (a fence não renderiza dentro de blocos raw-HTML). Git graphs renderizam, mas não seguem o tema e são fracos no mobile — use com moderação.
- **Renderiza no parser estrito**: o site de documentação usa Python-Markdown, que é mais estrito que o GitHub. Coloque uma linha em branco antes de toda lista, tabela e bloco de código com fence (regras `MD022`/`MD031`/`MD032`/`MD058`, aplicadas pelo `markdownlint-cli2` no pre-commit e no CI). Markdown que passa pelo linter renderiza tanto no site quanto no GitHub; o inverso não é garantido. Faça o preview localmente com `make docs-serve`.
- **Tabs e admonitions são exclusivos do site**: tabs de conteúdo (`=== "..."`) e admonitions `!!!`/`???` renderizam somente no site de documentação, não no GitHub. Use-os nas páginas autorais de `website/` e nos guias site-first sob `docs/` (setup, Docker), onde eles carregam a escolha do leitor (backend, câmera, SO) do início ao fim. READMEs de módulo e de exemplo também são exibidos no GitHub, então ali apresente alternativas como **blocos com fence e rótulo em negrito** separados (não tabs) e use blockquotes simples (`> **Warning:** ...`) para notas. Uma fence que usa comentários `#` como cabeçalhos de caso/variante deve se tornar blocos com rótulo em negrito (ou uma tabela) em um README, e um grupo de tabs em uma página do site.
- **Texto de link legível**: nunca use um caminho como o texto visível do link (`[vehicle/README.md](...)`, `[control/px4/config](...)`). Escreva um título legível (`[Vehicle core](...)`, `[PX4 config](...)`). Apontadores inline para arquivo-fonte (`([`sequencer.py`](sequencer.py))`) são aceitáveis. Links de símbolo → API gerada pertencem somente às páginas de `website/` (um link de README para `api/*.md` não é seguro para renderização dupla).
- **Mantenha-se fiel ao código**: todo comando, flag, tópico e nome de classe deve corresponder ao código. Prefira flags reais de argparse / nomes de parâmetros reais em vez de inventados.
- **Ao adicionar um módulo**: atualize o README do módulo e seu índice pai; se for uma nova área de nível superior, adicione **um bullet** em Features no README raiz apontando para a página correspondente no [site de documentação](https://black-bee-drones.github.io/nectar-sdk/). Siga [Adicionando um componente](#adicionando-um-componente) abaixo.

**Exemplo de Docstring**:

```python
def move_to(
    self,
    x: float,
    y: float,
    z: float,
    precision: float = 0.2,
) -> bool:
    """
    Navigate to a position in the world frame.

    Parameters
    ----------
    x : float
        Target X position in meters.
    y : float
        Target Y position in meters.
    z : float
        Target Z position (altitude) in meters.
    precision : float, optional
        Position tolerance in meters. Default is 0.2.

    Returns
    -------
    bool
        True if target reached within timeout, False otherwise.

    Examples
    --------
    >>> drone.move_to(x=2.0, y=1.0, z=1.5, precision=0.3)
    True
    """
```

### Testes

A suíte funcional vive em
[`nectar/test/`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/nectar/test) (ela
**não** é instalada com o pacote) e é `pytest` puro:

- `nectar/test/functional/` — um `test_<module>.py` por módulo do SDK. Cada teste realiza
  uma *operação real* sobre entradas sintéticas ou um loopback. Os testes se auto-pulam
  (nunca falham) quando uma dependência opcional está ausente, via
  `pytest.importorskip(...)`.
- `nectar/test/hardware/` — checks condicionados a dispositivo (RealSense, OAK-D),
  marcados como `hardware` e **desselecionados por padrão**.
- `nectar/test/conftest.py` + `nectar/test/helpers.py` — fixtures (`ros_node`, `fake_fcu`,
  `qt_app`) e o FCU de loopback.

Rode:

```bash
make verify-functional                      # all modules (hardware/gpu deselected)
make verify-functional MODULE="vision control"   # subset -> pytest -m "vision or control"
make test                                   # colcon test: the suite + cmake/xml lint
make verify-hardware                         # opt in to device checks on the rig

# (equivalently, from the package dir: cd nectar && pytest test/hardware -m hardware)

```

Diretrizes:

- **Adicione um teste para toda nova funcionalidade.** Coloque-o no
  `test/functional/test_<module>.py` correspondente, marque o módulo com `pytestmark =
  pytest.mark.<module>`, e condicione qualquer coisa que precise de dispositivo/GPU/sim/rede
  com os markers `hardware` / `gpu` / `sim` / `network` (registrados em `pyproject.toml`).
  Faça assert com `assert` simples; pule com `pytest.skip(...)` / `pytest.importorskip(...)`
  — nunca falhe por uma dependência opcional ausente.
- **Faça lint/format com o ruff** (a única fonte de verdade — `make lint` / `make format`,
  também aplicado pelo pre-commit). `make verify-functional` se auto-pula de forma limpa,
  então um run verde na sua máquina reflete o que sua instalação de fato suporta.
- **Teste com hardware real** ao modificar código de controle de drone, e rode os markers
  relevantes de `make verify-functional` antes de submeter.
- `make doctor` imprime um relatório somente leitura do ambiente e dispositivos atuais —
  útil quando um teste é pulado e você quer saber por quê.

#### CI local (cross-distro)

Os checks rodam em fidelidade crescente:

- **Lint** — `make check` (ruff via pre-commit).
- **Suíte no host** (a mais rica; todas as deps instaladas, incl. AI/Qt/CUDA) — `make
  verify`, `make verify-functional`, `make verify-hardware` na sua máquina de dev.
- **Cross-distro em Docker** — `make ci-local` builda a imagem do SDK a partir do código
  *local* para cada distro ROS e roda `verify` + `verify-functional` em cada uma, espelhando
  [`.github/workflows/_build-verify.yml`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/.github/workflows/_build-verify.yml).
  Ele imprime um resumo de pass/fail e grava um relatório JUnit por distro em
  `ci-local-results/`. Somente amd64 (arm64 é coberto em um Jetson; Windows via WSL2 mais
  adiante). Builda uma imagem por vez e a remove depois, para limitar o uso de disco.

  ```bash
  make ci-local                                  # humble jazzy kilted (sdk stage)
  make ci-local DISTROS=jazzy                     # one distro
  make ci-local DISTROS="humble kilted" FULL=1    # include torch/AI (sdk-full; heavy)
  make ci-local REALSENSE=1                        # also build librealsense + realsense-verify
  ```

  Disco: builds de imagem completos são grandes. O data-root do Docker precisa ter vários GB
  livres (cada imagem `sdk` tem ~4-5 GB, `sdk-full` ~10 GB); o runner aborta um build abaixo
  de `MIN_FREE_GB` (padrão 8). Recupere espaço com `docker system prune` / removendo imagens
  antigas.

#### Voos SITL / integração (Tier 3)

A suíte em [`nectar/test/sitl/`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/nectar/test/sitl)
voa uma missão smoke real em um simulador **headless** para cada firmware + protocolo
(connect → takeoff → move → land), validando o núcleo do veículo e o link
firmware/protocolo de ponta a ponta. A fixture `sim_session` possui o ciclo de vida da
simulação (reaproveitando `make sim-start` / `sim-bridge` / `sim-stop`), então um único
comando substitui a orquestração manual em dois terminais.

```bash
make verify-sitl                          # full matrix (needs the sim stack: make sim-install)
make verify-sitl FIRMWARE=px4 PROTOCOL=dds  # one entry (FIRMWARE -> marker, PROTOCOL -> -k)
```

Matriz: `ardupilot` (mavros, mavlink), `px4` (mavros, mavlink, dds), `crazyflie` (sim do
Crazyswarm2). O Bebop é hardware-only (sem simulador). O tier é marcado como `sitl` e
**desselecionado por padrão**.

Rode onde a stack de simulação estiver instalada (`make sim-install`): sua máquina de dev ou
o Jetson, e como um gate de pré-release. **Não** está no CI — buildar os simuladores
(ArduPilot + PX4 + Gazebo, todos a partir do código-fonte) leva ~45-70 min e não há binário
apt para atalhar isso, então não vale a pena como job por PR ou agendado. O mesmo comando
`make verify-sitl` roda sem alterações em amd64 e arm64. (O Crazyflie se auto-pula a menos
que o backend `crazyflie_sim` do Crazyswarm2 seja buildado a partir do código-fonte.)

Para adicionar um firmware/protocolo: adicione um `SimSpec` a
[`nectar/test/sitl/sim_helpers.py`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/nectar/test/sitl/sim_helpers.py)
(seus `start_cmds`, tipo de drone, preset de config e envelope de voo); o `test_smoke_flight`
parametrizado e os markers pegam isso automaticamente. A suíte de navegação mais profunda do
ArduPilot fica em
[`examples/simulation/sitl_test.py`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/nectar/nectar/examples/simulation/sitl_test.py).

### Adicionando um componente

Ao adicionar novos componentes:

1. **Módulo Control**: estenda `BaseDrone` ou implemente o protocolo `Drone`; registre em `DroneFactory`. A lógica do ArduPilot agnóstica a transporte fica em `control/ardupilot/`; a navegação externa indoor (VSLAM, ponte de vision-pose) em `control/localization/`.
2. **Módulo Vision**:
   - Câmeras: adicione em `vision/camera/drivers/`, registre em `CameraFactory`
   - Algoritmos: adicione em `vision/algorithms/<category>/`
3. **Módulo AI**: estenda `BaseDetectionModel` (ou o equivalente de segmentação), registre em `Detector`/`Segmentor`
4. **Pontos de entrada ROS**: os nós vão no diretório `nodes/` correspondente e os arquivos `launch/` em `nectar/launch/`; instale os dois em `nectar/CMakeLists.txt`
5. **Export**: adicione os símbolos públicos ao `__init__.py` (deps pesadas via `_LAZY_ATTRS`)
6. **Documente**: atualize o README.md do módulo; para um novo módulo de nível superior, adicione um bullet em Features no README raiz apontando para a página correspondente no [site de documentação](https://black-bee-drones.github.io/nectar-sdk/)

### Contrato de Tempo de Importação

Dependências pesadas de terceiros (`torch`, `transformers`, `rfdetr`, `tensorflow`, `jax`, `matplotlib`, `mediapipe`, `pyrealsense2`, `depthai`, `supervision`, `ultralytics`, `pandas`, `geopy`) **não devem** ser importadas no momento de carregamento do módulo, no caminho de `from nectar.ai import Detector`, `from nectar.vision import ImageHandler`, ou `from nectar.control import MavrosConfig`.

Dois padrões são usados para reforçar isso, ambos padrão de mercado
([PEP 562](https://peps.python.org/pep-0562/), a mesma abordagem do scikit-learn / NumPy /
SciPy):

1. **Superfície lazy do pacote em `__init__.py`**: re-exports pesados passam por um dict `_LAZY_ATTRS` e `__getattr__`. Tipos leves (dataclasses, enums, exceptions) permanecem eager. Veja `nectar/ai/detection/__init__.py` e `nectar/vision/__init__.py` para o padrão canônico.
2. **Imports locais em funções**: quando um módulo precisa de `matplotlib` / `pandas` somente dentro de um helper de plotagem, o import vive dentro do corpo da função, não no topo do arquivo. Veja `nectar/vision/algorithms/distance/calibrator.py::ModelCalibrator.plot`.

Verifique o contrato disparando um interpretador novo e afirmando que os módulos proibidos
estão ausentes de `sys.modules` depois de um import público:

```bash
python -c "import sys, nectar.control; assert 'torch' not in sys.modules and 'mediapipe' not in sys.modules"
```

Se você adicionar uma nova dependência pesada ou re-export, roteie-a por `_LAZY_ATTRS` (ou um
import local à função) para que o caminho de import público permaneça leve.

## Processo de Revisão

Os mantenedores revisam o código e fornecem feedback; trate as alterações solicitadas e,
uma vez aprovado, o PR é mesclado.

## Dúvidas?

- [GitHub Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) para perguntas gerais
- [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) para bugs/funcionalidades
