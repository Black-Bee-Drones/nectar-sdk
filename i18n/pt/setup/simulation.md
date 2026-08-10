# Simulação (Gazebo + ArduPilot / PX4 SITL)

Voe as mesmas missões que no hardware, no Gazebo com ArduPilot ou PX4 SITL — sem veículo.
Instale uma vez por firmware; depois inicie o simulador e a ponte ROS em dois terminais.

## Instalar

Um comando de instalação por firmware. ArduPilot puxa ArduCopter SITL, Gazebo, a ponte
`ros_gz` e o plugin ArduPilot Gazebo (seleciona a versão do Gazebo por distro ROS; tabela
por distro no [guia Docker](docker.md)). PX4 puxa PX4-Autopilot e Gazebo
e cria symlinks dos assets compartilhados do Nectar na árvore do PX4.

=== "ArduPilot"

    ```bash
    make sim-install FIRMWARE=ardupilot   # ArduCopter SITL + Gazebo + plugin
    ```

=== "PX4"

    ```bash
    make sim-install FIRMWARE=px4          # PX4 SITL + Gazebo + Nectar assets
    ```

=== "Both"

    ```bash
    make sim-install FIRMWARE=all          # ArduPilot + PX4
    ```

=== "PX4 native (uXRCE-DDS)"

    Para **PX4 uXRCE-DDS** (`PROTOCOL=dds`), instale também o agent nativo e `px4_msgs` uma
    vez:

    ```bash
    make sim-install FIRMWARE=px4 ARGS=--native
    ```

### Docker com Gazebo

```bash
INSTALL_GAZEBO=true make docker-build
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

Veja o [guia Docker](docker.md) para mais opções.

## Rodar a simulação

Dois terminais, o mesmo padrão nos dois firmwares: o simulador (terminal 1) mais a stack
ROS (terminal 2). Escolha `FIRMWARE` / `ENV` / `PROTOCOL` (padrões: `ardupilot` /
`outdoor` / `mavros`).

!!! warning "Combine o ENV entre os terminais"
    Use o mesmo `FIRMWARE` e `ENV` no terminal 1 (`sim-start`) e no terminal 2
    (`sim-bridge`). Indoor acrescenta o pipeline de visão; outdoor usa GPS.

| Setup | Terminal 1 (simulador) | Terminal 2 (stack ROS) |
|---|---|---|
| ArduPilot outdoor / MAVROS (padrão) | `make sim-start` | `make sim-bridge` |
| ArduPilot outdoor / MAVLink direto | `make sim-start FIRMWARE=ardupilot ENV=outdoor` | `make sim-bridge FIRMWARE=ardupilot ENV=outdoor PROTOCOL=mavlink` |
| ArduPilot indoor (visão) | `make sim-start FIRMWARE=ardupilot ENV=indoor` | `make sim-bridge FIRMWARE=ardupilot ENV=indoor` |
| PX4 outdoor / MAVROS | `make sim-start FIRMWARE=px4 ENV=outdoor` | `make sim-bridge FIRMWARE=px4 ENV=outdoor` |
| PX4 outdoor / MAVLink direto | `make sim-start FIRMWARE=px4 ENV=outdoor` | `make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=mavlink` |
| PX4 outdoor / uXRCE-DDS | `make sim-start FIRMWARE=px4 ENV=outdoor` | `make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=dds` |
| PX4 indoor (VIO a bordo) | `make sim-start FIRMWARE=px4 ENV=indoor` | `make sim-bridge FIRMWARE=px4 ENV=indoor` |
| PX4 indoor / MAVLink direto | `make sim-start FIRMWARE=px4 ENV=indoor` | `make sim-bridge FIRMWARE=px4 ENV=indoor PROTOCOL=mavlink` |

**PX4 MAVLink direto** (`PROTOCOL=mavlink`): o terminal 2 pula o MAVROS e só inicia pontes
de câmera; a missão se conecta ao UDP offboard `14540` do PX4 (`backend` `px4_mavlink`).

**PX4 uXRCE-DDS** (`PROTOCOL=dds`): o terminal 2 roda `MicroXRCEAgent` em UDP `:8888`; use
o backend `px4_dds` na missão. Exige a instalação única `ARGS=--native` acima.

Pare tudo (os dois firmwares) com `make sim-stop`.

Depois rode uma missão contra a simulação, por exemplo:

```bash
nectar-activate
python3 nectar/nectar/examples/control/basic.py --drone mavros --mode position --side 2.0
```

Veja o [módulo Simulation](../modules/simulation.md) para a matriz completa, o
pipeline de visão e a suíte de testes automatizados.
