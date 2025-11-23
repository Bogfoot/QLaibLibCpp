#pragma once

#include "qlaib/acquisition/IBackend.h"
#include "qlaib/core/EventBus.h"
#include "qlaib/data/SampleBatch.h"
#include "qlaib/metrics/Registry.h"
#include <QMainWindow>
#include <QTimer>
#include <memory>
#include <optional>
#include <functional>
#include <unordered_map>
#include <vector>

#ifdef QQL_ENABLE_CHARTS
QT_BEGIN_NAMESPACE
class QChartView;
class QLineSeries;
class QValueAxis;
class QChart;
class QTabWidget;
class QComboBox;
class QDoubleSpinBox;
class QPushButton;
class QShortcut;
class QTableWidget;
class QVBoxLayout;
QT_END_NAMESPACE
#endif

namespace qlaib::ui {

/// User-configurable coincidence pair (channel A/B and relative delay).
struct PairSpec {
  QString label;    ///< Display name shown in tables/plots.
  int chA;          ///< 1-based channel index A.
  int chB;          ///< 1-based channel index B.
  long long delayPs;///< Optional calibrated delay (picoseconds).
};

/**
 * @brief Main GUI window: drives backends and renders live metrics/plots.
 *
 * Responsibilities:
 *  - select and start the desired backend (live quTAG, replay, mock)
 *  - pull batches on a timer and update charts/tables
 *  - manage coincidence pairs and calibration shortcuts
 */
class MainWindow : public QMainWindow {
  Q_OBJECT
public:
  explicit MainWindow(QWidget *parent = nullptr);
  void start();
  void stop();

  // CLI hooks
  void setMode(const QString &mode) { mode_ = mode; }
  void setReplayFile(const QString &file) { replayFile_ = file; }

private slots:
  void tick();
  void computeHistogram();
  void exportCsv();
  void toggleRecording();
  void addPair();
  void removeSelectedPair();
  void resetPairs();
  void calibrateSelected();
  void calibrateAll();

private:
  void setupUi();
#ifdef QQL_ENABLE_CHARTS
  void setupChartTabs();
  void setupHistogramTab();
  void setupPairsUI();
  void connectShortcut(Qt::Key key, std::function<void()> slot);
#endif
  void appendSample(const data::SampleBatch &batch);
  void refreshPairList(const data::SampleBatch &batch);
  void refreshPairsTable();
  void saveConfig();
  void loadConfig();

  acquisition::BackendConfig cfg_;
  std::unique_ptr<acquisition::IBackend> backend_;
  metrics::Registry metrics_;
  QTimer timer_;
  std::optional<data::SampleBatch> latestBatch_;
  std::vector<PairSpec> pairs_;
  QString mode_{"live"};
  QString replayFile_;
  double histogramWindowPs_{200.0};
  double coincidenceWindowPs_{200.0};

#ifdef QQL_ENABLE_CHARTS
  QVBoxLayout *mainLayout_{nullptr};
  QTabWidget *tabs_{nullptr};
  QChartView *singlesView_{nullptr};
  QChartView *coincView_{nullptr};
  QChartView *metricsView_{nullptr};
  QChartView *histView_{nullptr};
  QWidget *histTab_{nullptr};
  QChart *singlesChart_{nullptr};
  QChart *coincChart_{nullptr};
  QChart *metricsChart_{nullptr};
  QChart *histChart_{nullptr};
  QValueAxis *singlesAxisX_{nullptr};
  QValueAxis *singlesAxisY_{nullptr};
  QValueAxis *coincAxisX_{nullptr};
  QValueAxis *coincAxisY_{nullptr};
  QValueAxis *metricsAxisX_{nullptr};
  QValueAxis *metricsAxisY_{nullptr};
  QValueAxis *histAxisX_{nullptr};
  QValueAxis *histAxisY_{nullptr};
  QComboBox *pairBox_{nullptr};
  QDoubleSpinBox *windowSpin_{nullptr};
  QDoubleSpinBox *startSpin_{nullptr};
  QDoubleSpinBox *endSpin_{nullptr};
  QDoubleSpinBox *stepSpin_{nullptr};
  QDoubleSpinBox *exposureSpin_{nullptr};
  QDoubleSpinBox *coincWindowSpin_{nullptr};
  QTableWidget *pairsTable_{nullptr};
  QPushButton *histBtn_{nullptr};
  QPushButton *recordBtn_{nullptr};
  bool fillingPairsTable_{false};
  std::unordered_map<QString, QLineSeries *> singlesSeries_;
  std::unordered_map<QString, QLineSeries *> coincSeries_;
  std::unordered_map<QString, QLineSeries *> metricSeries_;
  int historyLen_{400};
#endif
  qint64 t0_ms_{0};
};

} // namespace qlaib::ui
