# Matriz de compatibilidade

O que o Nectar SDK suporta, e até onde cada parte foi verificada, nas distribuições ROS 2
e plataformas. O SDK é modular: uma instalação core puxa a base ROS, os pacotes do SDK e
as deps Python core; todo o resto (backends de control, AI, RealSense, OAK-D, simulação)
é um grupo opt-in. Cada tabela de módulo indica como instalá-lo.

Este é um documento vivo. O status reflete a verificação mais completa feita até agora;
as células avançam conforme mais setups são exercitados.

## Legenda

O símbolo de cada célula reflete o nível mais profundo de verificação alcançado (veja
[Como é verificado](#how-its-verified)).

| Símbolo | Significado |
|:---:|---|
| `●` | **Functional** — um check `verify-functional`, uma execução SITL ou um voo em hardware exercitou (uma operação real, não só um import). |
| `◐` | **Build** — a imagem faz build e `make verify` passa (pacote presente, imports, nós); o check funcional ainda não foi registrado naquela distribuição. |
| `○` | **Ainda não testado**. |
| `—` | **Não aplicável** (o recurso ou sua dependência não está disponível ali). |

A distribuição ROS 2 implica a base Ubuntu: **Humble** = 22.04, **Jazzy** / **Kilted** =
24.04. A coluna **Jetson** é JetPack 6.x (L4T, arm64, CUDA), build a partir de
[`docker/Dockerfile.jetson`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/docker/Dockerfile.jetson)
sobre base Humble.

## Plataformas

SDK base (`nectar`, `nectar_interfaces`, Python core) — builds e `make verify`:

| Plataforma | Humble | Jazzy | Kilted |
|---|:---:|:---:|:---:|
| Ubuntu amd64 (CI) | ● | ● | ● |
| Ubuntu arm64 (CI) | ◐ | ◐ | ◐ |
| Jetson JetPack 6.x (arm64) | ● | — | — |
| Windows (WSL2 / Docker Desktop) | ● | ● | ● |

## Runtime core

Sempre instalado. Executor ROS 2, mensagens customizadas, interoperabilidade cv_bridge.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Executor rclpy + round-trip `nectar_interfaces` | ● | ● | ● | ● |
| cv_bridge ↔ numpy (ABI `<2.0`) | ● | ● | ● | ● |

## Vision

Instalar: `make python-vision` (algoritmos) / extras de câmera conforme necessário.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| ArUco / cor / linha / distância (algoritmos) | ● | ● | ● | ● |
| Câmera por tópico ROS (`CameraFactory`) | ● | ● | ● | ● |
| Câmera USB / OpenCV | ● | ● | ● | ● |
| RealSense D4xx (librealsense source)[^realsense] | ● | ● | ◐ | ● |
| OAK-D (`depthai`)[^oakd] | ● | ● | ◐ | ● |
| MediaPipe mão / face[^mediapipe] | ● | ● | ● | ◐ |

## Control

Instalar: `make python-control`; backends são opt-in (`make drone-<x>`).

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Núcleo do veículo (PID, navigator, transforms de frame) | ● | ● | ● | ● |
| Transporte MAVLink direto (`pymavlink`)[^mavlink] | ● | ● | ● | ● |
| Backend MAVROS (ArduPilot / PX4) | ◐ | ● | ● | ◐ |
| PX4 nativo uXRCE-DDS[^px4dds] | ● | ● | ● | ◐ |
| Crazyflie / Crazyswarm2[^crazyflie] | ● | ● | ● | ○ |
| Driver Bebop[^bebop] | ● | ◐ | ◐ | — |

## Localização (indoor / sem GPS)

Instalar: `make python-control`; o container Isaac é só Jetson.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Ponte vision-pose — backend MAVROS | ● | ● | ● | ● |
| Ponte vision-pose — backend MAVLink | ● | ● | ● | ● |
| Isaac ROS Visual SLAM (producer)[^isaac] | — | — | — | ● |

## Sensors

Instalar: `make python-sensors`.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Filtro de máscara de obstáculo | ● | ● | ● | ● |
| Rangefinder → MAVLink `DISTANCE_SENSOR` | ● | ● | ● | ● |
| Driver UART TF-Luna[^tfluna] | ● | ● | ● | ● |

## AI / detecção

Instalar: `make python-ai && make pytorch`.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| CLI `nectar-ai` | ● | ● | ● | ● |
| Inferência de detecção (YOLO / DETR / RF-DETR)[^detect] | ● | ● | ◐ | ● |
| Inferência de classificação (YOLO-cls / ViT) | ● | ● | ◐ | ● |
| PyTorch CUDA (tensor GPU)[^torchcuda] | ● | ● | ● | ● |
| Treinamento / segmentação / classificação | ● | ● | ◐ | ◐ |

## Interface

Instalar: `make python-interface`.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| GUI Qt6 / PySide6 (construct offscreen) | ● | ● | ● | ● |
| GUI completa em display[^gui] | ● | ● | ● | ● |

## Simulação

Instalar: `make sim-install`. Não faz parte de nenhuma imagem publicada.

| Recurso | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Gazebo + ponte `ros_gz`[^gazebo] | ● | ● | ● | ○ |
| ArduPilot SITL — MAVROS[^sitl] | ● | ● | ● | — |
| ArduPilot SITL — MAVLink[^sitl] | ● | ● | ● | — |
| PX4 SITL — MAVROS[^sitl] | ◐ | ● | ● | — |
| PX4 SITL — MAVLink[^sitl] | ◐ | ● | ● | — |
| PX4 SITL — uXRCE-DDS[^sitl] | ● | ● | ● | — |

## Versões pinadas

<span id="pinned-versions"></span>

Versões por distro em
[`scripts/lib/config.sh`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/lib/config.sh).

| | Humble | Jazzy | Kilted | Jetson |
|---|---|---|---|---|
| librealsense / realsense-ros | v2.55.1 / 4.55.1 | v2.56.5 / 4.56.4 | v2.57.6 / 4.57.2 | v2.55.1 / 4.55.1 (CUDA, RSUSB) |
| Micro-XRCE-DDS-Agent | v2.4.2 | v2.4.3 | v3.0.1 | (igual ao Humble) |
| Gazebo (`ros_gz`) | Harmonic (source) | Harmonic (binary) | Ionic (binary) | — |
| PyTorch | uv `--torch-backend` (CPU/CUDA) | igual | igual | wheels JetPack (CUDA) |

## Como é verificado

<span id="how-its-verified"></span>

Três comandos sustentam esta matriz; o símbolo de uma célula reflete o nível mais profundo
alcançado. O CI roda os níveis 1-2 em distros/arches e as células acima são atualizadas à
mão a partir desses resultados.

| Nível | Comando | O que prova |
|------|---------|----------------|
| 1 — Build | `make verify` | A imagem faz build, os pacotes estão presentes, os módulos importam e os executáveis dos nós estão instalados. (`make doctor` dá um relatório somente leitura de ambiente/dispositivo/CUDA.) |
| 2 — Functional | `make verify-functional` | A suíte **pytest** em [`nectar/test/`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/nectar/test) (também por `colcon test`). Cada teste faz uma *operação real* — detectar um ArUco sintético, um passo de PID, handshake MAVLink em loopback, relé de pose VSLAM, abrir a janela Qt offscreen, inferência com nano-modelo. Os testes se pulam quando dispositivo/GPU/sim/dependência falta. Subconjunto com `MODULE="vision control"`; testes de hardware/GPU entram com `make verify-hardware`; reproduza por distro com `make ci-local`. |
| 3 — SITL / integração | `make verify-sitl` | A suíte em [`nectar/test/sitl/`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/nectar/test/sitl): um voo headless real (connect, takeoff, move, land) por firmware/protocolo. |

## Ainda não coberto

- **ROS 2 Lyrical (Ubuntu 26.04)**: ainda não suportado. No momento da escrita o deb
  `mavros` não está publicado para Lyrical e a stack scientific-Python não tem wheels para
  Python 3.14; a camada ROS/C++ e o Gazebo compilam. Revisar quando os dois chegarem.
