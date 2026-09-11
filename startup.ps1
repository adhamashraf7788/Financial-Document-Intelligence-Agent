#!/usr/bin/env pwsh
# LEDGER Financial Document Intelligence - Local Startup Script (PowerShell)
# Runs all services locally without Docker (for development on Windows)

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PROJECT_ROOT

# Colors for output
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Error ".env file not found. Create it with GROQ_API_KEY=your-key"
    exit 1
}

# Load environment variables
Get-Content .env | Where-Object { -not $_.StartsWith("#") -and $_ -match "=" } | ForEach-Object {
    $parts = $_.Split("=", 2)
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
}

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found in PATH"
    exit 1
}

# Function to check if port is in use
function Port-InUse { param($port) (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue) -ne $null }

# Function to check if weaviate container is running
function Weaviate-ContainerRunning {
    $container = docker ps --filter "name=weaviate" --filter "status=running" --format "{{.Names}}" 2>$null
    return $container -eq "weaviate"
}

# Function to wait for service to be ready
function Wait-ForService {
    param($url, $name, $maxAttempts = 30)
    Write-Info "Waiting for $name at $url..."
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Info "$name is ready!"
                return $true
            }
        } catch { }
        Start-Sleep 2
    }
    Write-Error "$name failed to start after $($maxAttempts * 2) seconds"
    return $false
}

