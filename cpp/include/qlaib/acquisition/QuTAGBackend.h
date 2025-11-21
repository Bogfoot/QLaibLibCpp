#pragma once

#include "qlaib/acquisition/IBackend.h"
#include "tdcbase.h"
#include <vector>

namespace qlaib::acquisition {

// Minimal backend that initializes quTAG via libtdcbase and can write .bin captures.
class QuTAGBackend : public IBackend {
public:
  bool start(const BackendConfig &config) override;
  void stop() override;
  std::optional<data::SampleBatch> nextBatch() override;

  // Start writing timestamps to a binary file (compressed=false => FORMAT_BINARY).
  bool startRecording(const std::string &filepath, bool compressed = false);
  void stopRecording();

private:
  std::vector<Int64> tsBuffer_;
  std::vector<Uint8> chBuffer_;
  bool connected_{false};
  bool recording_{false};
  double exposureMs_{1000.0};
  long long coincWindowPs_{200000};
  int bufferSize_{200000};
};

} // namespace qlaib::acquisition
