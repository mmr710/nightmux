# nightmux in a container: tmux, the agents, and the daemon.
#   docker run -it --name nightmux -v nightmux-home:/root -v ~/code:/code \
#     -p 127.0.0.1:9090:9090 ghcr.io/mmr710/nightmux
# First run asks the setup questions; log the agents in once with
#   docker exec -it nightmux claude      (or codex, …)
# The dashboard has no login: keep the port on 127.0.0.1 (or your tailnet).
FROM python:3.12-slim
ARG AGENTS="@anthropic-ai/claude-code @openai/codex"
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux git curl ca-certificates procps nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$AGENTS" ]; then npm install -g $AGENTS && npm cache clean --force; fi
COPY nightmux.py /app/nightmux.py
ENV NIGHTMUX_HOST=0.0.0.0 NIGHTMUX_NO_SERVICE=1 PYTHONUNBUFFERED=1
WORKDIR /code
EXPOSE 9090
ENTRYPOINT ["sh", "-c", "[ -f ~/.nightmux.json ] || python3 /app/nightmux.py --setup; exec python3 /app/nightmux.py"]