# Kill any existing processes on our ports
Write-Info "Cleaning up existing processes..."
@(7000, 7860, 8000, 8002, 8085) | ForEach-Object {
    if (Port-InUse $_) {
        Write-Warn "Port $_ in use, killing process..."
        Get-Process -Id (Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

# Start Weaviate (required for retrieval)
Write-Info "Checking for existing Weaviate container..."
if (Weaviate-ContainerRunning) {
    Write-Info "Found existing Weaviate container 'weaviate', using it"
    # Get port mappings from the container
    $httpPort = (docker port weaviate 8080 2>$null) -replace '.*:',''
    $grpcPort = (docker port weaviate 50051 2>$null) -replace '.*:',''
    $env:WEAVIATE_HOST = "localhost"
    $env:WEAVIATE_PORT = if ($httpPort) { $httpPort } else { "8085" }
    $env:WEAVIATE_GRPC_PORT = if ($grpcPort) { $grpcPort } else { "50052" }
    Write-Info "Weaviate HTTP: localhost:$env:WEAVIATE_PORT, GRPC: localhost:$env:WEAVIATE_GRPC_PORT"
} elseif (-not (Port-InUse 8085)) {
    Write-Info "Starting new Weaviate container..."
    docker run -d `
        --name weaviate-local `
        -p 8085:8080 `
        -p 50052:50051 `
        -e QUERY_DEFAULTS_LIMIT=25 `
        -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true `
        -e PERSISTENCE_DATA_PATH=/var/lib/weaviate `
        -e DEFAULT_VECTORIZER_MODULE=none `
        -e ENABLE_MODULES="" `
        -e CLUSTER_HOSTNAME=node1 `
        -v weaviate_data:/var/lib/weaviate `
        cr.weaviate.io/semitechnologies/weaviate:1.28.0
    
    $env:WEAVIATE_HOST = "localhost"
    $env:WEAVIATE_PORT = "8085"
    $env:WEAVIATE_GRPC_PORT = "50052"
    Wait-ForService "http://localhost:8085/v1/.well-known/ready" "Weaviate"
} else {
    Write-Info "Weaviate already running on port 8085"
    $env:WEAVIATE_HOST = "localhost"
    $env:WEAVIATE_PORT = "8085"
    $env:WEAVIATE_GRPC_PORT = "50052"
}

# Install dependencies if needed
function Install-Deps { param($serviceDir) 
    $reqFile = Join-Path $serviceDir "requirements.txt"
    if (Test-Path $reqFile) {
        Write-Info "Installing dependencies for $serviceDir..."
        python -m pip install -r $reqFile --default-timeout=1000
    }
}

# Install all dependencies
Write-Info "Installing Python dependencies..."
Install-Deps "services/retrieval"
Install-Deps "services/agent"
Install-Deps "services/ui"
Install-Deps "services/doc_processor"
Install-Deps "shared"

$env:PYTHONPATH = "$PROJECT_ROOT;$env:PYTHONPATH"

# Start Retrieval Service (port 8000)
Write-Info "Starting Retrieval Service on port 8000..."
# WEAVIATE_HOST, WEAVIATE_PORT, WEAVIATE_GRPC_PORT already set above
$retrievalProc = Start-Process python -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" -WorkingDirectory "$PROJECT_ROOT\services\retrieval" -PassThru -RedirectStandardOutput "$env:TEMP\retrieval.log" -RedirectStandardError "$env:TEMP\retrieval.err.log"

Wait-ForService "http://localhost:8000/health" "Retrieval Service"

# Start Agent Service (port 7000)
Write-Info "Starting Agent Service on port 7000..."
$env:RETRIEVAL_SERVICE_URL = "http://localhost:8000/search/pipeline"
$agentProc = Start-Process python -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000", "--reload" -WorkingDirectory "$PROJECT_ROOT\services\agent" -PassThru -RedirectStandardOutput "$env:TEMP\agent.log" -RedirectStandardError "$env:TEMP\agent.err.log"

Wait-ForService "http://localhost:7000/health" "Agent Service"

# Start Doc Processor (port 8002)
Write-Info "Starting Document Processor on port 8002..."
$docProcessorProc = Start-Process python -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--reload" -WorkingDirectory "$PROJECT_ROOT\services\doc_processor" -PassThru -RedirectStandardOutput "$env:TEMP\doc_processor.log" -RedirectStandardError "$env:TEMP\doc_processor.err.log"

Wait-ForService "http://localhost:8002/health" "Document Processor"

# Start UI Service (port 7860)
Write-Info "Starting UI Service on port 7860..."
$env:AGENT_SERVICE_URL = "http://localhost:7000"
$env:GRADIO_SHARE = "False"
$uiProc = Start-Process python -ArgumentList "app.py" -WorkingDirectory "$PROJECT_ROOT\services\ui" -PassThru -RedirectStandardOutput "$env:TEMP\ui.log" -RedirectStandardError "$env:TEMP\ui.err.log"

Start-Sleep 3

# Summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "All services started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Weaviate:        http://localhost:8085"
Write-Host "Retrieval API:   http://localhost:8000"
Write-Host "Agent API:       http://localhost:7000"
Write-Host "Doc Processor:   http://localhost:8002"
Write-Host "UI (Gradio):     http://localhost:7860"
Write-Host ""
Write-Host "Dashboard:       http://localhost:7000/api/v1/dashboard"
Write-Host "Agent Health:    http://localhost:7000/health"
Write-Host "Retrieval Health: http://localhost:8000/health"
Write-Host ""
Write-Host "Logs:"
Write-Host "  Retrieval:      Get-Content $env:TEMP\retrieval.log -Wait"
Write-Host "  Agent:          Get-Content $env:TEMP\agent.log -Wait"
Write-Host "  Doc Processor:  Get-Content $env:TEMP\doc_processor.log -Wait"
Write-Host "  UI:             Get-Content $env:TEMP\ui.log -Wait"
Write-Host ""
Write-Host "PIDs: Retrieval=$($retrievalProc.Id), Agent=$($agentProc.Id), DocProcessor=$($docProcessorProc.Id), UI=$($uiProc.Id)"
Write-Host ""
Write-Host "Press Ctrl+C to stop all services"

# Trap Ctrl+C
$cleanup = {
    Write-Host ""
    Write-Info "Stopping all services..."
    $retrievalProc, $agentProc, $docProcessorProc, $uiProc | ForEach-Object { if ($_) { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } }
    docker stop weaviate-local -ErrorAction SilentlyContinue
    Write-Info "All services stopped"
    exit 0
}
# Only stops weaviate-local (our created container), not the existing 'weaviate' container
Register-EngineEvent -SourceIdentifier ([System.Console]::CancelKeyPress) -Action $cleanup -SupportEvent

# Wait for all processes
while ($true) { Start-Sleep 10 }