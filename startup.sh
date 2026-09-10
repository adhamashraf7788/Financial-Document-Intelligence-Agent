#!/bin/bash
# LEDGER Financial Document Intelligence - Local Startup Script
# Runs all services locally without Docker (for development)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if .env exists
if [ ! -f .env ]; then
    log_error ".env file not found. Create it with GROQ_API_KEY=your-key"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 not found"
    exit 1
fi

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    log_warn "Not in a virtual environment. Consider: python3 -m venv .venv && source .venv/bin/activate"
fi

# Function to check if port is in use
port_in_use() {
    lsof -i:"$1" >/dev/null 2>&1
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for $name at $url..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" >/dev/null 2>&1; then
            log_info "$name is ready!"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    log_error "$name failed to start after $((max_attempts * 2)) seconds"
    return 1
}

# Kill any existing processes on our ports
log_info "Cleaning up existing processes..."
for port in 7000 7860 8000 8002 8085; do
    if port_in_use $port; then
        log_warn "Port $port in use, killing process..."
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
    fi
done

# Start Weaviate (required for retrieval)
log_info "Starting Weaviate..."
if ! port_in_use 8085; then
    docker run -d \
        --name weaviate-local \
        -p 8085:8080 \
        -p 50052:50051 \
        -e QUERY_DEFAULTS_LIMIT=25 \
        -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
        -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
        -e DEFAULT_VECTORIZER_MODULE=none \
        -e ENABLE_MODULES="" \
        -e CLUSTER_HOSTNAME=node1 \
        -v weaviate_data:/var/lib/weaviate \
        cr.weaviate.io/semitechnologies/weaviate:1.28.0
    
    wait_for_service "http://localhost:8085/v1/.well-known/ready" "Weaviate"
else
    log_info "Weaviate already running on port 8085"
fi

# Install dependencies if needed
install_deps() {
    local service_dir=$1
    local req_file="$service_dir/requirements.txt"
    if [ -f "$req_file" ]; then
        log_info "Installing dependencies for $service_dir..."
        pip install --quiet -r "$req_file" --default-timeout=1000
    fi
}

# Install all dependencies
log_info "Installing Python dependencies..."
install_deps "services/retrieval"
install_deps "services/agent"
install_deps "services/ui"
install_deps "services/doc_processor"
install_deps "shared"

# Start Retrieval Service (port 8000)
log_info "Starting Retrieval Service on port 8000..."
cd "$PROJECT_ROOT/services/retrieval"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export WEAVIATE_HOST=localhost
export WEAVIATE_PORT=8085
export WEAVIATE_GRPC_PORT=50051
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/retrieval.log 2>&1 &
RETRIEVAL_PID=$!
cd "$PROJECT_ROOT"

wait_for_service "http://localhost:8000/health" "Retrieval Service"

# Start Agent Service (port 7000)
log_info "Starting Agent Service on port 7000..."
cd "$PROJECT_ROOT/services/agent"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export RETRIEVAL_SERVICE_URL=http://localhost:8000/search/pipeline
python -m uvicorn main:app --host 0.0.0.0 --port 7000 --reload > /tmp/agent.log 2>&1 &
AGENT_PID=$!
cd "$PROJECT_ROOT"

wait_for_service "http://localhost:7000/health" "Agent Service"

# Start Doc Processor (port 8002)
log_info "Starting Document Processor on port 8002..."
cd "$PROJECT_ROOT/services/doc_processor"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload > /tmp/doc_processor.log 2>&1 &
DOC_PROCESSOR_PID=$!
cd "$PROJECT_ROOT"

wait_for_service "http://localhost:8002/health" "Document Processor"

# Start UI Service (port 7860)
log_info "Starting UI Service on port 7860..."
cd "$PROJECT_ROOT/services/ui"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export AGENT_SERVICE_URL=http://localhost:7000
export GRADIO_SHARE=False
python app.py > /tmp/ui.log 2>&1 &
UI_PID=$!
cd "$PROJECT_ROOT"

# Give UI a moment to start
sleep 3

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}All services started!${NC}"
echo "=========================================="
echo "Weaviate:        http://localhost:8085"
echo "Retrieval API:   http://localhost:8000"
echo "Agent API:       http://localhost:7000"
echo "Doc Processor:   http://localhost:8002"
echo "UI (Gradio):     http://localhost:7860"
echo ""
echo "Dashboard:       http://localhost:7000/api/v1/dashboard"
echo "Agent Health:    http://localhost:7000/health"
echo "Retrieval Health: http://localhost:8000/health"
echo ""
echo "Logs:"
echo "  Retrieval:      tail -f /tmp/retrieval.log"
echo "  Agent:          tail -f /tmp/agent.log"
echo "  Doc Processor:  tail -f /tmp/doc_processor.log"
echo "  UI:             tail -f /tmp/ui.log"
echo ""
echo "PIDs: Retrieval=$RETRIEVAL_PID, Agent=$AGENT_PID, DocProcessor=$DOC_PROCESSOR_PID, UI=$UI_PID"
echo ""
echo "Press Ctrl+C to stop all services"

# Trap Ctrl+C to kill all child processes
trap 'kill $RETRIEVAL_PID $AGENT_PID $DOC_PROCESSOR_PID $UI_PID 2>/dev/null; docker stop weaviate-local 2>/dev/null; echo ""; log_info "All services stopped"; exit 0' INT

# Wait for all background processes
wait