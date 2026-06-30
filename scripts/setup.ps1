$ErrorActionPreference = "Stop"

$RootDirectory = Split-Path -Parent $PSScriptRoot
Set-Location $RootDirectory

Write-Host "Checking required tools..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed."
}

docker compose version | Out-Null

docker info *> $null

if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running."
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
}
else {
    throw "Python is not installed."
}

if (-not (Test-Path ".env")) {
    Write-Host "Creating local .env configuration..."

    $GrafanaPassword = (
        [guid]::NewGuid().ToString("N")
        + [guid]::NewGuid().ToString("N")
    )

    $EnvironmentContent = @"
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=$GrafanaPassword
APP_VERSION=1.0.0
APP_COLOR=blue
"@

    $Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)

    [System.IO.File]::WriteAllText(
        (Join-Path $RootDirectory ".env"),
        $EnvironmentContent,
        $Utf8WithoutBom
    )

    Write-Host "Created .env with a generated Grafana password."
}
else {
    Write-Host "Using the existing local .env file."
}

if (-not (Test-Path "nginx/active.conf")) {
    Write-Host "Creating initial blue gateway configuration..."
    Copy-Item "nginx/default.conf" "nginx/active.conf"
}

Write-Host "Validating Docker Compose configuration..."
docker compose config --quiet

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "Building and starting all services..."
docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose startup failed."
}

Write-Host "Running deployment verification..."
& $PythonCommand scripts/smoke_test.py

if ($LASTEXITCODE -ne 0) {
    throw "Smoke testing failed."
}

Write-Host ""
Write-Host "Environment preparation completed successfully."
Write-Host "Application: http://localhost:5000"
Write-Host "Grafana:    http://localhost:3000"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "Loki:       http://localhost:3100"
Write-Host ""
Write-Host "Grafana credentials are stored in the local .env file."
