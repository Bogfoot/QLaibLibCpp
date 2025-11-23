#include "qlaib/ui/MainWindow.h"
#include "Coincidences.h"
#include "ReadCSV.h"
#include "qlaib/acquisition/BinReplayBackend.h"
#include "qlaib/acquisition/MockBackend.h"
#ifdef QQL_ENABLE_QUTAG
#include "qlaib/acquisition/QuTAGBackend.h"
#endif
#include <vector>

// Forward declare to placate some compilers where the header isn't picked up.
long long findBestDelayPicoseconds(
    std::span<const long long> reference, std::span<const long long> target,
    long long coincWindowPs, long long delayStartPs, long long delayEndPs,
    long long delayStepPs, std::vector<std::pair<float, int>> *scratchResults);

#ifdef QQL_ENABLE_CHARTS
#include <QtCharts/QChart>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QValueAxis>
#endif

#include <QFile>
#include <QFileDialog>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QDebug>
#include <QPushButton>
#include <QShortcut>
#include <QSpinBox>
#include <QStandardPaths>
#include <QStatusBar>
#include <QTabWidget>
#include <QTableWidget>
#include <QTextStream>
#include <QVBoxLayout>
#include <QtWidgets>
#include <cstdlib>
#include <optional>
#include <span>
#include <unordered_map>

namespace qlaib::ui {

#ifdef QQL_ENABLE_CHARTS
using SeriesMap = std::unordered_map<QString, QLineSeries *>;
#endif

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent) {
  fprintf(stderr, "[MainWindow] ctor start\n");
  resize(1200, 720);
  setWindowTitle("QLaib Live (C++ Qt)");
  qDebug("MainWindow: before setupUi");
  setupUi();
  qDebug("MainWindow: after setupUi");

  cfg_.useMock = true;
  cfg_.exposureSeconds = 0.5;
  cfg_.timestampBufferSize = 200000;
  cfg_.coincidenceWindowPs = 200000;

  // Backend selection via CLI mode
  if (mode_.compare("replay", Qt::CaseInsensitive) == 0) {
    cfg_.replayFile = replayFile_.toStdString();
    if (cfg_.replayFile.empty()) {
      statusBar()->showMessage("Replay mode requires --replay-bin");
      backend_ = std::make_unique<acquisition::MockBackend>();
    } else {
      cfg_.useMock = false;
      backend_ = std::make_unique<acquisition::BinReplayBackend>();
      statusBar()->showMessage(QString("Replay: %1").arg(replayFile_));
    }
  } else if (mode_.compare("mock", Qt::CaseInsensitive) == 0) {
    backend_ = std::make_unique<acquisition::MockBackend>();
    statusBar()->showMessage("Mock mode");
  } else { // live (default)
#ifdef QQL_ENABLE_QUTAG
    backend_ = std::make_unique<acquisition::QuTAGBackend>();
    statusBar()->showMessage("quTAG live (fallback to mock if init fails)");
#else
    backend_ = std::make_unique<acquisition::MockBackend>();
    statusBar()->showMessage("Live quTAG disabled at build; using Mock backend");
#endif
  }
  qDebug("MainWindow: backend selected");

  metrics_.registerMetric(std::make_unique<metrics::DummyVisibility>());
  metrics_.registerMetric(std::make_unique<metrics::DummyQBER>());
  qDebug("MainWindow: metrics registered");

  connect(&timer_, &QTimer::timeout, this, &MainWindow::tick);
  timer_.setInterval(50);

  loadConfig();
  qDebug("MainWindow: constructed");
  fprintf(stderr, "[MainWindow] ctor end\n");
}

