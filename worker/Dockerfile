# Multi-stage build: install the Alpaca CLI in a Go build stage, then copy
# just the compiled binary into the final Python image. Pinned to a
# specific release rather than @latest, since the CLI is Alpha Preview and
# flags/commands can change without notice between releases — do not swap
# this to @latest mid-build-week.
FROM golang:1.23-bookworm AS alpaca-cli
# Pinned to specific tagged release for build reproducibility
RUN go install github.com/alpacahq/cli/cmd/alpaca@v0.1.0

FROM python:3.12-slim
WORKDIR /app
COPY --from=alpaca-cli /go/bin/alpaca /usr/local/bin/alpaca
RUN alpaca version || true
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "run_loop.py"]
