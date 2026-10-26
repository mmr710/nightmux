# The box a sandboxed agent runs in: `docker build -t nightmux-agent -f docker/agent.Dockerfile docker`
# Then `!sandbox on` in a topic (or "sandbox": {"all": true} in the config) and !restore.
FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ripgrep python3 python3-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli \
    && mkdir -p /home/agent && chmod 777 /home/agent
ENV HOME=/home/agent
