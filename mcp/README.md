# MCP sidecar

Wraps Alpaca's official Trading MCP Server so the worker's Execution Agent
can reach it over Railway's private network instead of the public internet.

See: https://docs.alpaca.markets (Trading MCP Server) for the upstream
server this Dockerfile should run — swap the placeholder CMD below for the
real install/run steps once confirmed against current docs.
