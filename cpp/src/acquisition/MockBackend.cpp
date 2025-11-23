#include "qlaib/acquisition/MockBackend.h"
#include <chrono>

namespace qlaib::acquisition {

bool MockBackend::start(const BackendConfig &config) {
  exposure_ = config.exposureSeconds;
  startTime_ = std::chrono::steady_clock::now();
  running_ = true;
  return true;
}

void MockBackend::stop() { running_ = false; }

std::optional<data::SampleBatch> MockBackend::nextBatch() {
  if (!running_)
    return std::nullopt;

  std::uniform_int_distribution<std::uint64_t> singlesDist(5'000, 12'000);
  std::normal_distribution<double> metricNoise(0.0, 0.01);

  data::SampleBatch batch;
  batch.timestamp = std::chrono::steady_clock::now();
  // Simulate 8 channels to mirror quTAG defaults
  batch.singles.resize(8);
  for (auto &s : batch.singles) {
    s = singlesDist(rng_);
  }

  // synthetic timestamps per channel within exposure window
  const long long exposurePs =
      static_cast<long long>(exposure_ * 1'000'000'000'000LL);
  batch.timestamps_ps.resize(batch.singles.size());
  std::uniform_int_distribution<long long> tsDist(0, exposurePs);
  for (size_t ch = 0; ch < batch.singles.size(); ++ch) {
    batch.timestamps_ps[ch].reserve(batch.singles[ch]);
    for (std::uint64_t i = 0; i < batch.singles[ch]; ++i) {
      batch.timestamps_ps[ch].push_back(tsDist(rng_));
    }
    std::sort(batch.timestamps_ps[ch].begin(), batch.timestamps_ps[ch].end());
  }

  // Per-channel singles already reflect the current exposure only; keep as-is.

  batch.coincidences = {
      {"HV", static_cast<std::uint64_t>(batch.singles[0] * 0.15)},
      {"DA", static_cast<std::uint64_t>(batch.singles[1] * 0.12)},
      {"CHSH", static_cast<std::uint64_t>(batch.singles[2] * 0.09)}};

  batch.metrics["qber"] = 0.03 + metricNoise(rng_);
  batch.metrics["visibility"] = 0.92 + metricNoise(rng_);
  batch.metrics["s_parameter"] = 2.72 + metricNoise(rng_);

  return batch;
}

} // namespace qlaib::acquisition
