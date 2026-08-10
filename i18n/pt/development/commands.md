# Comandos e Makefile

O [`Makefile`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/Makefile) é um
wrapper fino sobre o [`scripts/setup.sh`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/setup.sh):
todo `make <target>` roda `./scripts/setup.sh <command>`. Liste tudo a qualquer momento com:

```bash
make help          # or: ./scripts/setup.sh help
```

## Instalação e sistema

| Comando | Faz |
|---|---|
| `make setup` | Menu de instalação interativo (nada é instalado até você escolher) |
| `make system` | Instala pacotes apt do sistema |
| `make ros2` | Instala ROS 2 + MAVROS |
| `make geographiclib` | Instala os datasets de geoide do GeographicLib |
| `make ros2-env` | Configura o `~/.bashrc` (adiciona `nectar-activate`) |
| `make rosdep-init` | Inicializa o rosdep |
| `make full-install` | Instalação completa a partir do zero (usado pelo bootstrap) |
| `make update` | Atualiza os pacotes do sistema (apt upgrade) |

## Módulos Python

| Comando | Instala |
|---|---|
| `make python` | Somente o core (numpy, opencv, scipy) |
| `make python-control` | + GPS, PID, navegação MAVROS |
| `make python-vision` | + drivers de câmera, ArUco, cor, linha |
| `make python-ai` | + YOLO, DETR, RF-DETR (precisa de PyTorch) |
| `make python-interface` | + GUI Qt6 / PySide6 |
| `make python-sensors` | + pyserial / pymavlink |
| `make python-all` | Todos os módulos |
| `make python-full` | Todos + drivers de hardware de câmera |
| `make python-dev` | Ferramental de teste/dev (pytest) |
| `make pytorch` | PyTorch (detecta CUDA/CPU automaticamente) |

Veja [Instalação](../setup/index.md) para mais detalhes.

## Drivers de drone

| Comando | Instala |
|---|---|
| `make drone-mavros` | MAVROS (ArduPilot) + GeographicLib |
| `make drone-px4` | PX4 sobre MAVROS |
| `make drone-px4-dds` | PX4 sobre uXRCE-DDS |
| `make drone-crazyflie` | Crazyswarm2 |
| `make drone-bebop` | Parrot Bebop 2 |
| `make drone-all` | Todos os anteriores |

Inicie um driver/bridge para hardware real com `make driver DRONE=<type> ...`; veja
[Drivers de drone](../setup/drivers.md).

## Build, verificação e qualidade

| Comando | Faz |
|---|---|
| `make build` | Builda o workspace inteiro |
| `make build-pkg` | Builda somente os pacotes do SDK |
| `make clean` | Remove os artefatos de build |
| `make verify` | Verifica a instalação (presença/imports) |
| `make verify-functional` | Suíte funcional pytest (`MODULE="vision control"` para um subconjunto) |
| `make verify-hardware` | Testes condicionados a dispositivo (câmeras, rangefinder) |
| `make verify-sitl` | Testes de voo SITL/integração (`FIRMWARE=`, `PROTOCOL=`) |
| `make doctor` | Relatório somente leitura do ambiente (ROS, módulos, dispositivos, CUDA) |
| `make test` | colcon test (suíte funcional + lint cmake/xml) |
| `make ci-local` | CI cross-distro em Docker (`DISTROS=`, `FULL=`) |
| `make check` | Todos os checks de pre-commit (lint/format, igual ao CI) |
| `make lint` / `make lint-fix` / `make format` | ruff check / fix / format do Python |

## Simulação

Escolha `FIRMWARE` (`ardupilot`/`px4`), `ENV` (`outdoor`/`indoor`), `PROTOCOL`
(`mavros`/`mavlink`/`dds`).

| Comando | Faz |
|---|---|
| `make sim-install FIRMWARE=..` | Instala SITL + Gazebo (também `all`) |
| `make sim-start FIRMWARE=.. ENV=..` | Terminal 1: o simulador |
| `make sim-bridge FIRMWARE=.. ENV=.. PROTOCOL=..` | Terminal 2: a stack ROS |
| `make sim-stop` | Para tudo |

Veja [Simulação](../setup/simulation.md).

## Drivers para hardware real

| Comando | Faz |
|---|---|
| `make driver DRONE=.. ENV=.. FCU_URL=..` | Inicia o driver/bridge ao qual a missão se conecta |
| `make driver-mavros` / `driver-px4` / `driver-px4-dds` / `driver-bebop` / `driver-crazyflie` | Atalhos por tipo |
| `make driver-stop` | Para todos os drivers/bridges |

Sobrescritas de conexão via variáveis de ambiente: `FCU_URL` / `DEV` / `BAUD` / `PORT` / `IP`.

## RealSense e Isaac VSLAM

| Comando | Faz |
|---|---|
| `make realsense` | Builda o librealsense + realsense-ros |
| `make realsense-verify` | Verifica a instalação do RealSense |
| `make isaac-run` | Inicia o container Isaac ROS Visual SLAM (Jetson) |
| `make isaac-stop` | Desmonta os containers do Isaac |
| `make vslam-viz` | Check VSLAM no RViz (`VSLAM_PROFILE=light` ou `full`) |

## Docker

| Comando | Faz |
|---|---|
| `make docker-build` | Imagem do SDK (sem AI) |
| `make docker-build-full` | Imagem completa (+ PyTorch/AI) |
| `make docker-build-t265` | Imagem com suporte a T265 |
| `make docker-run` | Roda com X11, câmeras, USB |
| `make docker-exec` | Terminal extra em um container em execução |
| `make docker-publish-jetson` | Builda + faz push da imagem Jetson (rode no Jetson) |

Veja [Docker](../setup/docker.md).

## Site de documentação

| Comando | Faz |
|---|---|
| `make docs-install` | Cria o `.venv-docs` e instala o toolchain de documentação |
| `make docs-sync` | Monta `build/docs/` (EN) e `build/docs-pt/` (PT) |
| `make docs` | Sincroniza, builda EN + PT, faz merge em `build/site/` (+ `build/site/pt/`) |
| `make docs-serve` | Preview bilíngue em `http://localhost:8000/nectar-sdk/` e `.../pt/` |
| `make docs-serve-en` | Live reload somente em inglês (os links da versão PT dão 404) |

Edite as páginas autorais em `website/`, os READMEs dos módulos e `docs/*.md`; tudo sob
`build/` é gerado. As convenções estão em [Contribuindo](../project/contributing.md).
