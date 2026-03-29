# Base image for Python 3.11 (Dev Container optimized)
FROM mcr.microsoft.com/devcontainers/python:3.11

# Install essential system tools
# Including 'sudo' allows for easier package management inside the container
RUN apt-get update && apt-get install -y \
    curl \
    git \
    sudo \
    gh \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) and Claude Code
# Combined into a single RUN command to minimize image layers
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force

# Install Python libraries
# Includes pandas for data processing and yfinance for financial data acquisition
RUN pip install --no-cache-dir \
    requests \
    beautifulsoup4 \
    tenacity \
    pandas \
    yfinance