void MainWindow::setupUi() {
#ifdef QQL_ENABLE_CHARTS
  qDebug("setupUi: begin");
  auto *central = new QWidget(this);
  mainLayout_ = new QVBoxLayout(central);

  // Controls bar
  auto *controls = new QWidget(central);
  auto *cl = new QHBoxLayout(controls);
  auto *btnExport = new QPushButton("Export CSV", controls);
  exposureSpin_ = new QDoubleSpinBox(controls);
  exposureSpin_->setRange(0.05, 60.0);
  exposureSpin_->setSingleStep(0.05);
  exposureSpin_->setValue(cfg_.exposureSeconds);
  auto *lblExp = new QLabel("Exposure (s):", controls);
  coincWindowSpin_ = new QDoubleSpinBox(controls);
  coincWindowSpin_->setRange(10.0, 5000.0);
  coincWindowSpin_->setSingleStep(10.0);
  coincWindowSpin_->setValue(coincidenceWindowPs_);
  auto *lblCoinc = new QLabel("Coinc window (ps):", controls);
  histBtn_ = new QPushButton("Histogram", controls);
  recordBtn_ = new QPushButton("Record BIN", controls);

  cl->addWidget(lblExp);
  cl->addWidget(exposureSpin_);
  cl->addSpacing(12);
  cl->addWidget(lblCoinc);
  cl->addWidget(coincWindowSpin_);
  cl->addSpacing(12);
  cl->addWidget(histBtn_);
  cl->addWidget(btnExport);
  cl->addWidget(recordBtn_);
  cl->addStretch(1);
  mainLayout_->addWidget(controls, 0);

  // Tabs
  tabs_ = new QTabWidget(central);
  mainLayout_->addWidget(tabs_, 1);
  setupChartTabs();
  setupHistogramTab();

  setCentralWidget(central);
  qDebug("setupUi: end");

  connect(btnExport, &QPushButton::clicked, this, &MainWindow::exportCsv);
  connect(histBtn_, &QPushButton::clicked, this, [this]() {
    computeHistogram();
    if (histTab_)
      tabs_->setCurrentWidget(histTab_);
  });
  connect(recordBtn_, &QPushButton::clicked, this,
          &MainWindow::toggleRecording);
  connect(exposureSpin_, &QDoubleSpinBox::editingFinished, this, [this]() {
    cfg_.exposureSeconds = exposureSpin_->value();
    saveConfig();
    restartBackend();
  });
  connect(coincWindowSpin_, qOverload<double>(&QDoubleSpinBox::valueChanged),
          this, [this](double v) {
            coincidenceWindowPs_ = v;
            cfg_.coincidenceWindowPs = static_cast<long long>(v);
            saveConfig();
          });

  // Hotkeys to switch tabs (1-3)
  auto switchTab = [this](int idx) {
    if (idx >= 0 && idx < tabs_->count())
      tabs_->setCurrentIndex(idx);
  };
  connectShortcut(Qt::Key_1, [switchTab]() { switchTab(0); });
  connectShortcut(Qt::Key_2, [switchTab]() { switchTab(1); });
  connectShortcut(Qt::Key_3, [switchTab]() { switchTab(2); });
#else
  auto *central = new QWidget(this);
  auto *layout = new QHBoxLayout(central);
  layout->addWidget(
      new QLabel("Qt Charts not available. Build with QQL_ENABLE_CHARTS=ON "
                 "after installing qtcharts."));
  setCentralWidget(central);
#endif
}

