#!/bin/bash
# Open-PC Startup Script
# Initializes VNC, Desktop, and Agent Server

set -e

echo "=========================================="
echo "  Open-PC - AI Desktop Environment"
echo "=========================================="

# Configuration
DISPLAY_NUM=1
VNC_PORT=${VNC_PORT:-5901}
WEBSOCKET_PORT=${WEBSOCKET_PORT:-6080}
AGENT_PORT=${AGENT_PORT:-8080}
VNC_RESOLUTION=${VNC_RESOLUTION:-1920x1080}
VNC_COL_DEPTH=${VNC_COL_DEPTH:-24}
VNC_PASSWORD=${VNC_PASSWORD:-openpc}

export DISPLAY=:${DISPLAY_NUM}
export AGENT_HOST=${AGENT_HOST:-0.0.0.0}
export AGENT_PORT=${AGENT_PORT}

# ============== VNC Setup ==============
echo "[1/5] Setting up VNC..."

# Clean up existing processes
pkill -f "X.*vnc.*:${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "vncserver" 2>/dev/null || true
rm -f /tmp/.X${DISPLAY_NUM}-lock 2>/dev/null || true
rm -f /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true
rm -f /home/desktop/.vnc/*.pid 2>/dev/null || true
rm -f /home/desktop/.vnc/*.log 2>/dev/null || true

# Ensure VNC directory exists
mkdir -p /home/desktop/.vnc
chown -R desktop:desktop /home/desktop/.vnc

# Copy xstartup
cp /opt/openpc/xstartup /home/desktop/.vnc/xstartup
chmod 755 /home/desktop/.vnc/xstartup
chown desktop:desktop /home/desktop/.vnc/xstartup

# Set VNC password
if [ -n "$VNC_PASSWORD" ]; then
    echo "$VNC_PASSWORD" | su - desktop -c "vncpasswd -f > /home/desktop/.vnc/passwd"
    chmod 600 /home/desktop/.vnc/passwd
    chown desktop:desktop /home/desktop/.vnc/passwd
fi

# Start VNC server
echo "Starting VNC server on :${DISPLAY_NUM}..."
su - desktop -c "vncserver :${DISPLAY_NUM} -geometry ${VNC_RESOLUTION} -depth ${VNC_COL_DEPTH} -SecurityTypes VncAuth -PasswordFile /home/desktop/.vnc/passwd" 2>&1 || {
    echo "VNC server failed to start, retrying..."
    sleep 2
    su - desktop -c "vncserver :${DISPLAY_NUM} -geometry ${VNC_RESOLUTION} -depth ${VNC_COL_DEPTH} -SecurityTypes VncAuth -PasswordFile /home/desktop/.vnc/passwd"
}

# ============== Wait for X11 ==============
echo "[2/5] Waiting for X11 display..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset q" >/dev/null 2>&1; then
        echo "X11 display is ready!"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "Waiting for X11... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 1
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "Warning: X11 display may not be fully ready"
fi

# Copy Xauthority
if [ -f /home/desktop/.Xauthority ]; then
    cp /home/desktop/.Xauthority /root/.Xauthority 2>/dev/null || true
fi

# ============== Screen Power Management ==============
echo "[3/5] Configuring screen settings..."
su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset s off" 2>/dev/null || true
su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset s noblank" 2>/dev/null || true
su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset -dpms" 2>/dev/null || true
su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset dpms 0 0 0" 2>/dev/null || true

# ============== noVNC Setup ==============
echo "[4/5] Starting noVNC..."
cd /opt/novnc
./utils/novnc_proxy --vnc localhost:${VNC_PORT} --listen ${WEBSOCKET_PORT} &
sleep 2

# ============== Start Agent Server ==============
echo "[5/5] Starting Open-PC Agent Server..."

# Set environment for agent
export PYAUTOGUI_FAILSAFE=0
export XAUTHORITY=/home/desktop/.Xauthority

# Create log directory
mkdir -p /var/log/openpc
chmod 777 /var/log/openpc

# Start the agent server
cd /opt/openpc
python3 agent_server.py 2>&1 | tee /var/log/openpc/agent.log &
AGENT_PID=$!

echo ""
echo "=========================================="
echo "  Open-PC Started Successfully!"
echo "=========================================="
echo "  VNC Port:        ${VNC_PORT}"
echo "  noVNC (Web):     http://localhost:${WEBSOCKET_PORT}"
echo "  Agent API:       http://localhost:${AGENT_PORT}"
echo "  Agent WebSocket: ws://localhost:${AGENT_PORT}/ws"
echo "  VNC Password:    ${VNC_PASSWORD}"
echo "=========================================="
echo ""

# ============== Health Monitoring Loop ==============
while true; do
    # Check VNC
    if ! pgrep -f "X.*vnc.*:${DISPLAY_NUM}" > /dev/null; then
        echo "$(date) VNC server died, restarting..."
        su - desktop -c "vncserver :${DISPLAY_NUM} -geometry ${VNC_RESOLUTION} -depth ${VNC_COL_DEPTH} -SecurityTypes VncAuth -PasswordFile /home/desktop/.vnc/passwd"
        sleep 2
    fi

    # Check noVNC
    if ! pgrep -f "novnc_proxy" > /dev/null; then
        echo "$(date) noVNC died, restarting..."
        cd /opt/novnc && ./utils/novnc_proxy --vnc localhost:${VNC_PORT} --listen ${WEBSOCKET_PORT} &
    fi

    # Check Agent
    if ! pgrep -f "agent_server.py" > /dev/null; then
        echo "$(date) Agent server died, restarting..."
        cd /opt/openpc && python3 agent_server.py 2>&1 | tee -a /var/log/openpc/agent.log &
    fi

    # Keep screen alive
    su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset s off s noblank s 0 0" 2>/dev/null || true
    su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset -dpms" 2>/dev/null || true
    su - desktop -c "DISPLAY=:${DISPLAY_NUM} xset dpms force on" 2>/dev/null || true

    sleep 30
done