#include "qlaib/ui/MainWindow.h"
#include <QApplication>
#include <QByteArray>
#include <QCommandLineParser>
#include <QProcessEnvironment>
#include <cstdlib>
#include <iostream>

int main(int argc, char **argv) {
  // Allow headless runs without X/Wayland: set QLAIB_HEADLESS=1 or unset DISPLAY.
  auto env = QProcessEnvironment::systemEnvironment();
  if (env.contains("QLAIB_HEADLESS") || (!env.contains("DISPLAY") && !env.contains("WAYLAND_DISPLAY"))) {
    qputenv("QT_QPA_PLATFORM", QByteArray("offscreen"));
  }
  std::cerr << "[qlaib_gui] Starting QApplication\n";
  QApplication app(argc, argv);

   // CLI options for backend selection
  QCommandLineParser parser;
  parser.setApplicationDescription("QLaib C++ Live GUI");
  parser.addHelpOption();
  QCommandLineOption modeOpt({"m", "mode"}, "Backend mode: live|replay|mock (default: live)", "mode", "live");
  QCommandLineOption replayOpt({"r", "replay-bin"}, "Path to BIN file for replay mode", "file");
  parser.addOption(modeOpt);
  parser.addOption(replayOpt);
  parser.process(app);

  std::cerr << "[qlaib_gui] Creating MainWindow\n";
  qlaib::ui::MainWindow w;

  // convey options to MainWindow via getters
  w.setMode(parser.value(modeOpt));
  if (parser.isSet(replayOpt))
    w.setReplayFile(parser.value(replayOpt));

  std::cerr << "[qlaib_gui] Showing window\n";
  w.show();
  std::cerr << "[qlaib_gui] Starting backend\n";
  w.start();
  auto rc = app.exec();
  std::cerr << "[qlaib_gui] Exit code " << rc << "\n";
  return rc;
}