#ifdef QQL_ENABLE_CHARTS
void MainWindow::setupChartTabs() {
  // Singles tab
  auto *singlesTab = new QWidget(tabs_);
  auto *sLayout = new QVBoxLayout(singlesTab);
  setupPairsUI();
  singlesChart_ = new QChart();
  singlesChart_->setTitle("Singles (counts)");
  singlesAxisX_ = new QValueAxis;
  singlesAxisY_ = new QValueAxis;
  singlesAxisX_->setTitleText("Time (s)");
  singlesAxisY_->setTitleText("Counts");
  singlesChart_->addAxis(singlesAxisX_, Qt::AlignBottom);
  singlesChart_->addAxis(singlesAxisY_, Qt::AlignLeft);
  singlesView_ = new QChartView(singlesChart_);
  singlesView_->setRenderHint(QPainter::Antialiasing);
  sLayout->addWidget(singlesView_);
  tabs_->addTab(singlesTab, "Singles");

  // Coincidences tab
  auto *coincTab = new QWidget(tabs_);
  auto *cLayout = new QVBoxLayout(coincTab);
  coincChart_ = new QChart();
  coincChart_->setTitle("Coincidences");
  coincAxisX_ = new QValueAxis;
  coincAxisY_ = new QValueAxis;
  coincAxisX_->setTitleText("Time (s)");
  coincAxisY_->setTitleText("Counts");
  coincChart_->addAxis(coincAxisX_, Qt::AlignBottom);
  coincChart_->addAxis(coincAxisY_, Qt::AlignLeft);
  coincView_ = new QChartView(coincChart_);
  coincView_->setRenderHint(QPainter::Antialiasing);
  cLayout->addWidget(coincView_);
  tabs_->addTab(coincTab, "Coincidences");

  // Metrics tab
  auto *metricsTab = new QWidget(tabs_);
  auto *mLayout = new QVBoxLayout(metricsTab);
  metricsChart_ = new QChart();
  metricsChart_->setTitle("Metrics");
  metricsAxisX_ = new QValueAxis;
  metricsAxisY_ = new QValueAxis;
  metricsAxisX_->setTitleText("Time (s)");
  metricsAxisY_->setTitleText("Value");
  metricsChart_->addAxis(metricsAxisX_, Qt::AlignBottom);
  metricsChart_->addAxis(metricsAxisY_, Qt::AlignLeft);
  metricsView_ = new QChartView(metricsChart_);
  metricsView_->setRenderHint(QPainter::Antialiasing);
  mLayout->addWidget(metricsView_);
  tabs_->addTab(metricsTab, "Metrics");
}

void MainWindow::setupHistogramTab() {
  histTab_ = new QWidget(tabs_);
  auto *v = new QVBoxLayout(histTab_);
  auto *controls = new QWidget(histTab_);
  auto *cl = new QHBoxLayout(controls);
  pairBox_ = new QComboBox(controls);
  windowSpin_ = new QDoubleSpinBox(controls);
  windowSpin_->setRange(10.0, 10000.0);
  windowSpin_->setValue(200.0);
  startSpin_ = new QDoubleSpinBox(controls);
  startSpin_->setRange(-20000.0, 0.0);
  startSpin_->setValue(-8000.0);
  endSpin_ = new QDoubleSpinBox(controls);
  endSpin_->setRange(0.0, 20000.0);
  endSpin_->setValue(8000.0);
  stepSpin_ = new QDoubleSpinBox(controls);
  stepSpin_->setRange(1.0, 2000.0);
  stepSpin_->setValue(50.0);
  cl->addWidget(new QLabel("Pair:", controls));
  cl->addWidget(pairBox_);
  cl->addWidget(new QLabel("Window ps", controls));
  cl->addWidget(windowSpin_);
  cl->addWidget(new QLabel("Start ps", controls));
  cl->addWidget(startSpin_);
  cl->addWidget(new QLabel("End ps", controls));
  cl->addWidget(endSpin_);
  cl->addWidget(new QLabel("Step ps", controls));
  cl->addWidget(stepSpin_);
  cl->addStretch(1);
  v->addWidget(controls, 0);

  histChart_ = new QChart();
  histChart_->setTitle("Delay histogram");
  histAxisX_ = new QValueAxis;
  histAxisY_ = new QValueAxis;
  histAxisX_->setTitleText("Delay (ps)");
  histAxisY_->setTitleText("Counts");
  histChart_->addAxis(histAxisX_, Qt::AlignBottom);
  histChart_->addAxis(histAxisY_, Qt::AlignLeft);
  histView_ = new QChartView(histChart_);
  histView_->setRenderHint(QPainter::Antialiasing);
  v->addWidget(histView_, 1);
  tabs_->addTab(histTab_, "Histogram");
}
#endif

