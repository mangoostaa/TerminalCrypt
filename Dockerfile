# TerminalCrypt — terminal crypto dashboard
# Pure-Python image (the Rust/Cython indicator backends are optional; the app
# falls back to pure Python automatically), so this stays small and portable.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="TerminalCrypt" \
      org.opencontainers.image.description="Real-time terminal crypto dashboard with WebSocket feeds, indicators, radar, paper trading and derivatives data." \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    TERM=xterm-256color

WORKDIR /app

# Install runtime deps first for better layer caching.
RUN pip install --no-cache-dir websocket-client requests rich

COPY . /app
RUN pip install --no-cache-dir . || pip install --no-cache-dir -e .

# A colourful TUI needs a real terminal: run with `docker run -it`.
ENTRYPOINT ["terminalcrypt"]
CMD []
