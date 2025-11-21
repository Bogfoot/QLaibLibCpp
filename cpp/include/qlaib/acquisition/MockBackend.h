#pragma once

#include "qlaib/acquisition/IBackend.h"
#include <fstream>
#include <random>

namespace qlaib::acquisition {

// Mock backend: generates synthetic singles/coincidences for UI/dev work.
class MockBackend : public IBackend {
public:
  bool start(const BackendConfig &config) override;
  void stop() override;
  std::optional<data::SampleBatch> nextBatch() override;

private:
  std::mt19937 rng_{std::random_device{}()};
  std::chrono::steady_clock::time_point startTime_;
  double exposure_{1.0};
  bool running_{false};
};

} // namespace qlaib::acquisition
