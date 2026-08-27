# Open-PC: AI-Controlled Linux Desktop
# A standalone sandbox for AI desktop automation
#
# GPU support (opt-in):
#   Set ENABLE_GPU=true to install NVIDIA CUDA + PyTorch inside the image.
#   Runtime also requires the NVIDIA Container Toolkit on the host.
#
#   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
#
#   Without GPU (default):
#   docker compose up -d --build

ARG ENABLE_GPU=false

FROM ubuntu:24.04

ARG ENABLE_GPU

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1
ENV VNC_PORT=5901
ENV WEBSOCKET_PORT=6080
ENV AGENT_PORT=8080
ENV VNC_RESOLUTION=1920x1080
ENV VNC_COL_DEPTH=24
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Install base packages
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    sudo \
    git \
    vim \
    nano \
    htop \
    net-tools \
    iputils-ping \
    python3 \
    python3-pip \
    python3-dev \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    nodejs \
    npm \
    build-essential \
    dos2unix \
    locales \
    xdotool \
    wmctrl \
    scrot \
    imagemagick \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    && locale-gen en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install XFCE desktop environment (lightweight)
RUN apt-get update && apt-get install -y \
    xfce4 \
    xfce4-terminal \
    xfce4-screenshooter \
    xfce4-taskmanager \
    xfce4-clipman-plugin \
    thunar \
    xfce4-settings \
    xfconf \
    dbus-x11 \
    x11-xserver-utils \
    x11-apps \
    x11-utils \
    libx11-dev \
    libxext-dev \
    libxrender-dev \
    libxinerama-dev \
    libxi-dev \
    libxrandr-dev \
    libxcursor-dev \
    libxtst-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install VNC server and noVNC
RUN apt-get update && apt-get install -y \
    tigervnc-standalone-server \
    tigervnc-common \
    && git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify.git /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and dependencies (Ubuntu 24.04 uses t64 suffix for some packages)
RUN apt-get update && apt-get install -y \
    gnupg \
    fonts-liberation \
    libasound2t64 \
    libatk-bridge2.0-0t64 \
    libatk1.0-0t64 \
    libatspi2.0-0t64 \
    libcups2t64 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0t64 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python automation packages (Ubuntu 24.04 requires --break-system-packages for pip)
RUN pip3 install --no-cache-dir --break-system-packages \
    websockets==12.0 \
    aiohttp==3.9.1 \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    pyautogui==0.9.54 \
    Pillow>=10.0.0 \
    mss==9.0.1 \
    python-xlib==0.33 \
    python-dotenv==1.0.0 \
    pydantic==2.5.0 \
    opencv-python-headless==4.9.0.80 \
    numpy==1.26.0 \
    pytesseract==0.3.10

# ── GPU / CUDA layer (opt-in) ─────────────────────────────────────
# Only installed when ENABLE_GPU=true. Adds NVIDIA CUDA runtime,
# cuDNN, PyTorch (CUDA), and common ML libs so the container can
# run GPU-accelerated workloads (inference, training, Ollama, etc.).
#
# Build with: --build-arg ENABLE_GPU=true
# Runtime:    needs NVIDIA Container Toolkit + docker-compose.gpu.yml
RUN if [ "$ENABLE_GPU" = "true" ]; then \
        curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/31986713.keylist \
            | gpg --dearmor -o /usr/share/keyrings/nvidia-cuda.gpg \
        && echo "deb [signed-by=/usr/share/keyrings/nvidia-cuda.gpg] https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64 /" \
            > /etc/apt/sources.list.d/nvidia-cuda.list \
        && apt-get update \
        && apt-get install -y --no-install-recommends \
            cuda-cudart-12-6 \
            cuda-libraries-12-6 \
            cuda-nvcc-12-6 \
            libcublas-12-6 \
            libcudnn9-cuda-12 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* \
        && pip3 install --no-cache-dir --break-system-packages \
            torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126 \
        && pip3 install --no-cache-dir --break-system-packages \
            transformers>=4.40.0 \
            accelerate>=0.30.0 \
            sentencepiece \
            safetensors \
            huggingface_hub \
        ; fi

# Set GPU environment variables (harmless when no GPU; used by NVIDIA runtime)
ENV NVIDIA_VISIBLE_DEVICES=${ENABLE_GPU:+all}
ENV NVIDIA_DRIVER_CAPABILITIES=${ENABLE_GPU:+compute,utility}
ENV PATH=${ENABLE_GPU:+/usr/local/cuda-12.6.3/bin:}${PATH}
ENV LD_LIBRARY_PATH=${ENABLE_GPU:+/usr/local/cuda-12.6.3/lib64:}${LD_LIBRARY_PATH}

# Create desktop user
RUN useradd -m -s /bin/bash desktop && \
    echo "desktop:desktop" | chpasswd && \
    usermod -aG sudo,audio,video desktop

# Create necessary directories
RUN mkdir -p /home/desktop/.vnc \
    && mkdir -p /home/desktop/.config \
    && mkdir -p /home/desktop/Desktop \
    && mkdir -p /opt/openpc \
    && mkdir -p /var/log/openpc \
    && chown -R desktop:desktop /home/desktop

# Copy application files
COPY agent_server.py /opt/openpc/agent_server.py
COPY desktop_manager.py /opt/openpc/desktop_manager.py
COPY sanitization.py /opt/openpc/sanitization.py
COPY startup.sh /opt/openpc/startup.sh
COPY xstartup /opt/openpc/xstartup
COPY health_check.py /opt/openpc/health_check.py

# Set permissions
RUN chmod +x /opt/openpc/startup.sh \
    && chmod +x /opt/openpc/xstartup \
    && chmod 755 /opt/openpc/*.py

# Copy to VNC directory
RUN cp /opt/openpc/xstartup /home/desktop/.vnc/xstartup \
    && chmod 755 /home/desktop/.vnc/xstartup \
    && chown desktop:desktop /home/desktop/.vnc/xstartup

# Expose ports
# 5901 - VNC
# 6080 - noVNC (web)
# 8080 - AI Agent WebSocket/REST API
EXPOSE 5901 6080 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 /opt/openpc/health_check.py || exit 1

# Set working directory
WORKDIR /opt/openpc

# Start services
ENTRYPOINT ["/bin/bash", "/opt/openpc/startup.sh"]