void MainWindow::start() {
  const auto backendName = [this]() -> const char * {
    if (dynamic_cast<acquisition::MockBackend *>(backend_.get()))
      return "MockBackend";
    if (dynamic_cast<acquisition::BinReplayBackend *>(backend_.get()))
      return "BinReplayBackend";
#ifdef QQL_ENABLE_QUTAG
    if (dynamic_cast<acquisition::QuTAGBackend *>(backend_.get()))
      return "QuTAGBackend";
#endif
    return "UnknownBackend";
  }();

  qInfo("MainWindow::start backend=%s mode=%s replay=%s useMock=%d "
        "exposure=%.3fs buf=%d coincWin=%lld history=%d",
        backendName, qPrintable(mode_), qPrintable(replayFile_),
        cfg_.useMock ? 1 : 0, cfg_.exposureSeconds, cfg_.timestampBufferSize,
        static_cast<long long>(cfg_.coincidenceWindowPs), historyLen_);

  const bool started = backend_->start(cfg_);
  if (!started) {
    qWarning("MainWindow::start: backend %s failed to start, "
             "switching to MockBackend", backendName);
    statusBar()->showMessage("Backend failed to start; switching to mock");
    backend_ = std::make_unique<acquisition::MockBackend>();
    cfg_.useMock = true;
    const bool mockStarted = backend_->start(cfg_);
    qInfo("MainWindow::start: MockBackend %s",
          mockStarted ? "started" : "failed to start");
  } else {
    qInfo("MainWindow::start: backend %s started", backendName);
  }
  t0_ms_ = QDateTime::currentMSecsSinceEpoch();
  timer_.start();
}

void MainWindow::stop() {
  timer_.stop();
  backend_->stop();
}

void MainWindow::restartBackend() {
  stop();
  start();
}

void MainWindow::tick() {
  auto batch = backend_->nextBatch();
  if (!batch)
    return;
  metrics_.computeAll(*batch);
  latestBatch_ = batch;
  saveConfig();
  appendSample(*batch);
  refreshPairList(*batch);
}

