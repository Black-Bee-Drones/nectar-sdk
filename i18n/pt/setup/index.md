# Instalação

Instale o SDK aqui e depois acrescente o que a missão precisa: [drivers de drone](drivers.md),
[simulação](simulation.md), [RealSense e indoor](realsense.md) ou
[Docker](docker.md). A matriz de plataformas testadas está em
[Compatibilidade](compatibility.md).

## Escolha sua instalação

Comece pela linha que corresponde à sua máquina:

| Ponto de partida | Faça isto |
|---|---|
| Máquina limpa, sem ROS 2 | Aba [**Do zero**](#from-scratch-no-ros-2) — um comando de bootstrap instala ROS 2 + o SDK |
| ROS 2 instalado, SDK ainda não clonado | clone em `~/ros2_ws/src`, depois aba [**Workspace existente**](#existing-ros-2-workspace) → `make setup` |
| SDK clonado, nada instalado | `make setup` (abre o menu de setup) |
| Deps instaladas, só falta o venv | rode de novo `make python-all` (ou seus módulos) — cria `$WORKSPACE/.venv` |
| Quer zero setup no host | [Docker](docker.md): `make docker-build && make docker-run` |

`make setup` (ou `./scripts/setup.sh` sem args) abre um menu interativo. Entradas:

- **Quick setup** — deps de sistema + escolha de módulos + build + verify
- **Python modules** — instala só os módulos que você escolher
- **Drone driver** — mavros / px4 / px4-dds / crazyflie / bebop
- **System packages** — pulado quando já instalado
- **ROS 2 environment**, **Build**, **Verify**, **RealSense**

!!! note "Nada instala até você escolher"
    Pacotes de sistema são idempotentes. **MAVROS** (`ros-*-mavros`) é opt-in — rode
    `make drone-mavros` quando usar o backend MAVROS. Datasets geoid do **GeographicLib**
    instalam com `make full-install` / bootstrap (idempotente) ou com `make drone-mavros`;
    não são puxados a cada execução do menu.

### Depois acrescente o que a missão precisa

| Objetivo | Comandos |
|---|---|
| ArduPilot / PX4 via MAVLink direto | `make setup` (escolha `control`) — `pymavlink` vem com o SDK core; opcional `make drone-mavros` para dados geoid |
| ArduPilot / PX4 via MAVROS | `make setup` (escolha `control`) e depois `make drone-mavros` |
| PX4 via uXRCE-DDS + detecção | `make setup` (escolha `control ai`) e depois `make drone-px4-dds` |
| Crazyflie / Bebop | `make drone-crazyflie` / `make drone-bebop` |
| Só o app GUI | `make python-interface` |
| Simulação (SITL + Gazebo) | [`make sim-install`](simulation.md) |

Detalhes: [Drivers de drone](drivers.md) (instalar + voar hardware), [Simulação](simulation.md)
e [RealSense e indoor](realsense.md).

<span id="from-scratch-no-ros-2"></span>
<span id="existing-ros-2-workspace"></span>

=== "Do zero (sem ROS 2)"

    Um script de bootstrap standalone instala tudo em uma máquina Ubuntu/Debian limpa:
    pacotes de sistema, ROS 2 (ros-base), dados geoid GeographicLib, Git LFS, o próprio SDK,
    dependências Python (`python all`) e build do workspace. MAVROS e outros drivers
    continuam opt-in — acrescente-os no menu de setup ou com `make drone-mavros` após o
    bootstrap.

    ```bash
    bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)
    ```

    O bootstrap pergunta o caminho do workspace (padrão `~/ros2_ws`) e o branch (main ou
    dev), clona o repositório e delega a `./scripts/setup.sh full-install`.

    Para CI/Docker (não interativo):

    ```bash
    NON_INTERACTIVE=true ROS2_WORKSPACE=~/ros2_ws bash scripts/bootstrap.sh
    ```

    ### Menu de setup

    Rodar o script de setup sem argumentos abre o mesmo menu interativo de `make setup`
    (configurar módulos, drivers, pacotes de sistema, env ROS, build, verify — nada roda
    até você escolher):

    ```bash
    ./scripts/setup.sh
    ```

=== "Workspace ROS 2 existente"

    Clone no workspace e abra o menu de setup:

    ```bash
    cd ~/ros2_ws/src
    git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
    cd nectar-sdk
    make setup
    ```

    O **Quick setup** do menu roda: `system` (idempotente) → `git-lfs` → **seleção de
    módulos** (`cmd_python` para os módulos escolhidos; PyTorch primeiro se escolher AI) →
    `rosdep-init` → `ros2-deps` → `build-pkg` → `verify`. GeographicLib não faz parte do
    Quick setup — instala com `make full-install` / bootstrap ou com `make drone-mavros`
    (idempotente). Sem interação (`NON_INTERACTIVE=true`, p.ex. CI) `make setup` pula o
    menu e roda Quick setup com `all`.

=== "Docker"

    Pule o setup de ROS/Python no host — faça build e entre no container de desenvolvimento:

    ```bash
    make docker-build
    make docker-run
    ```

    Para fluxos Isaac / VSLAM / RealSense, veja o [guia Docker](docker.md)
    (`make isaac-run`, mounts de dispositivo, notas Jetson).

## Ambiente Python

<span id="python-environment"></span>

As dependências Python instalam em um único ambiente virtual compartilhado, gerenciado pelo
[uv](https://github.com/astral-sh/uv), em `$WORKSPACE/.venv` (p.ex. `~/ros2_ws/.venv`). O
`uv` é instalado automaticamente se estiver ausente.

- **Criado automaticamente** no primeiro `make python*` / `make setup`, com
  `--system-site-packages` para que o ROS 2 (`rclpy`, bindings de mensagens, `colcon`)
  continue visível dentro dele.
- **A ativação é opt-in.** Os próprios comandos do SDK (`make build`, `make verify`,
  `make python*`, `make pytorch`) usam o venv internamente, então sempre funcionam. No seu
  shell interativo ele **não** é forçado — assim não atrapalha outros projetos e
  workspaces. `make ros2-env` instala o comando `nectar-activate` para quando quiser.
- **Reutilizado por todo o workspace.** Todo pacote sob `src/` — o SDK e o seu código de
  missão/competição — compartilha este venv, então você instala uma vez e faz
  `import nectar` de qualquer lugar. Não precisa de venv por projeto.

Entre nele quando precisar (p.ex. para `ros2 run nectar <node>` ou seus scripts); o prompt
mostra `(nectar)`:

```bash
nectar-activate            # enter the SDK env (command added by `make ros2-env`)
deactivate                 # leave it (shell built-in)
uv pip install <package>   # add a package (fast); plain `pip install` also works
```

Para ativar o env em todo shell novo, acrescente uma linha ao `~/.bashrc`:

```bash
source ~/ros2_ws/.venv/bin/activate
```

Sobrescreva o local com `NECTAR_VENV=/path` (um `VIRTUAL_ENV` já ativo é respeitado); veja
[Configuração](configuration.md#python-environment-location) para o caveat do venv.

## Instalar por módulo

Instale só os módulos de que precisa (dependências em `nectar/pyproject.toml`). Cada alvo
`make` é um wrapper fino sobre o script de setup, então as duas colunas fazem o mesmo:

| Alvo `make` | Script de setup | Instala |
|---|---|---|
| `make python` | `./scripts/setup.sh python` | Só o core (numpy, opencv, scipy) |
| `make python-control` | `./scripts/setup.sh python control` | + navegação GPS/PID, pymavlink (MAVLink direto) |
| `make python-vision` | `./scripts/setup.sh python vision` | + drivers de câmera, ArUco, cor, detecção de linha |
| `make python-ai` | `./scripts/setup.sh python ai` | + YOLO, DETR, RF-DETR (exige PyTorch) |
| `make python-interface` | `./scripts/setup.sh python interface` | + GUI Qt6 / PySide6 |
| `make python-sensors` | `./scripts/setup.sh python sensors` | + pyserial / pymavlink (driver TF-Luna, ponte MAVLink) |
| `make python-all` | `./scripts/setup.sh python all` | Todos os módulos |
| `make python-full` | `./scripts/setup.sh python full` | Todos + drivers de hardware de câmera |

## PyTorch (obrigatório para o módulo de IA)

Instalado pela integração nativa de PyTorch do uv (`--torch-backend`), que detecta o driver
CUDA e puxa torch mais as wheels `nvidia-*` CUDA do índice correto em
`download.pytorch.org`:

| Comando | Efeito |
|---|---|
| `make pytorch` | Auto-detecta GPU (CUDA 13 -> cu130; sem GPU -> cpu) |
| `./scripts/setup.sh pytorch cpu` | Força CPU |
| `./scripts/setup.sh pytorch cu128` | Força um backend (cpu/cu118/cu126/cu128/cu130/...) |

Um par conhecido `torch`/`torchvision` é pinado por padrão em
[`scripts/lib/config.sh`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/lib/config.sh)
para reprodutibilidade; sobrescreva com `TORCH_VERSION` / `TORCHVISION_VERSION` (defina os
dois juntos). Wheels CUDA grandes em links lentos podem travar — o timeout por request sobe
para 600s (`UV_HTTP_TIMEOUT`); em redes muito instáveis também
`export UV_CONCURRENT_DOWNLOADS=1`. Veja [PyTorch Get Started](https://pytorch.org/get-started/locally/)
e o [guia PyTorch do uv](https://docs.astral.sh/uv/guides/integration/pytorch/).

## Build e verificação

| Comando | Faz |
|---|---|
| `make build` | Build de todo o workspace |
| `make build-pkg` | Build só dos pacotes do SDK |
| `make verify` | Checa a instalação (presença/imports) |
| `make doctor` | Relatório de ambiente (ROS, módulos, dispositivos, CUDA) |
| `make clean` | Remove artefatos de build |
| `make verify-functional` | Testes funcionais de regressão (pytest; `MODULE="vision control"`) |
| `make test` | colcon test (suíte funcional + lint cmake/xml) |

A lista completa de comandos está na referência
[Comandos e Makefile](../development/commands.md).

## Setup de sistema (passos individuais)

| Comando | Passo |
|---|---|
| `./scripts/setup.sh system` | pacotes apt |
| `./scripts/setup.sh ros2` | pacotes base ROS 2 (ros-base, rviz2, cv_bridge, …) |
| `./scripts/setup.sh geographiclib` | datasets geoid GeographicLib (também por `full-install` e `make drone-mavros`) |
| `./scripts/setup.sh ros2-env` | Configura `~/.bashrc` |
| `./scripts/setup.sh rosdep-init` | Inicializa rosdep |
| `./scripts/setup.sh git-ssh` | Configura git e chaves SSH |

## Solução de problemas

### ROS 2 não encontrado

```bash
source /opt/ros/humble/setup.bash
```

### Pacote não encontrado após o build

```bash
source ~/ros2_ws/install/local_setup.bash
```

### Permissão negada na câmera

```bash
sudo usermod -a -G video $USER

# Logout and login

```

### Problemas de conexão MAVROS

```bash
sudo usermod -a -G dialout $USER

# Logout and login

```
