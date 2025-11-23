#pragma once

#include "qlaib/data/SampleBatch.h"
#include <optional>
#include <string>

namespace qlaib::acquisition {

/**
 * @brief Immutable configuration shared by all acquisition backends.
 *
 * The GUI populates this from CLI flags / UI controls and passes it once
 * into IBackend::start(). Backends should treat the struct as read‑only
 * after that point.
 */
struct BackendConfig {
  /// Integration time used by backends that collect a batch per exposure.
  double exposureSeconds{1.0};
  /// Whether the frontend explicitly requested the mock backend.
  bool useMock{true};
  /// BIN file path used when replaying recorded data.
  std::string replayFile;
  /// Coincidence window in picoseconds for coincidence counting.
  long long coincidenceWindowPs{200000}; // 200 ps default
  /// Maximum timestamp buffer length for streaming (live quTAG).
  int timestampBufferSize{50000000}; // default 50M to avoid saturation
};

class IBackend {
public:
  virtual ~IBackend() = default;

  /**
   * @brief Initialise the backend and prepare to emit batches.
   * @param config Immutable acquisition parameters.
   * @return true on success; false if initialisation failed.
   */
  virtual bool start(const BackendConfig &config) = 0;

  /// Stop acquisition and release any hardware or file handles.
  virtual void stop() = 0;

  /**
   * @brief Retrieve the next batch of samples, if available.
   * @return A SampleBatch when data is ready; std::nullopt otherwise.
   */
  virtual std::optional<data::SampleBatch> nextBatch() = 0;
};

} // namespace qlaib::acquisition
