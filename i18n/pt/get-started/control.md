# Voar um drone

Decole, voe um quadrado e pouse com o mesmo código em qualquer plataforma suportada. Você
escolhe um **backend** (firmware mais um transporte), inicia o **driver** (ou um simulador),
define uma **fonte de pose** e roda uma missão. Só a chave da factory e o config mudam entre
plataformas; as chamadas de voo permanecem idênticas.

Escolha o backend na aba abaixo; a seleção vale para instalação, driver e código da missão.
Novo no workspace? Faça a [Instalação](../setup/index.md) primeiro.

## 1. Instale o backend

Instale `control` e depois o driver que o veículo usa:

```bash
make setup           # pick: control
```

=== "ArduPilot · MAVROS"

    ```bash
    make drone-mavros
    ```

=== "ArduPilot · MAVLink"

    Sem instalação extra: `pymavlink` já vem com o SDK core. `make drone-mavros` adiciona os
    dados geoid usados na altitude GPS.

=== "PX4 · MAVROS"

    ```bash
    make drone-px4
    ```

=== "PX4 · MAVLink"

    Sem instalação extra: `pymavlink` já vem com o SDK core. `make drone-mavros` adiciona os
    dados geoid usados na altitude GPS.

=== "PX4 · uXRCE-DDS"

    ```bash
    make drone-px4-dds
    ```

=== "Crazyflie"

    ```bash
    make drone-crazyflie
    ```

=== "Bebop"

    ```bash
    make drone-bebop
    ```

## 2. Defina a fonte de pose

Para ArduPilot e PX4 o **ambiente** seleciona a fonte de pose no config:

| Ambiente | Fonte de pose | Argumento no config |
|----------|---------------|---------------------|
| Outdoor | GPS | `pose_source=PoseSource.GPS` |
| Indoor (sem GPS) | Visão (VSLAM) | `pose_source=PoseSource.VISION` |

!!! note "Voo indoor"
    Indoor exige um feed de vision-pose no EKF do FCU; veja
    [Localização](../modules/control/localization/) (arquitetura, Run,
    origem EKF, procedimento indoor). Bebop e Crazyflie voam indoor sem GPS e ignoram
    essa configuração.

## 3. Inicie o driver

Inicie o driver ou a ponte a que a missão se conecta **antes** de rodá-la (os exemplos usam
`start_driver=False` por padrão). Overrides de conexão passam por variáveis de ambiente
(`FCU_URL`, `DEV`, `BAUD`, `IP`).

=== "ArduPilot · MAVROS"

    ```bash
    make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600
    ```

=== "ArduPilot · MAVLink"

    Outdoor não precisa de ponte; a missão abre o link. Indoor inicia a ponte de
    vision-pose:

    ```bash
    make driver DRONE=mavlink ENV=indoor
    ```

=== "PX4 · MAVROS"

    ```bash
    make driver DRONE=px4 FCU_URL=udp://:14540@127.0.0.1:14580
    ```

=== "PX4 · MAVLink"

    Outdoor não precisa de ponte; a missão abre o link. Indoor inicia a ponte de
    vision-pose:

    ```bash
    make driver DRONE=px4_mavlink ENV=indoor
    ```

=== "PX4 · uXRCE-DDS"

    ```bash
    make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # PORT=8888 for UDP
    ```

=== "Crazyflie"

    ```bash
    make driver-crazyflie
    ```

=== "Bebop"

    ```bash
    make driver-bebop IP=192.168.42.1
    ```

!!! tip "Sem hardware ainda? Voe em simulação"
    ```bash
    make sim-install FIRMWARE=ardupilot   # one-time (use FIRMWARE=px4 for PX4)
    make sim-start                        # terminal 1
    make sim-bridge                       # terminal 2
    ```
    Para MAVLink direto ou uXRCE-DDS, acrescente `PROTOCOL=mavlink` / `PROTOCOL=dds` em
    `sim-bridge`. Matriz completa: [Simulação](../setup/simulation.md).

## 4. Escreva a missão

