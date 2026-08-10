# Exemplos do Módulo Control

Exemplos de voo para cada drone e transporte suportados, de uma decolagem básica a um REPL
de navegação interativa. Rode qualquer script com `python3 <script>.py [flags]` a partir
deste diretório (esses scripts não são instalados como executáveis ROS 2). Eles usam
`start_driver=False` por padrão, então inicie primeiro o driver, a bridge ou o simulador
correspondente.

| Script | O que faz | Flags principais |
|--------|--------------|-----------|
| `basic.py` | Decolagem, padrões de velocity/hover/position, pouso | `--drone {mavros,mavlink,px4,px4_mavlink,px4_dds,bebop,crazyflie}` · `--env {outdoor,indoor}` · `--mode {velocity,hover,position}` · `--connection` (mavlink/px4_mavlink) · `--height --side --velocity --precision --hover-time --cf-name --backend` |
| `sensors.py` | Monitora dados de GPS/vision/local | `--source gps\|vision` |
| `pid_simulation.py` | Simulação de controlador PID | `--kp --ki --plot` |
| `navigation.py` | Suíte de teste de navegação ArduPilot/PX4 | `--drone {mavros,mavlink,px4}` · `--mode {indoor,outdoor}` · `--connection` · `--strategy --test --distance` (veja abaixo) |
| `interactive_navigation.py` | REPL interativo — digite waypoints em tempo real | `--drone {mavros,mavlink,px4,px4_mavlink,px4_dds}` · `--mode {indoor,outdoor}` · `--connection --strategy --altitude --no-takeoff` |
| `servo_test.py` | REPL interativo — testador de servo/PWM pré-voo via `MAV_CMD_DO_SET_SERVO` | `--channel --hold --release` |
| `obstacles.py` | Navegação com desvio de obstáculos por câmera de profundidade (RealSense) | rode diretamente: `python3 obstacles.py` |

> Fonte de pose vs. padrão de voo: em `basic.py`, `--env {outdoor,indoor}` seleciona a **fonte de pose** (outdoor = GPS, indoor = vision — combine com o `ENV=` do simulador) e `--mode` seleciona o **padrão de voo** (`velocity`/`hover`/`position`). Em `navigation.py` / `interactive_navigation.py`, `--mode {indoor,outdoor}` seleciona a fonte de pose. `--connection` sobrescreve a string de conexão para os drones com pymavlink direto `--drone mavlink` (ArduPilot, por exemplo `tcp:127.0.0.1:5762`) e `--drone px4_mavlink` (PX4, por exemplo `udp:0.0.0.0:14540`); `--drone px4` (MAVROS) usa um `fcu_url` como `udp://:14540@127.0.0.1:14580`.

## Voo Básico

`basic.py` arma, decola até `--height`, voa um padrão `--mode` e pousa. Invocações comuns:

| Caso | Comando |
|------|---------|
| ArduPilot / MAVROS, quadrado de velocity (outdoor GPS, padrão) | `python3 basic.py --drone mavros --height 2.0` |
| ArduPilot / MAVROS, quadrado de position indoor (pose por vision) | `python3 basic.py --drone mavros --env indoor --mode position --height 2.0` |
| Crazyflie, hover em simulação | `python3 basic.py --drone crazyflie --mode hover --height 0.5 --backend sim --hover-time 10` |
| Crazyflie, quadrado de position (lados de 0,6 m) | `python3 basic.py --drone crazyflie --mode position --height 0.5 --side 0.6` |
| Crazyflie, quadrado de velocity | `python3 basic.py --drone crazyflie --mode velocity --height 0.4 --velocity 0.2 --side 0.5` |
| Bebop, quadrado de velocity | `python3 basic.py --drone bebop --mode velocity` |
| PX4 / MAVROS | `python3 basic.py --drone px4 --height 2.0` |
| PX4 / MAVLink direto | `python3 basic.py --drone px4_mavlink --connection udp:0.0.0.0:14540 --height 2.0` |
| PX4 / uXRCE-DDS nativo | `python3 basic.py --drone px4_dds --height 2.0` |

Resultado esperado: o drone arma, sobe até `--height`, voa o padrão selecionado (um quadrado para `velocity`/`position`, uma espera cronometrada para `hover`) e então pousa e desarma.

Para PX4 em simulação, inicie primeiro o simulador correspondente: `make sim-start FIRMWARE=px4 ENV=outdoor` mais `make sim-bridge FIRMWARE=px4 ENV=outdoor` (adicione `PROTOCOL=mavlink` para `px4_mavlink`, `PROTOCOL=dds` para `px4_dds`, que roda o MicroXRCEAgent).

### Modos

| Modo | Descrição |
|------|-------------|
| `velocity` (padrão) | Decolagem, voa um quadrado com comandos de velocity, pousa |
| `hover` | Decolagem, mantém a posição por `--hover-time` segundos, pousa |
| `position` | Decolagem, voa um quadrado com comandos `move_to`, pousa |

## Monitoramento de Sensores

```bash
python3 sensors.py --source gps
python3 sensors.py --source vision
```

## Simulação de PID

```bash
python3 pid_simulation.py
python3 pid_simulation.py --setpoint 30 --kp 0.8 --ki 0.2
python3 pid_simulation.py --plot
```

## Navegação

ArduPilot ou PX4 — `--drone mavros|mavlink|px4` (padrão `mavros`). `--mode indoor` usa a fonte de pose por vision, `--mode outdoor` (padrão) usa GPS.

