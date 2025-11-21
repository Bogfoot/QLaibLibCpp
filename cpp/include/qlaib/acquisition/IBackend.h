#pragma once

#include "qlaib/data/SampleBatch.h"
#include <optional>
#include <string>

namespace qlaib::acquisition {

struct BackendConfig {
  double exposureSeconds{1.0};
  bool useMock{true};
  std::string replayFile;
  long long coincidenceWindowPs{200000}; // 200 ps default
  int timestampBufferSize{200000};       // for live quTAG streaming
};

class IBackend {
public:
  virtual ~IBackend() = default;
  virtual bool start(const BackendConfig &config) = 0;
  virtual void stop() = 0;
  virtual std::optional<data::SampleBatch> nextBatch() = 0;
};

} // namespace qlaib::acquisition
