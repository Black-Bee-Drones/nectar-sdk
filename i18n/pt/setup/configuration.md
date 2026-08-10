# Configuração

De onde o SDK lê versões e caminhos, e como sobrescrevê-los.

## Versões e listas de pacotes

Todas as versões e listas de pacotes ficam em um único arquivo:

```
scripts/lib/config.sh
```

Edite-o para mudar a distro ROS, a versão do PyTorch, a do librealsense, as listas apt e
mais. Todo script, o Makefile e o Dockerfile leem deste arquivo, então uma mudança aqui
se propaga. Overrides comuns por invocação (sem editar):

| Variável | Controla |
|---|---|
| `ROS_DISTRO` | Distribuição ROS 2 (p.ex. `humble`, `jazzy`, `kilted`) |
| `TORCH_VERSION` / `TORCHVISION_VERSION` | Par PyTorch (defina os dois juntos) |
| `LIBREALSENSE_VERSION` / `REALSENSE_ROS_TAG` | Versões da stack RealSense |

## Local do ambiente Python

<span id="python-environment-location"></span>

As dependências Python instalam em `$WORKSPACE/.venv`. Sobrescreva com `NECTAR_VENV=/path`;
um `VIRTUAL_ENV` ativo é respeitado. Para ativação e compartilhamento no workspace, veja
[Instalação — Ambiente Python](index.md#python-environment).

!!! warning "Deixe o SDK criar o venv"
    Use sempre `make python*` / `make setup` para criar `$WORKSPACE/.venv` — ele fixa o
    venv no `python3` do ROS. Um `uv venv` manual pode escolher um Python mais novo sem
    wheels para algumas dependências (p.ex. `mediapipe`).

## Mudar versões no workspace

Como `scripts/lib/config.sh` é a fonte única, atualizar uma dependência para todo o
workspace (SDK + seus pacotes de missão que compartilham o venv) é uma edição seguida de
uma nova execução do alvo `make python*` / `make pytorch` / `make realsense` correspondente.
