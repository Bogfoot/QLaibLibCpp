#include "qlaib/acquisition/BinReplayBackend.h"
#include "ReadCSV.h" // from coincfinder
#include "Coincidences.h"
#include "Singles.h"
#include <cmath>

namespace qlaib::acquisition {

bool BinReplayBackend::start(const BackendConfig &config) {
  if (config.replayFile.empty())
    return false;
  double durationSec = 0.0;
  singles_ = readBINtoSingles(config.replayFile, durationSec);
  if (singles_.empty())
    return false;
  // determine earliest and latest seconds
  long long earliest = std::numeric_limits<long long>::max();
  long long latest = std::numeric_limits<long long>::min();
  for (auto &[ch, s] : singles_) {
    if (s.eventsPerSecond.empty())
      continue;
    earliest = std::min(earliest, s.baseSecond);
    latest = std::max(
        latest, s.baseSecond + static_cast<long long>(s.eventsPerSecond.size()) - 1);
  }
  currentSecond_ = earliest;
  lastSecond_ = latest;
  coincWindowPs_ = config.coincidenceWindowPs;
  return true;
}

void BinReplayBackend::stop() {
  singles_.clear();
}

std::optional<data::SampleBatch> BinReplayBackend::nextBatch() {
  if (singles_.empty() || currentSecond_ > lastSecond_)
    return std::nullopt;

  data::SampleBatch batch;
  batch.timestamp = std::chrono::steady_clock::now();

  // Build singles vector up to max channel seen
  int maxCh = 0;
  for (auto &[ch, _] : singles_)
    maxCh = std::max(maxCh, ch);
  batch.singles.assign(static_cast<size_t>(maxCh), 0);
  batch.timestamps_ps.resize(static_cast<size_t>(maxCh));

  for (auto &[ch, s] : singles_) {
    const auto &bucket = eventsForSecond(s, currentSecond_);
    batch.singles[ch - 1] = static_cast<std::uint64_t>(bucket.size());
    batch.timestamps_ps[ch - 1] = bucket; // already in ps relative to first ts
  }

  // Default pairs as in README (H/V/D/A): (1,5), (2,6), (3,7), (4,8)
  const std::pair<int, int> pairs[] = {{1,5},{2,6},{3,7},{4,8},{1,6},{2,5},{3,8},{4,7}};

  std::vector<std::pair<float,int>> scratch;
  for (auto [a,b] : pairs) {
    if (!singles_.count(a) || !singles_.count(b))
      continue;
    const auto &sa = eventsForSecond(singles_.at(a), currentSecond_);
    const auto &sb = eventsForSecond(singles_.at(b), currentSecond_);
    // include first event of next second for cross-boundary
    std::vector<long long> mergedScratch;
    const auto &sbNext = eventsForSecond(singles_.at(b), currentSecond_ + 1);
    std::span<const long long> sBSpan =
        appendNextFirstEvent(sb, sbNext, mergedScratch);
    std::span<const long long> sASpan(sa.data(), sa.size());
    int coincidences = countCoincidencesWithDelay(sASpan, sBSpan, coincWindowPs_, 0);
    batch.coincidences.push_back({std::to_string(a) + "-" + std::to_string(b),
                                  static_cast<std::uint64_t>(coincidences)});
  }

  // Simple metrics (placeholder): visibility approx from first pair
  if (!batch.coincidences.empty()) {
    batch.metrics["visibility"] =
        batch.coincidences.front().counts /
        std::max<double>(1.0, batch.coincidences.front().counts + 500.0);
  }

  ++currentSecond_;
  return batch;
}

} // namespace qlaib::acquisition
