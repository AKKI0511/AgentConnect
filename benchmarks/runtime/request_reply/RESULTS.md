# Request/reply exchange results

## Local verification: 2026-10-21

Windows x64, CPython 3.12.8, Docker Redis 8.2.10 on localhost:6380 with AOF
and restart support. All 12 one-Runtime cells passed in 94.66 seconds:
3,600/3,600 exchanges, zero errors and timeouts. This includes memory and
Redis over embedded and HTTP access at 1, 8 and 32 pairs. N=1 used 100
trips per pair; N=8/32 used 20. Warmup and fixed gates follow the README.

Completed-only HTTP p95 at N=1/8/32 was 6.1/47.6/716.9 ms for memory and
42.5/283.0/3898.8 ms for Redis. Redis N=32 remains measured, not a 100%
completion gate. These local observations do not establish a latency SLA.
Two-process replicas were not measured in this run. Raw JSON and JUnit remain
in the ignored local results directory.


## Earlier local matrix

Windows 11, CPython 3.12.8, 13th Gen Intel Core i7-13700H (20 logical
processors). Packages: pytest-benchmark 5.3.0, redis-py 5.3.1, hiredis 3.4.1,
httpx 0.28.1, pydantic 2.13.5. Tree was dirty on `717fc31`. This is one desktop, not a latency
SLA and not GitHub runner hardware.


Each caller/worker pair keeps one request in flight through `send`, `lease`,
`reply` and `get_result`. This recording used 20 trips per pair, one untimed
warmup each, and a 15-second trip timeout. Percentiles use completed trips.
Later default runs use 100 trips at concurrency 1 and omit p99 below 100
completed samples. Two-process rows split send/collection and lease/reply
across processes sharing Redis; they do not establish replica safety.

p50 / p95 / p99 are milliseconds; `ok` is completed / attempted.

| Store | Access | Replicas | N | ok | p50 | p95 | p99 | round-trips/s | err | timeout |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memory | embedded | 1 | 1 | 20/20 | 0.8 | 0.9 | 0.9 | 1359 | 0 | 0 |
| memory | embedded | 1 | 8 | 160/160 | 0.7 | 0.9 | 1.3 | 1396 | 0 | 0 |
| memory | embedded | 1 | 32 | 640/640 | 0.7 | 1.3 | 2.8 | 1222 | 0 | 0 |
| memory | HTTP | 1 | 1 | 20/20 | 4.7 | 5.2 | 5.2 | 210 | 0 | 0 |
| memory | HTTP | 1 | 8 | 160/160 | 38.3 | 61.3 | 73.7 | 195 | 0 | 0 |
| memory | HTTP | 1 | 32 | 640/640 | 278.1 | 703.1 | 926.5 | 97 | 0 | 0 |
| redis | embedded | 1 | 1 | 20/20 | 38.4 | 59.2 | 62.8 | 25 | 0 | 0 |
| redis | embedded | 1 | 8 | 160/160 | 117.0 | 230.8 | 309.0 | 58 | 0 | 0 |
| redis | embedded | 1 | 32 | 640/640 | 1053 | 3237 | 4345 | 23 | 0 | 0 |
| redis | HTTP | 1 | 1 | 20/20 | 63.9 | 85.7 | 86.6 | 15 | 0 | 0 |
| redis | HTTP | 1 | 8 | 160/160 | 150.2 | 288.3 | 455.2 | 44 | 0 | 0 |
| redis | HTTP | 1 | 32 | 640/640 | 1246 | 3657 | 4954 | 19 | 0 | 0 |
| redis | HTTP | 2 | 8 | 160/160 | 128.0 | 238.0 | 296.3 | 55 | 0 | 0 |
| redis | HTTP | 2 | 32 | 640/640 | 685.8 | 4099 | 6357 | 24 | 0 | 0 |


On this host memory/embedded throughput held through 32 pairs. HTTP memory
and Redis reached their highest throughput at 8 pairs. Redis concurrency 32
is measured only; the default gate requires complete, error-free work at
concurrency 1/8 and memory 32. The 5-second p95 bound detects stalls; it is
not a latency SLA. See [README.md](README.md) for reproduction.
