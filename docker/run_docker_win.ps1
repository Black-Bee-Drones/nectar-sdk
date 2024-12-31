# Define as variáveis
$imageName = "blackbee:ros2-humble"
$containerName = "ros2_black_bee"
$dockerfilePath = "docker/Dockerfile"

# Constrói a imagem Docker
Write-Host "Building Docker image..."
docker build -t $imageName -f $dockerfilePath .

# Executa o container Docker
Write-Host "Running Docker container..."
docker run -it `
    --name=$containerName `
    --env="DISPLAY=host.docker.internal:0.0" `
    --net="host" `
    $imageName `
    bash
