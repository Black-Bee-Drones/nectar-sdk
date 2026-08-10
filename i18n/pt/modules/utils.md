# Módulo de Utilitários

Funções utilitárias compartilhadas para gerenciamento de processos, cálculos de GPS e operações de posição.

## Componentes

| Arquivo | Descrição |
|------|-------------|
| `process.py` | Gerenciamento do ciclo de vida de processos e checagens do grafo do ROS 2 (tmux/gnome-terminal) |
| `gps_calculate.py` | Transformações de coordenadas GPS e cálculos de distância |
| `position_utils.py` | Conversões e transformações de posição/orientação |
| `log.py` | Helpers de cor/símbolo ANSI para saída de log no terminal (`OK`, `ERR`, `WARN`, `ARROW`) |

## ProcessUtils

Gerencia processos externos com tmux ou fallback para gnome-terminal.

### API

| Método | Descrição |
|--------|-------------|
| `is_gui_available()` | Verifica se o gnome-terminal está disponível |
| `get_ros2_nodes(timeout)` | Obtém a lista de nomes de nós ROS2 em execução |
| `is_node_running(node_pattern, timeout)` | Verifica se um nó ROS2 correspondente ao padrão está em execução |
| `wait_for_node(node_pattern, timeout, poll_interval)` | Espera um nó ROS2 aparecer |
| `get_ros2_topics(timeout)` | Obtém a lista de nomes de tópicos ROS 2 anunciados |
| `is_topic_present(topic_pattern, timeout)` | Verifica se um tópico correspondente ao padrão está anunciado |
| `wait_for_topic(topic_pattern, timeout, poll_interval)` | Espera um tópico ROS 2 aparecer |
| `start_process(command, name, gui)` | Inicia um comando em uma sessão tmux ou terminal |
| `has_process(name)` | Verifica se a sessão tmux existe |
| `kill_process(name)` | Termina a sessão tmux |

### Uso

```python
from nectar.utils.process import ProcessUtils

# Check if ROS2 node is running

if ProcessUtils.is_node_running("mavros_node"):
    print("MAVROS node is running")

# Start a ROS2 node in background

ProcessUtils.start_process(
    command="ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:921600",
    name="mavros_node",
    gui=False  # Use tmux (headless)
)

# Wait for node to appear

if ProcessUtils.wait_for_node("mavros_node", timeout=10.0):
    print("MAVROS node started")

# Wait for a topic before connecting

if ProcessUtils.wait_for_topic("/mavros/local_position/pose", timeout=10.0):
    print("Local position topic is live")

# Check if tmux session exists

if ProcessUtils.has_process("mavros_node"):
    print("MAVROS session exists")

# Stop the process

ProcessUtils.kill_process("mavros_node")
```

### Comportamento

- `start_process()` verifica se já existe uma sessão tmux e a mata antes de iniciar
- `kill_process()` retorna True se a sessão não existir (sem erro)
- Todos os métodos usam o módulo de logging do Python (sem instruções print)
- A detecção de nós ROS2 usa o comando `ros2 node list`
- A detecção de tópicos usa o comando `ros2 topic list`

## Helpers de log

`log.py` fornece símbolos coloridos em ANSI para saída de CLI. Eles se autodesabilitam quando o stderr não é um
TTY, quando `NO_COLOR` está definido, ou quando `RCUTILS_COLORIZED_OUTPUT=0` (convenção do ROS 2).

```python
from nectar.utils.log import OK, ERR, WARN, ARROW

print(f"{OK} Driver started")
print(f"{ERR} Connection failed")
print(f"{WARN} Retrying...")
print(f"{ARROW} Next step: arm")
```

## Utilitários de GPS

