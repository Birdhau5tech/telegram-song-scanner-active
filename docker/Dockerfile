FROM python:3.11-slim

# SET WORKING DIRECTORY
WORKDIR /app

# INSTALL SYSTEM DEPENDENCIES
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# COPY REQUIREMENTS
COPY requirements.txt requirements-dev.txt ./

# INSTALL PYTHON DEPENDENCIES
RUN pip install --no-cache-dir -r requirements.txt

# COPY APPLICATION
COPY . .

# CREATE DATA DIRECTORIES
RUN mkdir -p data/logs data/cache data/temp data/exports

# EXPOSE PORT
EXPOSE 5000

# SET ENVIRONMENT
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# RUN APPLICATION
CMD ["python", "-m", "src.main"]
