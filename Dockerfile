# Dockerfile (server)
FROM python:3.11-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive
ENV ACCEPT_EULA=Y

# unixODBC + Microsoft repo (bookworm) + ODBC 17 (no apt-key)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl gnupg2 ca-certificates unixodbc unixodbc-dev \
  && mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
     | gpg --dearmor -o /etc/apt/keyrings/microsoft.msm.gpg \
  && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.msm.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
     > /etc/apt/sources.list.d/mssql-release.list \
  && apt-get update \
  && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# bring in the app code (server.py must export `app`)
COPY . /app

# HF Spaces expects port 7860
ENV PORT=7860
EXPOSE 7860

# Run Flask app in server.py via Gunicorn

CMD ["gunicorn","--workers","2","--threads","4","--timeout","120","-b","0.0.0.0:7860","app:app"]