void MainWindow::appendSample(const data::SampleBatch &batch) {
#ifdef QQL_ENABLE_CHARTS
  const auto now_ms = QDateTime::currentMSecsSinceEpoch();
  double t = (now_ms - t0_ms_) / 1000.0;

  const auto trimSeries = [](QLineSeries *s, int maxPts) {
    Q_UNUSED(s);
    Q_UNUSED(maxPts);
  };

  auto updateSeries = [&](SeriesMap &map, QChart *chart, QValueAxis *axX,
                          QValueAxis *axY, const QString &name, double value) {
    auto *series = map[name];
    if (!series) {
      series = new QLineSeries(chart);
      series->setName(name);
      chart->addSeries(series);
      series->attachAxis(axX);
      series->attachAxis(axY);
      map[name] = series;
    }
    series->append(t, value);
    trimSeries(series, historyLen_);
  };

  // Singles
  for (size_t i = 0; i < batch.singles.size(); ++i) {
    updateSeries(singlesSeries_, singlesChart_, singlesAxisX_, singlesAxisY_,
                 QString("Ch%1").arg(i + 1),
                 static_cast<double>(batch.singles[i]));
  }
  singlesAxisX_->setRange(0.0, t + 1.0);

  // Coincidences (recomputed from pairs and raw timestamps)
  QSet<QString> activeLabels;
  activeLabels.reserve(static_cast<int>(pairs_.size()));
  for (const auto &pair : pairs_) {
    activeLabels.insert(pair.label);
    if (pair.chA <= 0 || pair.chB <= 0 ||
        pair.chA > static_cast<int>(batch.timestamps_ps.size()) ||
        pair.chB > static_cast<int>(batch.timestamps_ps.size()))
      continue;
    const auto &ta = batch.timestamps_ps[pair.chA - 1];
    const auto &tb = batch.timestamps_ps[pair.chB - 1];
    if (ta.empty() || tb.empty())
      continue;
    std::span<const long long> sa(ta.data(), ta.size());
    std::span<const long long> sb(tb.data(), tb.size());
    int coincidences = countCoincidencesWithDelay(
        sa, sb, static_cast<long long>(coincidenceWindowPs_), pair.delayPs);
    updateSeries(coincSeries_, coincChart_, coincAxisX_, coincAxisY_,
                 pair.label, coincidences);
  }
  // Remove stale coincidence series whose labels were renamed/removed
  for (auto it = coincSeries_.begin(); it != coincSeries_.end(); ) {
    if (!activeLabels.contains(it->first)) {
      QLineSeries *s = it->second;
      coincChart_->removeSeries(s);
      s->deleteLater();
      it = coincSeries_.erase(it);
    } else {
      ++it;
    }
  }
  coincAxisX_->setRange(0.0, t + 1.0);

  // Metrics (qber, visibility, s_parameter optional)
  const char *metricNames[] = {"qber", "visibility", "s_parameter"};
  for (auto key : metricNames) {
    auto it = batch.metrics.find(key);
    if (it == batch.metrics.end())
      continue;
    updateSeries(metricSeries_, metricsChart_, metricsAxisX_, metricsAxisY_,
                 QString::fromUtf8(key), it->second);
  }
  metricsAxisX_->setRange(0.0, t + 1.0);

  // Auto scale Y for singles/metrics
  const auto rescale = [](QChart *chart, QValueAxis *axY) {
    double maxY = 1.0;
    for (auto *s : chart->series()) {
      for (const auto &p : static_cast<QLineSeries *>(s)->points())
        maxY = std::max(maxY, p.y());
    }
    axY->setRange(0.0, maxY * 1.2);
  };
  rescale(singlesChart_, singlesAxisY_);
  rescale(coincChart_, coincAxisY_);
  rescale(metricsChart_, metricsAxisY_);
#endif

  double qber = batch.metrics.count("qber") ? batch.metrics.at("qber") : 0.0;
  double vis =
      batch.metrics.count("visibility") ? batch.metrics.at("visibility") : 0.0;
  statusBar()->showMessage(
      QString("QBER %1 | Vis %2 | Singles ch1 %3")
          .arg(qber, 0, 'f', 3)
          .arg(vis, 0, 'f', 3)
          .arg(batch.singles.empty() ? 0.0
                                     : static_cast<double>(batch.singles.front()),
               0, 'f', 0));
}

void MainWindow::refreshPairList(const data::SampleBatch &batch) {
#ifdef QQL_ENABLE_CHARTS
  if (!pairBox_)
    return;
  QStringList labels;
  labels.reserve(static_cast<int>(pairs_.size()));
  for (const auto &p : pairs_)
    labels << p.label;
  if (labels != pairLabelsCache_) {
    QString current = pairBox_->currentText();
    pairBox_->clear();
    pairBox_->addItems(labels);
    int idx = pairBox_->findText(current);
    if (idx >= 0)
      pairBox_->setCurrentIndex(idx);
    pairLabelsCache_ = labels;
    refreshPairsTable();
  }
#endif
}

