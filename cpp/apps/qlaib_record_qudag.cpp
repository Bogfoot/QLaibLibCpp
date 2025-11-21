#include "qlaib/acquisition/QuTAGBackend.h"
#include <chrono>
#include <iostream>
#include <thread>

int main(int argc, char **argv) {
#ifndef QQL_ENABLE_QUTAG
  std::cerr << "Build with -DQQL_ENABLE_QUTAG=ON to use the real device.\n";
  return 1;
#else
  if (argc < 2) {
    std::cerr << "Usage: qlaib_record_qudag <output.bin> [exposure_ms]\n";
    return 1;
  }

  std::string outFile = argv[1];
  double exposureMs = 1000.0;
  if (argc >= 3) {
    exposureMs = std::stod(argv[2]);
  }

  qlaib::acquisition::QuTAGBackend backend;
  qlaib::acquisition::BackendConfig cfg;
  cfg.exposureSeconds = exposureMs / 1000.0;
  cfg.useMock = false;

  if (!backend.start(cfg)) {
    std::cerr << "Failed to init quTAG. Is the device connected and libtdcbase "
                 "in link path?\n";
    return 1;
  }

  if (!backend.startRecording(outFile, /*compressed=*/false)) {
    std::cerr << "Could not start recording to " << outFile << "\n";
    backend.stop();
    return 1;
  }

  std::cout << "Recording to " << outFile
            << " ... press Ctrl+C to stop (writing stops on exit).\n";

  // Sleep until interrupted; stopRecording will be called in backend.stop().
  while (true) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  backend.stop();
  return 0;
#endif
}
