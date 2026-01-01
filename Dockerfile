FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir psycopg2-binary

# Copy application files
COPY server.py .
COPY index.html .
COPY config.json .

EXPOSE 3000

CMD ["python", "server.py"]
