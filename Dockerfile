FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY index.html .
COPY init.sql .
COPY templates/ templates/

# Use docker config (secrets should be passed via environment variables)
COPY config.docker.json config.json

EXPOSE 3000

CMD ["python", "server.py"]
