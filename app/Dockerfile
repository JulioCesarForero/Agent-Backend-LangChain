# Use official lightweight Python 3.11-slim image
FROM python:3.11-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Forzar UTF-8 en Python y en el sistema
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Create and set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install requirements
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install requirements con caché persistente (opcional)
# RUN --mount=type=cache,target=/root/.cache/pip \
#     pip install --upgrade pip && \
#     pip install -r requirements.txt



# Copy all the code
COPY . .

# Expose the port where FastAPI will run
EXPOSE 8000

# Default command con timeouts extendidos para permitir respuestas largas del RAG
# --timeout-keep-alive: tiempo para mantener conexiones keep-alive (5 minutos)
# --timeout-graceful-shutdown: tiempo para apagar graciosamente (30 segundos)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
