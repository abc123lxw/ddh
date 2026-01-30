# PowerShell script: Build and export Docker image with timestamp

$ErrorActionPreference = "Stop"

# Generate timestamp (format: YYYYMMDD_HHMMSS)
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Image name (with timestamp)
$imageName = "db-ops-analyzer:$timestamp"
$imageTag = "db-ops-analyzer:latest"

# Output directory
$outputDir = "F:\tmp"

# Check if output directory exists, create if not
if (-not (Test-Path $outputDir)) {
    Write-Host "Creating output directory: $outputDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# Output file name (with timestamp)
$outputFile = Join-Path $outputDir "db-ops-analyzer_$timestamp.tar"
$compressedFile = Join-Path $outputDir "db-ops-analyzer_$timestamp.tar.gz"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building and Exporting Docker Image" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Timestamp: $timestamp" -ForegroundColor Green
Write-Host "Image name: $imageName" -ForegroundColor Green
Write-Host "Output directory: $outputDir" -ForegroundColor Green
Write-Host ""

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Step 1: Build image
Write-Host "[1/3] Building Docker image..." -ForegroundColor Yellow
docker build -t $imageName -t $imageTag .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Image build failed" -ForegroundColor Red
    exit 1
}

Write-Host "Image built successfully: $imageName" -ForegroundColor Green
Write-Host ""

# Step 2: Export image to tar (temporary)
Write-Host "[2/3] Exporting image and compressing to tar.gz..." -ForegroundColor Yellow
Write-Host "Output file: $compressedFile" -ForegroundColor Gray

docker save $imageName -o $outputFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Image export failed" -ForegroundColor Red
    exit 1
}

# Step 3: Compress to tar.gz only, then remove .tar
if (Get-Command gzip -ErrorAction SilentlyContinue) {
    gzip -c $outputFile > $compressedFile
    if ($LASTEXITCODE -eq 0) {
        Remove-Item $outputFile -Force
        Write-Host "Image saved as tar.gz only: $compressedFile" -ForegroundColor Green
    } else {
        Write-Host "Warning: Compression failed, tar file kept: $outputFile" -ForegroundColor Yellow
    }
} else {
    $inputStream = [System.IO.File]::OpenRead($outputFile)
    $outputStream = [System.IO.File]::Create($compressedFile)
    $gzipStream = New-Object System.IO.Compression.GzipStream($outputStream, [System.IO.Compression.CompressionMode]::Compress)
    $inputStream.CopyTo($gzipStream)
    $gzipStream.Close()
    $outputStream.Close()
    $inputStream.Close()
    Remove-Item $outputFile -Force
    Write-Host "Image saved as tar.gz only: $compressedFile" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Display file information (only tar.gz)
Write-Host "Generated file:" -ForegroundColor Yellow
if (Test-Path $compressedFile) {
    $compressedSize = (Get-Item $compressedFile).Length / 1MB
    $compressedSizeStr = [math]::Round($compressedSize, 2).ToString()
    Write-Host "  - $compressedFile ($compressedSizeStr MB)" -ForegroundColor White
}

Write-Host ""
Write-Host "Image info:" -ForegroundColor Yellow
Write-Host "  - Image name: $imageName" -ForegroundColor White
Write-Host "  - Image tag: $imageTag" -ForegroundColor White

Write-Host ""
Write-Host "Usage:" -ForegroundColor Yellow
Write-Host "  Load image: gunzip -c `"$compressedFile`" | docker load" -ForegroundColor White