void MainWindow::computeHistogram() {
#ifdef QQL_ENABLE_CHARTS
  if (!latestBatch_) {
    statusBar()->showMessage("No data yet; start acquisition first.");
    return;
  }
  QString pair = pairBox_->currentText();
  const auto it =
      std::find_if(pairs_.begin(), pairs_.end(),
                   [&](const PairSpec &p) { return p.label == pair; });
  if (it == pairs_.end()) {
    statusBar()->showMessage("Select a pair to histogram.");
    return;
  }
  int a = it->chA;
  int b = it->chB;

  if (a <= 0 || b <= 0 ||
      a > static_cast<int>(latestBatch_->timestamps_ps.size()) ||
      b > static_cast<int>(latestBatch_->timestamps_ps.size())) {
    statusBar()->showMessage("Selected pair channels missing in data.");
    return;
  }

  const auto &ta = latestBatch_->timestamps_ps[a - 1];
  const auto &tb = latestBatch_->timestamps_ps[b - 1];
  if (ta.empty() || tb.empty()) {
    statusBar()->showMessage("No timestamps for selected pair in latest batch.");
    return;
  }

  std::vector<std::pair<float, int>> results;
  computeCoincidencesForRange(
      ta, tb, static_cast<long long>(windowSpin_->value()),
      static_cast<long long>(startSpin_->value()),
      static_cast<long long>(endSpin_->value()),
      static_cast<long long>(stepSpin_->value()), results);

  // Plot
  auto *series = new QLineSeries(histChart_);
  for (auto &r : results) {
    series->append(static_cast<double>(r.first), static_cast<double>(r.second));
  }
  histChart_->removeAllSeries();
  histChart_->addSeries(series);
  series->attachAxis(histAxisX_);
  series->attachAxis(histAxisY_);
  histAxisX_->setRange(startSpin_->value(), endSpin_->value());

  double maxY = 1.0;
  for (auto &r : results)
    maxY = std::max<double>(maxY, r.second);
  histAxisY_->setRange(0.0, maxY * 1.2);
  statusBar()->showMessage(
      QString("Histogram: %1 bins").arg(static_cast<int>(results.size())));
#endif
}

void MainWindow::exportCsv() {
#ifdef QQL_ENABLE_CHARTS
  QString path = QFileDialog::getSaveFileName(this, "Export CSV", "history.csv",
                                              "CSV Files (*.csv)");
  if (path.isEmpty())
    return;
  QFile f(path);
  if (!f.open(QIODevice::WriteOnly | QIODevice::Text))
    return;
  QTextStream out(&f);
  out << "series,time,value\n";
  auto dumpSeries = [&out](const QString &name, QLineSeries *s) {
    for (const auto &p : s->points())
      out << name << "," << p.x() << "," << p.y() << "\n";
  };
  for (auto &[name, s] : singlesSeries_)
    dumpSeries(name, s);
  for (auto &[name, s] : coincSeries_)
    dumpSeries(name, s);
  for (auto &[name, s] : metricSeries_)
    dumpSeries(name, s);
  statusBar()->showMessage("Exported CSV");
#endif
}

void MainWindow::toggleRecording() {
#ifdef QQL_ENABLE_QUTAG
  auto *qtb = dynamic_cast<acquisition::QuTAGBackend *>(backend_.get());
  if (!qtb) {
    statusBar()->showMessage("Recording only available with quTAG backend");
    return;
  }
  QString path = QFileDialog::getSaveFileName(this, "Record BIN", "capture.bin",
                                              "BIN Files (*.bin)");
  if (path.isEmpty())
    return;
  if (qtb->startRecording(path.toStdString(), false)) {
    statusBar()->showMessage("Recording to " + path);
  } else {
    statusBar()->showMessage("Failed to start recording");
  }
#else
  statusBar()->showMessage("Recording not built (enable QQL_ENABLE_QUTAG)");
#endif
}

#ifdef QQL_ENABLE_CHARTS
void MainWindow::connectShortcut(Qt::Key key, std::function<void()> slot) {
  auto *shortcut = new QShortcut(QKeySequence(key), this);
  connect(shortcut, &QShortcut::activated, this, std::move(slot));
}
#endif