Monte o drone com a chave e o config do backend. As chamadas de voo depois disso são as
mesmas para todos os backends.

=== "ArduPilot · MAVROS"

    ```python
    import nectar
    from nectar.control import DroneFactory, MavrosConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("mavros", MavrosConfig(pose_source=PoseSource.GPS))
    ```

=== "ArduPilot · MAVLink"

    ```python
    import nectar
    from nectar.control import DroneFactory, MavlinkConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("mavlink", MavlinkConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · MAVROS"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4MavrosConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4", Px4MavrosConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · MAVLink"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4MavlinkConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4_mavlink", Px4MavlinkConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · uXRCE-DDS"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4DdsConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4_dds", Px4DdsConfig(pose_source=PoseSource.GPS))
    ```

=== "Crazyflie"

    ```python
    import nectar
    from nectar.control import DroneFactory, CrazyflieConfig

    nectar.init()
    drone = DroneFactory.create("crazyflie", CrazyflieConfig())
    ```

=== "Bebop"

    ```python
    import nectar
    from nectar.control import DroneFactory, BebopConfig

    nectar.init()
    drone = DroneFactory.create("bebop", BebopConfig())
    ```

Voe um quadrado de 2 m e depois pouse:

```python
drone.takeoff(altitude=2.0)
drone.move_to(x=2.0, y=0.0, z=0.0)
drone.move_to(x=2.0, y=2.0, z=0.0)
drone.move_to(x=0.0, y=2.0, z=0.0)
drone.move_to(x=0.0, y=0.0, z=0.0)
drone.land()
nectar.shutdown()
```

Os exemplos do repositório voam o mesmo box em qualquer backend, com o navegador PID quando
o backend permite. Cada aba é o comando exato da plataforma (GPS outdoor; para indoor use
`--mode indoor` em `navigation.py` ou `--env indoor` em `basic.py` para a fonte de pose de
visão):

=== "ArduPilot · MAVROS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone mavros --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

=== "ArduPilot · MAVLink"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone mavlink --connection tcp:127.0.0.1:5762 \
        --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

    No hardware, passe o link serial, por exemplo `--connection /dev/ttyUSB0`.

=== "PX4 · MAVROS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone px4 --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

=== "PX4 · MAVLink"

    `navigation.py` não cobre este backend; o box em posição de `basic.py` cobre:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone px4_mavlink --mode position \
        --height 2.0 --side 2.0 --precision 0.15 --env outdoor
    ```

=== "PX4 · uXRCE-DDS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone px4_dds --mode position \
        --height 2.0 --side 2.0 --precision 0.15 --env outdoor
    ```

=== "Crazyflie"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone crazyflie --mode position \
        --height 0.5 --side 0.6 --precision 0.15
    ```

=== "Bebop"

    Bebop não tem controle de posição a bordo, então voa o box em velocidade:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py --drone bebop --mode velocity
    ```

!!! success "Resultado esperado"
    O drone arma, sobe até a altitude alvo, voa um box de 2 m (0,6 m no Crazyflie) com
    precisão de chegada de 0,15 m, depois pousa e desarma.

<figure class="nectar-shot">
  <div class="nectar-shot__media" data-src="../assets/media/basic-square.mp4">
    <video class="nectar-autoplay" muted loop playsinline preload="metadata">
      <source src="../assets/media/basic-square.mp4" type="video/mp4">
    </video>
  </div>
  <figcaption>Nosso drone voando o exemplo do quadrado em hardware real. Clique para ampliar.</figcaption>
</figure>

## Ver também

- [Referência de Control](../modules/control/index.md): a factory, o protocolo
  `Drone`, capacidades e a matriz completa de backends.
- [Vehicle core](../modules/control/vehicle/) · [Transports](../modules/control/mavlink/) ·
  [PID](../modules/control/pid/) · [Obstacles](../modules/control/obstacles/) ·
  [Localization](../modules/control/localization/index.md).
- [Exemplos de Control](../modules/examples/control.md): suíte de navegação,
  REPL interativo, teste de servo.
