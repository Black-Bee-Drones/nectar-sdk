# Drivers de drone

Cada drone precisa do próprio driver ou ponte, iniciado em um terminal separado antes da
missão se conectar (os exemplos usam `start_driver=False` por padrão). Este é o
correspondente no mundo real da ponte de [simulação](simulation.md).

Escolha o drone abaixo para instalação, comando do driver e um voo exemplo. Os alvos estão
em `scripts/lib/drones.sh`.

## Escolha seu drone

=== "ArduPilot · MAVROS"

    Instala MAVROS e os datasets geoid GeographicLib.

    ```bash
    make setup                 # pick: control
    make drone-mavros
    ```

    Inicie o driver e depois voe um quadrado de 2 m:

    ```bash
    make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600   # terminal 1
    nectar-activate                                                 # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone mavros --mode position --side 2.0
    ```

=== "ArduPilot · MAVLink"

    Sem instalação separada: `pymavlink` vem com o SDK core, então a missão abre o link.
    `make drone-mavros` adiciona os dados geoid usados na altitude GPS.

    Outdoor não precisa de ponte; voe direto:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone mavlink --mode position --side 2.0 --env outdoor \
        --connection serial:///dev/ttyUSB0:921600
    ```

    Indoor (sem GPS): inicie o alimentador de visão primeiro e depois a missão em outro
    endpoint MAVLink (exemplo Black Bee com MAVProxy: feeder `14552`, missão `14551`):

    ```bash
    make driver DRONE=mavlink ENV=indoor          # terminal 1: vision feeder
    python3 nectar/nectar/examples/control/basic.py \
        --drone mavlink --mode position --side 2.0 --env indoor \
        --connection udp:127.0.0.1:14551           # terminal 2: mission
    ```

=== "PX4 · MAVROS"

    Reutiliza MAVROS, lançado com `px4.launch`.

    ```bash
    make setup                 # pick: control
    make drone-px4
    ```

    ```bash
    make driver DRONE=px4 FCU_URL=udp://:14540@127.0.0.1:14580   # terminal 1
    nectar-activate                                              # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone px4 --mode position --side 2.0
    ```

=== "PX4 · MAVLink"

    Sem instalação separada: `pymavlink` vem com o SDK core. Outdoor a missão abre o link;
    indoor inicia a ponte de vision-pose (`make driver DRONE=px4_mavlink ENV=indoor`).

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py --drone px4_mavlink --mode position --side 2.0
    ```

=== "PX4 · uXRCE-DDS"

    Instala `px4_msgs` e o Micro XRCE-DDS Agent (hardware real; sem SITL).

    ```bash
    make setup                 # pick: control
    make drone-px4-dds
    ```

    ```bash
    make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # terminal 1 (PORT=8888 for UDP)
    nectar-activate                                    # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone px4_dds
    ```

    Para acrescentar um detector de objetos à mesma missão, instale também `ai`
    (`make setup` → `control ai`) e use `from nectar.ai.detection import Detector`.

=== "Crazyflie"

    Instala Crazyswarm2 (apt quando disponível, senão source) mais regras udev do rádio.
    Defina o URI em `crazyflies.yaml`.

    ```bash
    make drone-crazyflie
    ```

    ```bash
    make driver-crazyflie      # terminal 1: Crazyflie server
    nectar-activate            # terminal 2
    python3 nectar/nectar/examples/control/basic.py \
        --drone crazyflie --mode position --height 0.5 --side 0.6
    ```

=== "Bebop"

    Instala `ros2_parrot_arsdk` e `ros2_bebop_driver` (build source).

    ```bash
    make drone-bebop
    ```

    ```bash
    make driver-bebop IP=192.168.42.1   # terminal 1
    nectar-activate                     # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone bebop
    ```

!!! note "Gerenciar drivers"
    - Instale todos de uma vez com `make drone-all`.
    - Pare todos os drivers e pontes em execução com `make driver-stop`.
    - Sobrescreva conexões com as variáveis `FCU_URL`, `DEV`, `BAUD`, `PORT` e `IP`.
    - Existem atalhos por tipo (`make driver-mavros`, `driver-px4`, ...).

Para a matriz completa de backends e configuração, veja o
[módulo Control](../modules/control/index.md).
