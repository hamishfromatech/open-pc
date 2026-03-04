# Open-PC MCP Server
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY openpc_mcp.py .

# Expose MCP HTTP port
EXPOSE 8000

# Run MCP server
CMD ["python", "openpc_mcp.py"]