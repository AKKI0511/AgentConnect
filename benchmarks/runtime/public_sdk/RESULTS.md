# Public SDK local verification — 2026-10-21

Windows x64, CPython 3.12.8; dedicated Docker Redis 8.2.10 on localhost:6380
with AOF and restart support. The required-Redis full suites completed before
benchmarking, so server restart tests did not overlap measured work.

All 16 cells passed: discovery/Profile/ask, specialist fanout, correlated Thread
follow-up and capacity/reconnect, each on memory/Redis and embedded/HTTP. Each
store completed 190 timed journeys with zero errors and timeouts. Sampling and
unchanged gates are defined in [README.md](README.md).

Memory maximum completed-only p95 was 3.7402 seconds; Redis maximum was 1.1878
seconds, both below the fixed 5-second stall gate. These separately scheduled
desktop runs validate the gates; they are not a controlled backend comparison.

Warmup and report/platform collection occur outside pytest timing. Pytest batch
duration differed from the reported batch wall time by 0.04–0.21 ms across the
final runs. Timed work includes join/leave and the 50 ms capacity observation in
the reconnect workload. Configured handler delay was zero; any sleep-subtracted
journey metric still includes scheduling, transport and collection costs.

These runs exercise Thread relationships and retained replies after caller reconnect; they do not measure saturation or worker restart.

No hosted performance run was performed. Raw JSON and JUnit remain in the ignored local results directory.
