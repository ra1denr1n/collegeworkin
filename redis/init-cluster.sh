#!/bin/sh
set -e

NODES="172.30.0.11:6379 172.30.0.12:6379 172.30.0.13:6379 172.30.0.14:6379 172.30.0.15:6379 172.30.0.16:6379"

echo "Жду, пока все узлы Redis запустятся..."
for n in $NODES; do
  host=${n%:*}
  until redis-cli -h "$host" ping >/dev/null 2>&1; do sleep 1; done
done

if redis-cli -h 172.30.0.11 cluster info | grep -q "cluster_state:ok"; then
  echo "Кластер уже создан — ничего не делаю."
  exit 0
fi

echo "Создаю кластер..."
# --cluster-replicas 1 : у каждого мастера по одной реплике
redis-cli --cluster create $NODES --cluster-replicas 1 --cluster-yes
redis-cli -h 172.30.0.11 cluster nodes
