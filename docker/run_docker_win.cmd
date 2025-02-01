@echo off

REM Configura o nome da imagem e do container
set IMAGE_NAME=blackbee:ros2-humble
set CONTAINER_NAME=ros2_black_bee

REM Caminho do Dockerfile
set DOCKERFILE_PATH=docker/Dockerfile

REM Constrói a imagem Docker
if "%1" == "build" (
    echo Construindo a imagem Docker...
    docker build -t %IMAGE_NAME% -f %DOCKERFILE_PATH% .
)

REM Executa o container Docker
echo Iniciando o container...
docker run -it ^
    --name=%CONTAINER_NAME% ^
    --env="DISPLAY=host.docker.internal:0.0" ^
    --net=host ^
    %IMAGE_NAME% ^
    bash
