#!/bin/sh
set -e

# Первый запуск (каталог данных пуст) — копируем базу с primary
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "[replica] жду primary..."
  until pg_isready -h "$PRIMARY_HOST" -p 5432 -U "$REPLICATION_USER" >/dev/null 2>&1; do
    sleep 2
  done
  echo "[replica] pg_basebackup..."
  rm -rf "${PGDATA:?}"/*
  PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
    -h "$PRIMARY_HOST" -p 5432 -U "$REPLICATION_USER" \
    -D "$PGDATA" -Fp -Xs -P -R
  chmod 700 "$PGDATA"
fi

echo "[replica] запуск в режиме hot standby"
exec postgres "$@"
