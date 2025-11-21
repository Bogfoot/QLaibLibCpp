#pragma once

#include "qlaib/metrics/IMetric.h"
#include <memory>
#include <vector>

namespace qlaib::metrics {

class Registry {
public:
  void registerMetric(std::unique_ptr<IMetric> metric);
  void computeAll(data::SampleBatch &batch) const;

private:
  std::vector<std::unique_ptr<IMetric>> metrics_;
};

class DummyVisibility final : public IMetric {
public:
  std::string name() const override { return "visibility"; }
  double compute(const data::SampleBatch &batch) override;
};

class DummyQBER final : public IMetric {
public:
  std::string name() const override { return "qber"; }
  double compute(const data::SampleBatch &batch) override;
};

} // namespace qlaib::metrics
