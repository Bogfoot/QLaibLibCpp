#include "qlaib/metrics/Registry.h"
#include <algorithm>

namespace qlaib::metrics {

void Registry::registerMetric(std::unique_ptr<IMetric> metric) {
  metrics_.push_back(std::move(metric));
}

void Registry::computeAll(data::SampleBatch &batch) const {
  for (const auto &m : metrics_) {
    batch.metrics[m->name()] = m->compute(batch);
  }
}

double DummyVisibility::compute(const data::SampleBatch &batch) {
  if (batch.coincidences.empty())
    return 0.0;
  auto maxCoinc = std::max_element(
      batch.coincidences.begin(), batch.coincidences.end(),
      [](auto &a, auto &b) { return a.counts < b.counts; });
  return static_cast<double>(maxCoinc->counts) /
         static_cast<double>(maxCoinc->counts + 500.0);
}

double DummyQBER::compute(const data::SampleBatch &batch) {
  if (batch.singles.empty())
    return 0.0;
  double errors = static_cast<double>(batch.singles.front()) * 0.02;
  double total = static_cast<double>(batch.singles.front());
  return errors / total;
}

} // namespace qlaib::metrics
