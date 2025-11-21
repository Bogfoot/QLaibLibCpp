#pragma once

#include "qlaib/acquisition/IBackend.h"
#include <map>
#include "Singles.h"

namespace qlaib::acquisition {

// Replays a saved BIN file (quTAG timestamps) using coincfinder utilities.
class BinReplayBackend : public IBackend {
public:
  bool start(const BackendConfig &config) override;
  void stop() override;
  std::optional<data::SampleBatch> nextBatch() override;

private:
  std::map<int, Singles> singles_;
  long long currentSecond_{0};
  long long lastSecond_{-1};
  long long coincWindowPs_{200000};
};

} // namespace qlaib::acquisition
