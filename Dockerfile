FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for MewAct + X11
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-dev \
    git \
    xvfb \
    x11-utils \
    scrot \
    fluxbox \
    net-tools \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip3 install mcp pyautogui mss opencv-python-headless numpy pillow colorama

# Expose display for screenshots
ENV DISPLAY=:99

# Start Xvfb and MewAct
CMD Xvfb :99 -screen 0 1920x1080x24 & fluxbox & python3 mewact_mcp.py