void MainWindow::setupPairsUI() {
#ifdef QQL_ENABLE_CHARTS
  pairsTable_ = new QTableWidget(0, 4, this);
  QStringList headers = {"Label", "ChA", "ChB", "Delay ps"};
  pairsTable_->setHorizontalHeaderLabels(headers);
  pairsTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
  pairsTable_->setFixedHeight(150);
  if (mainLayout_)
    mainLayout_->insertWidget(1, pairsTable_);

  auto *btnRow = new QWidget(this);
  auto *h = new QHBoxLayout(btnRow);
  auto *add = new QPushButton("Add pair", btnRow);
  auto *rem = new QPushButton("Remove selected", btnRow);
  auto *reset = new QPushButton("Reset defaults", btnRow);
  auto *calibSel = new QPushButton("Calibrate selected", btnRow);
  auto *calibAll = new QPushButton("Calibrate all", btnRow);
  h->addWidget(add);
  h->addWidget(rem);
  h->addWidget(reset);
  h->addWidget(calibSel);
  h->addWidget(calibAll);
  h->addStretch(1);
  if (mainLayout_)
    mainLayout_->insertWidget(2, btnRow);

  connect(add, &QPushButton::clicked, this, &MainWindow::addPair);
  connect(rem, &QPushButton::clicked, this, &MainWindow::removeSelectedPair);
  connect(reset, &QPushButton::clicked, this, &MainWindow::resetPairs);
  connect(calibSel, &QPushButton::clicked, this,
          &MainWindow::calibrateSelected);
  connect(calibAll, &QPushButton::clicked, this, &MainWindow::calibrateAll);
  connect(pairsTable_, &QTableWidget::cellChanged, this,
          [this](int row, int col) {
            if (fillingPairsTable_)
              return;
            if (row < 0 || row >= static_cast<int>(pairs_.size()))
              return;
            auto *item = pairsTable_->item(row, col);
            if (!item)
              return;
            auto txt = item->text();
            auto &p = pairs_[static_cast<size_t>(row)];
            switch (col) {
            case 0:
              p.label = txt;
              break;
            case 1:
              p.chA = txt.toInt();
              break;
            case 2:
              p.chB = txt.toInt();
              break;
            case 3:
              p.delayPs = static_cast<long long>(txt.toDouble());
              break;
            default:
              break;
            }
            saveConfig();
          });
#endif
}

void MainWindow::addPair() {
  PairSpec p{QString("Pair %1").arg(pairs_.size() + 1), 1, 2, 0};
  pairs_.push_back(p);
  refreshPairsTable();
  saveConfig();
}

void MainWindow::removeSelectedPair() {
#ifdef QQL_ENABLE_CHARTS
  auto row = pairsTable_ ? pairsTable_->currentRow() : -1;
  if (row < 0 || row >= static_cast<int>(pairs_.size()))
    return;
  pairs_.erase(pairs_.begin() + row);
  refreshPairsTable();
  saveConfig();
#endif
}

void MainWindow::resetPairs() {
  pairs_.clear();
  pairs_.push_back({"1-5", 1, 5, 0});
  pairs_.push_back({"2-6", 2, 6, 0});
  pairs_.push_back({"3-7", 3, 7, 0});
  pairs_.push_back({"4-8", 4, 8, 0});
  pairs_.push_back({"1-6", 1, 6, 0});
  pairs_.push_back({"2-5", 2, 5, 0});
  pairs_.push_back({"3-8", 3, 8, 0});
  pairs_.push_back({"4-7", 4, 7, 0});
  refreshPairsTable();
  saveConfig();
}

void MainWindow::refreshPairsTable() {
#ifdef QQL_ENABLE_CHARTS
  if (!pairsTable_)
    return;
  fillingPairsTable_ = true;
  pairsTable_->setRowCount(static_cast<int>(pairs_.size()));
  for (int i = 0; i < static_cast<int>(pairs_.size()); ++i) {
    const auto &p = pairs_[static_cast<size_t>(i)];
    pairsTable_->setItem(i, 0, new QTableWidgetItem(p.label));
    pairsTable_->setItem(i, 1, new QTableWidgetItem(QString::number(p.chA)));
    pairsTable_->setItem(i, 2, new QTableWidgetItem(QString::number(p.chB)));
    pairsTable_->setItem(i, 3,
                         new QTableWidgetItem(QString::number(p.delayPs)));
  }
  fillingPairsTable_ = false;
  // Also refresh the histogram pair selector without recursing.
  if (pairBox_) {
    QString current = pairBox_->currentText();
    pairBox_->clear();
    for (const auto &p : pairs_)
      pairBox_->addItem(p.label);
    int idx = pairBox_->findText(current);
    if (idx >= 0)
      pairBox_->setCurrentIndex(idx);
  }
#endif
}

