# MIRELA SDK - Guia de Instalação

Este guia fornece instruções para instalar e configurar o ambiente completo do **MIRELA SDK** em sistemas Ubuntu/Debian sem necessidade de Docker.

## 📋 Pré-requisitos

- **Sistema Operacional**: Ubuntu 22.04+
- **Espaço em disco**: Mínimo 10GB livres
- **Memória RAM**: Mínimo 4GB (recomendado 8GB+)
- **Conexão com internet**: Necessária para download de dependências

## 🚀 Instalação Rápida

### Opção 1: Instalação Completa (Recomendada)

```bash
# Baixe o script de instalação
wget https://raw.githubusercontent.com/Black-Bee-Drones/mirela-sdk/main/scripts/install_env.sh
# Ou baixe o script de instalação direto pelo GitHub

# Torna o script executável
chmod +x install_env.sh

# Execute o script de instalação
./install_env.sh
```

O script irá:
1. ✅ Atualizar o sistema
2. ✅ Instalar pacotes essenciais (incluindo Git)
3. ✅ Configurar Git e SSH
4. ✅ Instalar ROS 2 Humble
5. ✅ Configurar GeographicLib para MAVROS
6. ✅ Clonar repositório mirela-sdk
7. ✅ Instalar dependências Python
8. ✅ Configurar workspace ROS 2
9. ✅ Configurar ambiente
10. ✅ Construir workspace
11. ✅ Verificar instalação

## 🔧 Componentes Instalados

### Sistema Base
- **Git** - Controle de versão
- **Python 3** - Linguagem de programação
- **Build tools** - Ferramentas de compilação
- **Câmera tools** - fswebcam, v4l-utils

### ROS 2 Humble
- **ros-humble-desktop-full** - Instalação completa do ROS 2
- **ros-humble-mavros** - Comunicação MAVLink
- **ros-humble-mavros-extras** - Extensões MAVROS
- **ros-humble-tf-transformations** - Transformações geométricas
- **python3-colcon-common-extensions** - Ferramentas de build

### Dependências Python

See [`requirements.txt`](requirements.txt)

### Workspace ROS 2
- **Localização**: `~/ros2_ws`
- **vision_opencv** - Suporte a visão computacional
- **mirela-sdk** - Pacote principal

## 🎯 Após a Instalação

### 1. Reiniciar Terminal
```bash
# Reinicie o terminal ou execute:
source ~/.bashrc
```

### 2. Verificar Instalação
```bash
# Verificar ROS 2
ros2 --version

# Verificar pacotes
cd ~/ros2_ws
ros2 pkg list | grep mirela

# Testar nós do mirela_sdk
ros2 run mirela_sdk gui
```

### 3. Estrutura do Workspace
```
~/ros2_ws/
├── src/
│   ├── vision_opencv/          # Suporte OpenCV
│   └── mirela-sdk/            # Pacote principal
├── build/                     # Arquivos de build
├── install/                   # Arquivos instalados
└── log/                      # Logs de build
```

## 🐛 Solução de Problemas

### Erro: "Não foi possível baixar o script"
```bash
# Alternativa usando curl
curl -O https://raw.githubusercontent.com/Black-Bee-Drones/mirela-sdk/main/install_env.sh
chmod +x install_env.sh

# Ou clone o repositório manualmente
git clone https://github.com/Black-Bee-Drones/mirela-sdk.git
cd mirela-sdk
./install_env.sh
```

### Erro: "ROS 2 não encontrado"
```bash
# Verificar se o ambiente está configurado
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/local_setup.bash
```

### Erro: "Pacote mirela_sdk não encontrado"
```bash
# Reconstruir workspace
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```

### Erro: "Dependências Python não encontradas"
```bash
# Reinstalar dependências
cd ~/ros2_ws/src/mirela-sdk
pip install -r requirements.txt
```

### Erro: "Permissão negada para câmera"
```bash
# Verificar se usuário está no grupo video
groups $USER | grep video

# Se não estiver, adicionar e reiniciar sessão
sudo usermod -a -G video $USER
# Fazer logout/login
```

### Erro: "GeographicLib datasets não encontrados"
```bash
# Reconfigurar GeographicLib
wget https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh
chmod +x install_geographiclib_datasets.sh
sudo ./install_geographiclib_datasets.sh
```

## 🔄 Atualizações

### Atualizar mirela-sdk
```bash
cd ~/ros2_ws/src/mirela-sdk
git pull origin main
cd ~/ros2_ws
colcon build --symlink-install
```

### Atualizar dependências Python
```bash
cd ~/ros2_ws/src/mirela-sdk
pip install -r requirements.txt --upgrade
```

## 📚 Exemplos de Uso

### Executar GUI
```bash
ros2 run mirela_sdk gui
```

### Testar Movimentação Básica
```bash
ros2 run mirela_sdk test_velocity
```

### Testar GPS
```bash
ros2 run mirela_sdk test_gps
```

### Visualizar Câmera Raspberry Pi
```bash
ros2 run mirela_sdk test_raspicam
```

### Detecção de ArUco
```bash
ros2 run mirela_sdk aruco_node
```

### Calibração de Cores
```bash
ros2 run mirela_sdk color_calibration_node
```

### Detecção de Linhas
```bash
ros2 run mirela_sdk line_detection_node
```

## 🆘 Suporte

Se encontrar problemas durante a instalação:

1. **Verifique os logs** do script de instalação
2. **Execute a verificação** com `./install_env.sh` (opção 3)
3. **Consulte a documentação** do ROS 2 Humble
4. **Abra uma issue** no repositório GitHub

## 📝 Notas Importantes

- ⚠️ **Não execute como root** - O script detecta e impede execução como root
- 🔄 **Backup automático** - O script faz backup do `.bashrc` antes de modificar
- 🎯 **Instalação modular** - Você pode escolher quais etapas executar
- 🔍 **Verificação automática** - O script verifica se componentes já estão instalados

---

**🚀🐝 AVANTE! Ambiente mirela_sdk pronto para uso!**