#!/bin/sh
out=${1:-/tmp/memory_stats.tsv}
: > "$out"
docker compose -f compose/docker-compose.yml run --rm --name memory-load -e MEMORY_ROWS fabric-jobs python -m scripts.memory_load &
job=$!
while kill -0 $job 2>/dev/null; do
  docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}' | sed "s/^/$(date +%s)\t/" >> "$out"
  sleep 0.5
done
wait $job
status=$?
awk -F'\t' '{
  split($3, a, " / "); v = a[1]; n = v + 0
  if (v ~ /GiB/) n *= 1024; else if (v ~ /MiB/) n = n; else if (v ~ /KiB/) n /= 1024; else n /= 1048576
  total[$1] += n
} END {
  for (t in total) if (total[t] > peak) peak = total[t]
  printf "peak total %.2f GiB over %d samples\n", peak / 1024, length(total)
}' "$out"
exit $status
