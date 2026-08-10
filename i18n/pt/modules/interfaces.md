# Nectar Interfaces

Definições de mensagens ROS2 customizadas para o Nectar SDK.

## Visão geral

Este pacote fornece tipos de mensagem ROS2 customizados usados pelos módulos de vision e control para publicar resultados de detecção e dados de sensores.

## Mensagens

### ArucoTransforms

Dados de estimativa de pose de marcadores ArUco.

**Arquivo:** `msg/ArucoTransforms.msg`

```
int32 id
geometry_msgs/Vector3 translation
std_msgs/Float64 yaw
```

| Campo | Tipo | Descrição |
|-------|------|-------------|
| `id` | `int32` | ID do marcador detectado |
| `translation` | `geometry_msgs/Vector3` | Posição 3D relativa à câmera (metros) |
| `yaw` | `std_msgs/Float64` | Ângulo de rotação do marcador (graus, 0-360) |

**Publicado por:** `ArucoNode` · **Tópico:** `/aruco/pose_estimate`

---

### LineInfo

Informação de estado da detecção de linha.

**Arquivo:** `msg/LineInfo.msg`

```
float64 center_x
float64 center_y
float64 angle
float64 width
float64 height
```

| Campo | Tipo | Descrição |
|-------|------|-------------|
| `center_x` | `float64` | Coordenada X do centro da linha (pixels) |
| `center_y` | `float64` | Coordenada Y do centro da linha (pixels) |
| `angle` | `float64` | Ângulo da linha (graus, -90 a +90) |
| `width` | `float64` | Largura média da linha (pixels) |
| `height` | `float64` | Altura média da linha (pixels) |

**Publicado por:** `LineDetectionNode` · **Tópico:** `line_state/{color}` (por exemplo, `line_state/blue`)

---

### PhotoInfo

Metadados de foto com coordenadas.

**Arquivo:** `msg/PhotoInfo.msg`

```
float64[] coordinates
string photo_num
```

| Campo | Tipo | Descrição |
|-------|------|-------------|
| `coordinates` | `float64[]` | Array de valores de coordenadas |
| `photo_num` | `string` | Identificador/número da foto |

---

## Dependências

| Pacote | Descrição |
|---------|-------------|
| `geometry_msgs` | Tipos de mensagem geométricos padrão do ROS2 (Vector3) |
| `std_msgs` | Tipos de mensagem padrão do ROS2 (Float64) |
| `rosidl_default_generators` | Geração de código IDL do ROS2 |

## Build

O pacote é buildado automaticamente com o workspace:

```bash
cd ~/ros2_ws
colcon build --packages-select nectar_interfaces
source install/setup.bash
```

Verifique:

```bash
ros2 interface list | grep nectar_interfaces
ros2 interface show nectar_interfaces/msg/ArucoTransforms
```

## Uso

**Python** — importar, publicar e subscrever:

```python
from nectar_interfaces.msg import ArucoTransforms, LineInfo, PhotoInfo
from geometry_msgs.msg import Vector3
from std_msgs.msg import Float64

# Publisher

pub = node.create_publisher(ArucoTransforms, '/aruco/pose_estimate', 10)
msg = ArucoTransforms()
msg.id = 42
msg.translation = Vector3(x=0.5, y=0.1, z=1.2)
msg.yaw = Float64(data=45.0)
pub.publish(msg)

# Subscriber

def on_aruco(msg: ArucoTransforms):
    print(f"Marker {msg.id} at ({msg.translation.x:.2f}, {msg.translation.y:.2f}, {msg.translation.z:.2f}) m")

node.create_subscription(ArucoTransforms, '/aruco/pose_estimate', on_aruco, 10)
```

**C++**:

```cpp
#include "nectar_interfaces/msg/aruco_transforms.hpp"

auto pub = node->create_publisher<nectar_interfaces::msg::ArucoTransforms>(
    "/aruco/pose_estimate", 10);
```

## Módulos relacionados

- [Vision Module](vision/) — drivers de câmera e algoritmos que publicam essas mensagens
- [Vision Nodes](vision/nodes/) — nós ROS 2 que usam essas interfaces

## Referências

- [Tutorial de interfaces do ROS2](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html)
- [Definição de mensagens do ROS2](https://docs.ros.org/en/humble/Concepts/About-ROS-Interfaces.html)
- [geometry_msgs](https://docs.ros.org/en/humble/p/geometry_msgs/)
- [std_msgs](https://docs.ros.org/en/humble/p/std_msgs/)
