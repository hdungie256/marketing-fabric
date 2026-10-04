#!/bin/sh
out=${1:-/tmp/ram_stats.tsv}
: > "$out"
docker compose -f compose/docker-compose.yml run --rm --name spike-ram -e SPIKE_ROWS fabric-jobs python -m spikes.ram &
job=$!
while kill -0 $job 2>/dev/null; do
  docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}' | sed "s/^/$(date +%s)\t/" >> "$out"
  sleep 0.5
done
wait $job
