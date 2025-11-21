#include "qlaib/acquisition/QuTAGBackend.h"
#include "Coincidences.h"
#include "tdcbase.h"
#include <algorithm>
#include <iostream>
#include <map>

namespace qlaib::acquisition {

namespace {
constexpr int kDefaultChannelMask = 0xFF; // enable channels 1..8
} // namespace

bool QuTAGBackend::start(const BackendConfig &config) {
  // Init device (-1 => first available)
  int rc = TDC_init(-1);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_init failed: " << TDC_perror(rc) << "\n";
    connected_ = false;
    return false;
  }
  connected_ = true;

  // exposureSeconds -> ms, clamped to API range
  exposureMs_ = std::clamp(config.exposureSeconds * 1000.0, 1.0,
                           65535.0); // API: Int32 ms
  rc = TDC_setExposureTime(static_cast<Int32>(exposureMs_));
  if (rc != TDC_Ok) {
    std::cerr << "TDC_setExposureTime failed: " << TDC_perror(rc) << "\n";
  }

  // Enable first 8 channels (no dedicated start)
  rc = TDC_enableChannels(false, kDefaultChannelMask);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_enableChannels failed: " << TDC_perror(rc) << "\n";
  }

  // Timestamp buffer for streaming
  bufferSize_ = std::clamp(config.timestampBufferSize, 1000, 1'000'000);
  coincWindowPs_ = config.coincidenceWindowPs;
  rc = TDC_setTimestampBufferSize(bufferSize_);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_setTimestampBufferSize failed: " << TDC_perror(rc)
              << "\n";
  }
  tsBuffer_.resize(static_cast<size_t>(bufferSize_));
  chBuffer_.resize(static_cast<size_t>(bufferSize_));

  // Stop any ongoing file writing
  TDC_writeTimestamps(nullptr, FORMAT_NONE);
  recording_ = false;
  return true;
}

void QuTAGBackend::stop() {
  stopRecording();
  if (connected_) {
    TDC_deInit();
    connected_ = false;
  }
}

std::optional<data::SampleBatch> QuTAGBackend::nextBatch() {
  if (!connected_)
    return std::nullopt;

  Int32 valid = 0;
  if (tsBuffer_.empty())
    return std::nullopt;

  // reset=1 clears buffer after read -> events since last call
  int rc = TDC_getLastTimestamps(1, tsBuffer_.data(), chBuffer_.data(), &valid);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_getLastTimestamps failed: " << TDC_perror(rc) << "\n";
    return std::nullopt;
  }
  if (valid <= 0)
    return std::nullopt;

  // Bucket by channel (1-based external)
  std::map<int, std::vector<long long>> perChannel;
  for (int i = 0; i < valid; ++i) {
    int ch = static_cast<int>(chBuffer_[static_cast<size_t>(i)]) + 1;
    perChannel[ch].push_back(tsBuffer_[static_cast<size_t>(i)]);
  }

  data::SampleBatch batch;
  batch.timestamp = std::chrono::steady_clock::now();

  int maxCh = 0;
  for (auto &[ch, _] : perChannel)
    maxCh = std::max(maxCh, ch);
  batch.singles.assign(static_cast<size_t>(maxCh), 0);
  batch.timestamps_ps.resize(static_cast<size_t>(maxCh));
  for (auto &[ch, vec] : perChannel) {
    batch.singles[ch - 1] = static_cast<std::uint64_t>(vec.size());
    batch.timestamps_ps[ch - 1] = vec;
  }

  // Default pairs
  const std::pair<int, int> pairs[] = {{1, 5}, {2, 6}, {3, 7}, {4, 8},
                                       {1, 6}, {2, 5}, {3, 8}, {4, 7}};
  for (auto [a, b] : pairs) {
    if (!perChannel.count(a) || !perChannel.count(b))
      continue;
    std::span<const long long> sa(perChannel[a].data(), perChannel[a].size());
    std::span<const long long> sb(perChannel[b].data(), perChannel[b].size());
    int coincidences =
        countCoincidencesWithDelay(sa, sb, coincWindowPs_, 0 /*delay*/);
    batch.coincidences.push_back({std::to_string(a) + "-" + std::to_string(b),
                                  static_cast<std::uint64_t>(coincidences)});
  }

  // Quick visibility proxy
  if (!batch.coincidences.empty()) {
    batch.metrics["visibility"] =
        batch.coincidences.front().counts /
        std::max<double>(1.0, batch.coincidences.front().counts + 500.0);
  }
  return batch;
}

bool QuTAGBackend::startRecording(const std::string &filepath,
                                  bool compressed) {
  if (!connected_)
    return false;
  auto fmt = compressed ? FORMAT_COMPRESSED : FORMAT_BINARY;
  int rc = TDC_writeTimestamps(filepath.c_str(), fmt);
  recording_ = (rc == TDC_Ok);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_writeTimestamps start failed: " << TDC_perror(rc) << "\n";
  }
  return recording_;
}

void QuTAGBackend::stopRecording() {
  if (!connected_ || !recording_)
    return;
  int rc = TDC_writeTimestamps(nullptr, FORMAT_NONE);
  if (rc != TDC_Ok) {
    std::cerr << "TDC_writeTimestamps stop failed: " << TDC_perror(rc) << "\n";
  }
  recording_ = false;
}

} // namespace qlaib::acquisition
