"""Regression checks for the result assembly in benchmark_serving.py.

Run with: pytest test_benchmark_serving.py
"""

import argparse
import asyncio

import benchmark_serving as bs


def _make_args():
  return argparse.Namespace(
      stream_request=True,
      machine_cost=None,
      scrape_server_metrics=False,
      save_json_results=True,
      num_prompts=3,
      backend="vllm",
      pm_namespace="",
      pm_job="",
  )


def _capture_result(monkeypatch):
  """Runs print_and_save_result once and returns the assembled result dict."""
  captured = {}

  def fake_save(args, benchmark_result, server_metrics, model, errors):
    captured.update(benchmark_result)

  monkeypatch.setattr(bs, "save_json_results", fake_save)

  async def run():
    # print_and_save_result reads the QPS counter, which needs _end_time set.
    bs.AsyncRequestCounter._instance = None
    counter = await bs.AsyncRequestCounter(target_requests=3)
    for _ in range(3):
      await counter.increment()

    # (prompt_len, output_len, latency_ms) per request.
    request_latencies = [(10, 5, 100.0), (20, 10, 200.0), (30, 15, 300.0)]
    await bs.print_and_save_result(
        args=_make_args(),
        benchmark_duration_sec=10.0,
        total_requests=3,
        model="test-model",
        request_latencies=request_latencies,
        ttfts=[10.0, 20.0, 30.0],
        itls=[1.0, 2.0, 3.0],
        tpots=[5.0, 10.0, 15.0],
        errors=bs.init_errors_map(),
    )

  asyncio.run(run())
  return captured


def test_tpot_stats_reach_the_saved_result(monkeypatch):
  """TPOT was printed but dropped before the JSON save. Guard against that."""
  result = _capture_result(monkeypatch)
  assert result["avg_TPOT_ms"] == 10.0
  assert result["median_TPOT_ms"] == 10.0
  assert result["min_TPOT_ms"] == 5.0
  assert result["max_TPOT_ms"] == 15.0


def test_streaming_latency_metrics_are_all_present(monkeypatch):
  result = _capture_result(monkeypatch)
  for name in ("TTFT_ms", "ITL_ms", "TPOT_ms"):
    for stat in ("avg", "median", "sd", "min", "max", "p90", "p99"):
      assert f"{stat}_{name}" in result, f"missing {stat}_{name}"


def test_throughput_totals(monkeypatch):
  result = _capture_result(monkeypatch)
  assert result["total_input_tokens"] == 60
  assert result["total_output_token"] == 30
  assert result["throughput"] == 3.0  # 30 output tokens over 10 seconds
