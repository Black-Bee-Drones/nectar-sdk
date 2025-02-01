$imageName = "blackbee:ros2-humble"
$containerName = "ros2_black_bee"
$dockerfilePath = "docker/Dockerfile"

# Constrói a imagem Docker
if ($args[0] -eq "build") {
    Write-Host "Construindo a imagem Docker..."
    docker build -t $imageName -f $dockerfilePath .
}

# Executa o container Docker
Write-Host "Iniciando o container..."
docker run -it `
    --name=$containerName `
    --env="DISPLAY=host.docker.internal:0.0" `
    --net="host" `
    $imageName `
    bash