| Caso | Comando |
|------|---------|
| Voo outdoor completo (estratégia PID padrão) | `python3 navigation.py --mode outdoor` |
| Indoor (pose por vision) sobre MAVROS | `python3 navigation.py --mode indoor --test body` |
| MAVLink direto contra a porta secundária do SITL (5762) | `python3 navigation.py --drone mavlink --connection tcp:127.0.0.1:5762 --test body` |
| Posição local do EKF em vez de GPS bruto | `python3 navigation.py --strategy pid-ekf` |
| Setpoint local (o FCU trata o controle de posição) | `python3 navigation.py --strategy position --test body` |
| Setpoint GPS global (waypoints de longo alcance) | `python3 navigation.py --mode outdoor --test gps --strategy position-global` |
| Teste com o drone na mão (sem decolagem) | `python3 navigation.py --no-takeoff --test body` |
| Distância personalizada, testes selecionados, log em CSV, repete 3x | `python3 navigation.py --test body takeoff-ref --distance 3.0 --csv runs.csv --loop 3` |

### Testes (`--test`, um ou mais; padrão `all`)

`body`, `takeoff-ref`, `altitude`, `velocity`, `gps`, `figure8`, `rectangle`, `cube-xyz`, `cube`, `gps-rectangle`. Os testes de GPS (`gps`, `gps-rectangle`) exigem `--mode outdoor`.

### Outros argumentos

| Arg | Padrão | Finalidade |
|-----|---------|---------|
| `--altitude` | `2.0` | Altitude de decolagem (m), ignorado com `--no-takeoff` |
| `--no-takeoff` | off | Define GUIDED + posição de takeoff sem armar (teste com o drone na mão) |
| `--distance` | `2.0` | Distância de navegação por waypoint (m) |
| `--precision` | `0.2` | Raio de precisão de chegada (m) |
| `--timeout` | `30.0` | Timeout por waypoint (s) |
| `--csv FILE` | nenhum | Anexa os resultados de cada trecho a um CSV (criado se não existir) |
| `--loop [N]` | nenhum | Repete os testes selecionados N vezes; `--loop` sem valor roda até Ctrl+C |

## Navegação Interativa

| Caso | Comando |
|------|---------|
| Outdoor, PID padrão | `python3 interactive_navigation.py --mode outdoor` |
| Transporte MAVLink direto | `python3 interactive_navigation.py --drone mavlink --mode outdoor` |
| Outdoor, EKF, altitude de 3 m | `python3 interactive_navigation.py --mode outdoor --strategy pid-ekf --altitude 3.0` |
| Com o drone na mão (sem armar/decolar) | `python3 interactive_navigation.py --no-takeoff` |

Uma vez rodando, digite waypoints no prompt `nav>`:

```
nav> 2 0           # 2m forward
nav> 0 3 0         # 3m left, hold altitude
nav> -2 -3 0       # back
nav> set ref takeoff
nav> 5 0 0         # 5m forward from takeoff origin
nav> 0 0 0         # return to takeoff
nav> set method pid-ekf
nav> 3 2            # now uses PID_EKF
nav> gps -22.413 -45.449 15
nav> status         # show drone state + settings
nav> land
```

### Estratégias de Navegação

| Estratégia | Descrição |
|----------|-------------|
| `pid` (padrão) | Controle de velocidade PID usando sensores brutos (vision/GPS) |
| `pid-ekf` | Controle de velocidade PID usando a posição local do EKF |
| `position` | Setpoint de posição local via `setpoint_raw/local` |
| `position-global` | Setpoint GPS global (somente outdoor, longo alcance) |

## Desvio de Obstáculos

```bash
python3 obstacles.py
```

Conecta um `DepthObstacleDetector` (RealSense D435i) com uma `SequenceStrategy`
(passagem lateral e retorno) e roda um `move_to` com desvio de obstáculos. Exige uma câmera
de profundidade conectada; veja [Obstacles](../control/obstacles.md) para os detectores e
estratégias.

## Teste de Servo / PWM

Aciona `MavrosDrone.do_servo` (`MAV_CMD_DO_SET_SERVO`, 183) a partir de um REPL para que você
possa verificar o canal AUX OUT correto e os extremos de PWM (por exemplo, hold/release de um
hook) na bancada. O script nunca arma o drone e nunca decola — mantenha as hélices retiradas.

**Padrões** — canal 3 (FCU ch 11 = AUX OUT 3), hold 1000 us, release 2000 us; MAVROS já em execução:

```bash
python3 servo_test.py
```

**Canal e presets personalizados**

```bash
python3 servo_test.py --channel 4 --hold 1100 --release 1900
```

No prompt `servo>`:

```
servo> 1500              # send PWM 1500 to current channel
servo> ch 3               # switch to AUX OUT 3 (FCU ch 11)
servo> hold               # send 'hold' preset
servo> release            # send 'release' preset
servo> sweep 1000 2000 100 0.3
servo> cycle 3 0.8        # toggle hold<->release 3 times, 0.8s apart
servo> set hold 1100      # update presets at runtime
servo> status             # channel, last PWM, FCU state
```

`do_servo(N, pwm)` mapeia para o número de servo `N + 8` do FCU, então `ch 3` aciona o AUX OUT
3 em um FCU no estilo Pixhawk (o Copter recomenda AUX OUT 1-4 para servos de hobby a 50 Hz;
evite MAIN OUT 1-8, que rodam a 400 Hz). Se uma escrita retornar `OK` mas o servo não se
mover, verifique a chave de segurança e se `SERVOx_FUNCTION = 0` no ArduPilot. Veja
[common-servo](https://ardupilot.org/copter/docs/common-servo.html) e
[MAV_CMD_DO_SET_SERVO](https://mavlink.io/en/messages/common.html#MAV_CMD_DO_SET_SERVO).
