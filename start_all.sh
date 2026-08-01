#!/bin/bash

echo "Stopping old services..."
for p in 8000 8001 8002 8003 8004 8005 8006 8080
do
    lsof -ti tcp:$p | xargs kill -9 2>/dev/null
done

echo "Activating virtual environment..."
source ~/Downloads/sahaay/venv/bin/activate

echo "Starting System Orchestrator..."
cd ~/Downloads/sahaay/system_orchestrator
nohup uvicorn app.main:app --reload --port 8000 > orchestrator.log 2>&1 &

echo "Starting Input Validation..."
cd ~/Downloads/sahaay/input_validation_security_engine
nohup uvicorn app:app --reload --port 8001 > input_validation.log 2>&1 &

echo "Starting AI Guidance..."
cd ~/Downloads/sahaay/ai_guidance_engine
nohup uvicorn app:app --reload --port 8002 > ai_guidance.log 2>&1 &

echo "Starting Trust Governance..."
cd ~/Downloads/sahaay/trust_governance_engine
nohup uvicorn app:app --reload --port 8003 > trust.log 2>&1 &

echo "Starting Official Service Registry..."
cd ~/Downloads/sahaay/official_service_registry
nohup uvicorn app:app --reload --port 8004 > registry.log 2>&1 &

echo "Starting Risk Engine..."
cd ~/Downloads/sahaay/risk_engine
nohup uvicorn app:app --reload --port 8005 > risk.log 2>&1 &

echo "Starting Intent Service..."
cd ~/Downloads/sahaay/intent_service
nohup uvicorn app:app --reload --port 8006 > intent.log 2>&1 &

echo "Starting Frontend..."
cd ~/Downloads/sahaay/multilingual_guidance_ui
nohup python3 -m http.server 8080 > frontend.log 2>&1 &

echo ""
echo "======================================="
echo "All services started!"
echo "Frontend: http://127.0.0.1:8080"
echo "System Orchestrator: http://127.0.0.1:8000/docs"
echo "Input Validation: http://127.0.0.1:8001/docs"
echo "AI Guidance: http://127.0.0.1:8002/docs"
echo "======================================="