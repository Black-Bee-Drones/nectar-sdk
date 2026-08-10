# Exemplos do Módulo Sensors

Teste na bancada os pipelines de sensores do computador de bordo antes de conectá-los a uma
missão.

| Script | O que faz |
|--------|--------------|
| `rangefinder_example.py` | Teste de bancada do pipeline TF-Luna → filtro → `DISTANCE_SENSOR` do MAVLink (sem ROS) |

## Argumentos

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--port` | `/dev/ttyUSB0` | Porta serial do TF-Luna |
| `--baud` | `115200` | Baud rate do TF-Luna |
| `--mavlink` | `udp:127.0.0.1:14551` | String de conexão MAVLink (UDP/TCP/serial) |
| `--mavlink-baud` | `921600` | Baud serial para endpoints MAVLink (ignorado para UDP/TCP) |
| `--filter` | `none` | `none` ou `obstacle_mask` |
| `--obstacle-height` | `0.0` | Altura do obstáculo (m); `<= 0` estima automaticamente |
| `--max-change` | `0.30` | Limiar de variação abrupta do mascaramento de obstáculo (m) |
| `--avg-window` | `10` | Janela de média do mascaramento de obstáculo (amostras) |
| `--estimate-lock-s` | `0.2` | Tempo para travar a altura auto-estimada (s) |
| `--timeout-s` | `5.0` | Timeout de leitura do sensor (s) |
| `--rate` | `50.0` | Taxa de publicação (Hz) |
| `--duration` | `0.0` | Tempo de execução (s); `0` = até Ctrl-C |

## Teste de bancada

**Passthrough bruto** (roda até Ctrl-C):

```bash
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551
```

**Auto-detecção da altura do obstáculo** (missão do hook e similares; não precisa de
conhecimento prévio):

```bash
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551 \
    --filter obstacle_mask \
    --duration 60
```

**Override de altura fixa** (SITL, fixtures conhecidas; trava em 1,7 m):

```bash
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551 \
    --filter obstacle_mask \
    --obstacle-height 1.7 \
    --duration 60
```

Resultado esperado: o script imprime amostras de distância filtradas a `--rate` Hz e as
transmite como `DISTANCE_SENSOR` do MAVLink; o tópico de rangefinder do FCU (abaixo) espelha
os valores.

Enquanto o script está rodando, em outro terminal, faça o echo do tópico de rangefinder do
FCU para confirmar que o stream mascarado está chegando ao EKF via MAVROS:

```bash
ros2 topic echo /mavros/rangefinder/rangefinder
```

Coloque um objeto de altura conhecida sob o sensor; o valor do tópico deve saltar
aproximadamente pela altura do objeto e se recuperar quando ele for removido.

Para implantações ROS, use o ponto de entrada `rangefinder_node.py` em vez disso:

```bash
ros2 run nectar rangefinder_node.py --ros-args \
    -p serial_port:=/dev/ttyUSB0 \
    -p mavlink_url:=udp:127.0.0.1:14551 \
    -p filter:=obstacle_mask
```

Veja [Sensors](../sensors.md) para a lista completa de parâmetros, os passos de
configuração do ArduPilot e a solução de problemas.
