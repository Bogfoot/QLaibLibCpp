#include "qlaib/ui/MainWindow.h"
#include <QApplication>
#include <QByteArray>
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
  std::cerr << "[qlaib_gui] Creating MainWindow\n";
  qlaib::ui::MainWindow w;
  std::cerr << "[qlaib_gui] Showing window\n";
  w.show();
  std::cerr << "[qlaib_gui] Starting backend\n";
  w.start();
  auto rc = app.exec();
  std::cerr << "[qlaib_gui] Exit code " << rc << "\n";
  return rc;
}
