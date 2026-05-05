FROM python:3.12-slim

WORKDIR /app

# DejaVu fonts satisfy the Linux candidate in load_font()
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

COPY . .

RUN mkdir -p tmp

EXPOSE 5000

ENV PYTHONUNBUFFERED=1

CMD ["python", "backend/app.py"]