void MainWindow::calibrateSelected() {
#ifdef QQL_ENABLE_CHARTS
  if (!latestBatch_ || !pairsTable_)
    return;
  int row = pairsTable_->currentRow();
  if (row < 0 || row >= static_cast<int>(pairs_.size()))
    return;
  auto &p = pairs_[static_cast<size_t>(row)];
  const auto &ta = latestBatch_->timestamps_ps[p.chA - 1];
  const auto &tb = latestBatch_->timestamps_ps[p.chB - 1];
  if (ta.empty() || tb.empty())
    return;
  auto best = ::findBestDelayPicoseconds(
      ta, tb, static_cast<long long>(coincidenceWindowPs_),
      static_cast<long long>(startSpin_->value()),
      static_cast<long long>(endSpin_->value()),
      static_cast<long long>(stepSpin_->value()), nullptr);
  p.delayPs = best;
  refreshPairsTable();
  saveConfig();
#endif
}

void MainWindow::calibrateAll() {
#ifdef QQL_ENABLE_CHARTS
  if (!latestBatch_)
    return;
  for (auto &p : pairs_) {
    if (p.chA <= 0 || p.chB <= 0 ||
        p.chA > static_cast<int>(latestBatch_->timestamps_ps.size()) ||
        p.chB > static_cast<int>(latestBatch_->timestamps_ps.size()))
      continue;
    std::span<const long long> ta(latestBatch_->timestamps_ps[p.chA - 1]);
    std::span<const long long> tb(latestBatch_->timestamps_ps[p.chB - 1]);
    if (ta.empty() || tb.empty())
      continue;
    p.delayPs = ::findBestDelayPicoseconds(
        ta, tb, static_cast<long long>(coincidenceWindowPs_),
        static_cast<long long>(startSpin_->value()),
        static_cast<long long>(endSpin_->value()),
        static_cast<long long>(stepSpin_->value()), nullptr);
  }
  refreshPairsTable();
  saveConfig();
#endif
}

void MainWindow::saveConfig() {
  QJsonObject root;
  root["coinc_window_ps"] = coincidenceWindowPs_;
  QJsonArray arr;
  for (const auto &p : pairs_) {
    QJsonObject o;
    o["label"] = p.label;
    o["chA"] = p.chA;
    o["chB"] = p.chB;
    o["delay_ps"] = static_cast<double>(p.delayPs);
    arr.append(o);
  }
  root["pairs"] = arr;
  auto path =
      QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation);
  QDir().mkpath(path);
  QFile f(path + "/qlaib_gui.json");
  if (f.open(QIODevice::WriteOnly))
    f.write(QJsonDocument(root).toJson());
}

void MainWindow::loadConfig() {
  qDebug("loadConfig: begin");
  resetPairs();
  auto path =
      QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation) +
      "/qlaib_gui.json";
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly))
  {
    qDebug("loadConfig: no config file");
    return;
  }
  auto doc = QJsonDocument::fromJson(f.readAll());
  if (!doc.isObject())
    return;
  auto root = doc.object();
  coincidenceWindowPs_ = root.value("coinc_window_ps").toDouble(200.0);
  if (coincWindowSpin_)
    coincWindowSpin_->setValue(coincidenceWindowPs_);
  if (root.contains("pairs") && root["pairs"].isArray()) {
    pairs_.clear();
    for (auto v : root["pairs"].toArray()) {
      auto o = v.toObject();
      PairSpec p;
      p.label = o.value("label").toString();
      p.chA = o.value("chA").toInt();
      p.chB = o.value("chB").toInt();
      p.delayPs = static_cast<long long>(o.value("delay_ps").toDouble());
      pairs_.push_back(p);
    }
  }
  refreshPairsTable();
  qDebug("loadConfig: end");
}

} // namespace qlaib::ui
