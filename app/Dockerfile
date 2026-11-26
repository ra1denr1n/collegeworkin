FROM python:3.14.0

# Не создавать .pyc и сразу выводить логи
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала зависимости: этот слой кэшируется и не пересобирается при правке кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Один процесс на контейнер: масштабируемся количеством контейнеров.
# --no-access-log: под нагрузкой лог каждого запроса заметно замедляет работу.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