Cálculos de coordenadas geográficas usando [geographiclib](https://geographiclib.sourceforge.io/) para operações geodésicas.

### Classe GPSCalculate

Classe utilitária estática para cálculos de coordenadas GPS.

| Método | Descrição |
|--------|-------------|
| `haversine(lat1, lon1, lat2, lon2)` | Distância entre pontos GPS usando a fórmula de Haversine (metros) |
| `bearing(lat1, lon1, lat2, lon2)` | Ângulo de rumo inicial entre pontos (graus, 0-360°) |
| `calculate_gps_offset(x, y, z, lat, lon, alt, heading)` | Calcula novas coordenadas GPS a partir de um offset em metros |
| `interp_geo(start, end, frac)` | Interpolação geodésica entre duas coordenadas GPS |
| `generate_point_grid(vertices, grid_shape)` | Gera uma grade 2D de coordenadas GPS dentro de uma área quadrilateral |

### Uso

```python
from nectar.utils.gps_calculate import GPSCalculate

# Calculate distance between two GPS coordinates

dist = GPSCalculate.haversine(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Distance: {dist:.2f} m")

# Calculate bearing

bearing = GPSCalculate.bearing(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Bearing: {bearing:.1f}°")

# Calculate GPS offset

new_lat, new_lon, new_alt = GPSCalculate.calculate_gps_offset(
    x=10.0,  # 10 meters east
    y=5.0,   # 5 meters north
    z=2.0,   # 2 meters up
    latitude=-27.1234,
    longitude=-48.4567,
    altitude=100.0,
    heading=45.0  # degrees
)

# Interpolate between GPS points

midpoint = GPSCalculate.interp_geo(
    start=(-27.1234, -48.4567),
    end=(-27.1245, -48.4578),
    frac=0.5  # 50% of the way
)

# Generate grid of GPS points

vertices = (
    (-27.1234, -48.4567),  # top-left
    (-27.1234, -48.4578),  # top-right
    (-27.1245, -48.4578),  # bottom-right
    (-27.1245, -48.4567),  # bottom-left
)
grid = GPSCalculate.generate_point_grid(vertices, grid_shape=(10, 10))
```

### Precisão: Haversine vs Geodésica

`PositionUtils.get_body_distance()` usa `Geodesic.WGS84.Inverse` ([Karney 2013](https://doi.org/10.1007/s00190-012-0578-z)) para distância e rumo GPS. Haversine (esférica, R=6371km) permanece em `GPSCalculate` para uso geral.

Pontos posicionados em distâncias exatas conhecidas usando `Geodesic.WGS84.Direct` (precisão de ~15nm). Os dois métodos então calculam a distância. Veja o [script de benchmark completo](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/experiments/benchmark_geodesic_vs_haversine.py).

**Erro de distância** (contra distâncias exatas conhecidas):

| Distância | Erro geodésico | Erro Haversine | Haversine % |
|----------|---------------:|----------------:|------------:|
| 1m N | 0,80 nm | 0,35 cm | 0,353% |
| 1m E | 0,09 nm | 0,18 cm | 0,181% |
| 5m N | 0,10 nm | 1,77 cm | 0,353% |
| 10m E | 0,14 nm | 1,81 cm | 0,181% |
| 50m N | 0,16 nm | 17,66 cm | 0,353% |
| 100m E | 0,02 nm | 18,08 cm | 0,181% |
| 1km | 0,00 nm | 1,23 m | 0,123% |
| 5km | 0,00 nm | 17,68 m | 0,354% |
| 100km | 0,00 nm | 121,91 m | 0,122% |
| 500km | 0,00 nm | 2138,93 m | 0,428% |

O erro do Haversine é (0,1%–0,43%), causado pelo achatamento da Terra (1/298). Ele subestima distâncias equatoriais (~0,11%) e polares (~0,45%) porque o raio de curvatura real difere da esfera média.

**Erro de rumo**: A geodésica é exata (0,000000°). O Haversine tem erro < 0,2° em casos típicos.

**Tempo de execução** (média sobre 10.000 iterações):

| Escala | Haversine+Bearing | Geodesic.Inverse | Razão |
|-------|------------------:|-----------------:|------:|
| 1m | 18 µs | 37 µs | 2,1x |
| 10m | 17 µs | 93 µs | 5,4x |
| 1km | 22 µs | 38 µs | 1,7x |
| 100km | 18 µs | 93 µs | 5,1x |
| 5570km | 18 µs | 152 µs | 8,4x |

Os dois são desprezíveis para um loop PID de 100Hz (orçamento de 10ms). O pior caso da geodésica é < 200µs.

## Utilitários de posição

Transformações de coordenadas, conversões de rotação e utilitários de mensagens ROS.

### Classe PositionUtils

Classe utilitária estática para operações de posição e orientação.

| Método | Descrição |
|--------|-------------|
| `get_body_distance(target, current, heading)` | Calcula a distância da posição atual até o alvo em coordenadas de frame de corpo (body) |
| `get_yaw_from_pose(pose)` | Extrai o ângulo de yaw de uma mensagem de pose do ROS (radianos) |
| `compute_yaw_error(target_yaw, current_yaw, threshold)` | Calcula o erro de yaw pelo caminho mais curto, em radianos, com deadband opcional |
| `convert_position_to_target(pose, heading, lidar)` | Converte mensagens de posição para tipos de mensagem de alvo (target) |
| `transform_takeoff_to_body_velocities(vx, vy, vz, current_yaw, takeoff_yaw)` | Transforma velocidades do frame de takeoff para o frame de corpo |

### Uso

```python
from nectar.utils.position_utils import PositionUtils
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget

# Calculate body frame distance

dx_body, dy_body, dz_body = PositionUtils.get_body_distance(
    target=target_position,  # PositionTarget or GeoPoseStamped
    current=current_pose,     # PoseStamped, PoseWithCovarianceStamped, or NavSatFix
    heading=45.0  # degrees (required for NavSatFix)
)

# Extract yaw from pose

yaw = PositionUtils.get_yaw_from_pose(pose_message)  # radians

# Compute yaw error (shortest path, wrapped to [-pi, pi])

import numpy as np
dyaw = PositionUtils.compute_yaw_error(target_yaw=1.0, current_yaw=0.5)  # radians
dyaw = PositionUtils.compute_yaw_error(1.0, 0.5, threshold=np.radians(3))  # with deadband

# Convert position to target message

target = PositionUtils.convert_position_to_target(
    pose=current_pose,
    heading=45.0,  # degrees, required for NavSatFix
    lidar=2.5  # optional altitude override
)

# Transform velocities from takeoff frame to body frame

vx_body, vy_body, vz_body = PositionUtils.transform_takeoff_to_body_velocities(
    vx=1.0,
    vy=0.5,
    vz=0.0,
    current_yaw=0.785,  # radians (45°)
    takeoff_yaw=0.0     # radians
)
```

### Tipos de mensagem suportados

**PositionUtils.get_body_distance()**:

- `target`: `PositionTarget` (local) ou `GeoPoseStamped` (GPS)
- `current`: `PoseStamped` ou `PoseWithCovarianceStamped` (local) ou `NavSatFix` (GPS)

**PositionUtils.get_yaw_from_pose()**:

- `PoseStamped`, `PoseWithCovarianceStamped`, `GeoPoseStamped`, ou `PositionTarget`

**PositionUtils.compute_yaw_error()**:

- `target_yaw`, `current_yaw`: floats em radianos
- `threshold`: deadband opcional em radianos (erros abaixo desse valor retornam 0.0)

**PositionUtils.convert_position_to_target()**:

- `PoseStamped` / `PoseWithCovarianceStamped` → `PositionTarget` (local)
- `NavSatFix` → `GeoPoseStamped` (GPS, exige heading)

## Dependências

| Pacote | Finalidade |
|---------|---------|
| `geographiclib` | Cálculos geodésicos (elipsoide WGS84) |
| `tf_transformations` | Conversões de quaternion/Euler do ROS |
| `numpy` | Operações com arrays |
| `geographic_msgs` | Tipos de mensagem GPS do ROS |
| `geometry_msgs` | Tipos de mensagem de pose do ROS |
| `mavros_msgs` | Tipos de mensagem do MAVROS |
| `sensor_msgs` | Tipos de mensagem de sensores do ROS |
