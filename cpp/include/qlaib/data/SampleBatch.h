#pragma once

#include <chrono>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace qlaib::data {

struct Coincidence {
  std::string label;
  std::uint64_t counts;
};

struct SampleBatch {
  std::chrono::steady_clock::time_point timestamp;
  std::vector<std::uint64_t> singles;               // per-channel counts
  std::vector<Coincidence> coincidences;            // labeled coincidences
  std::unordered_map<std::string, double> metrics;  // QBER, visibility, etc.
  std::vector<std::vector<long long>> timestamps_ps; // raw timestamps per channel
};

} // namespace qlaib::data
