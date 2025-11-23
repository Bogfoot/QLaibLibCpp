#include "qlaib/ui/MainWindow.h"
#include <QApplication>
#include <QByteArray>
#include <QCommandLineParser>
#include <QProcessEnvironment>
#include <cstdlib>
#include <iostream>

int main(int argc, char **argv) {
  std::cerr << "[qlaib_gui] argv[0]=" << (argv && argv[0] ? argv[0] : "<null>") << "\n";
#ifdef Q_OS_WIN
  // On Windows, force the platform to "windows" to avoid inherited offscreen values.
  const QByteArray current = qgetenv("QT_QPA_PLATFORM");
  if (!current.isEmpty())
    std::cerr << "[qlaib_gui] existing QT_QPA_PLATFORM=" << current.constData() << "\n";
  qputenv("QT_QPA_PLATFORM", QByteArray("windows"));
  std::cerr << "[qlaib_gui] forcing QT_QPA_PLATFORM=windows\n";
#else
  // Allow headless runs without X/Wayland on Unix: set QLAIB_HEADLESS=1 or unset DISPLAY.
  auto env = QProcessEnvironment::systemEnvironment();
  if (env.contains("QLAIB_HEADLESS") || (!env.contains("DISPLAY") && !env.contains("WAYLAND_DISPLAY"))) {
    qputenv("QT_QPA_PLATFORM", QByteArray("offscreen"));
  }
#endif
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
  {
    const auto args = app.arguments();
    std::cerr << "[qlaib_gui] argv (" << args.size() << "):";
    for (int i = 0; i < args.size(); ++i) {
      std::cerr << " [" << i << "]=" << args[i].toStdString();
    }
    std::cerr << "\n";
  }
  auto rc = app.exec();
  std::cerr << "[qlaib_gui] Exit code " << rc << "\n";
  return rc;
}
