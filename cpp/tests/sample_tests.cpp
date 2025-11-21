#include <QtTest/QtTest>
#include "qlaib/acquisition/MockBackend.h"

class MockBackendTest : public QObject {
  Q_OBJECT
private slots:
  void generates_batches() {
    qlaib::acquisition::MockBackend backend;
    qlaib::acquisition::BackendConfig cfg;
    QVERIFY(backend.start(cfg));
    auto batch = backend.nextBatch();
    QVERIFY(batch.has_value());
    QVERIFY(!batch->singles.empty());
  }
};

QTEST_MAIN(MockBackendTest)
#include "sample_tests.moc"
