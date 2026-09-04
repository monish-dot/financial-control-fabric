import { ControlDomain, ControlStatus } from './controls';

export type AnomalySeverity = 'NORMAL' | 'WATCH' | 'ANOMALOUS' | 'CRITICAL';

export interface ResidualObservation {
  residual_id: string;
  control_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  account_id?: string | null;
  merchant_id?: string | null;
  partner_id?: string | null;
  timestamp: string;
  expected_amount: string;
  actual_amount: string;
  residual_amount: string;
  currency: string;
  status: ControlStatus;
  metadata: Record<string, any>;
  vector?: any;
}

export interface ResidualDistributionStatistics {
  count: number;
  zero_residual_ratio?: string;
  mean: string;
  median: string;
  standard_deviation?: string;
  variance?: string;
  stddev?: string;
  minimum?: string;
  maximum?: string;
  p95: string;
  p99: string;
  absolute_mean?: string;
  absolute_median?: string;
  positive_ratio?: string;
  negative_ratio?: string;
  positive_bias_ratio?: string;
  negative_bias_ratio?: string;
}

export interface ResidualDistributionResponse {
  domain: ControlDomain;
  statistics: ResidualDistributionStatistics;
}

export interface ResidualDistributionShift {
  baseline_count: number;
  current_count: number;
  ks_statistic: string;
  wasserstein_distance: string;
  population_stability_index: string;
}

export interface ResidualTemporalMetrics {
  rolling_window: number;
  rolling_mean: string[];
  rolling_absolute_mean?: string[];
  rolling_zero_residual_ratio?: string[];
  cusum_positive?: string | null;
  cusum_negative?: string | null;
  cusum_max_absolute?: string | null;
  cusum_change_detected?: boolean;
}

export interface AnomalyScoreDetails {
  score: string;
  severity: AnomalySeverity;
  signals: string[];
  explanation?: string;
  distribution_metrics?: any;
  temporal_metrics?: any;
}

export interface ResidualAnalysis {
  domain?: ControlDomain;
  statistics?: ResidualDistributionStatistics;
  distribution_shift?: ResidualDistributionShift;
  temporal_metrics?: ResidualTemporalMetrics;
  anomaly_score: AnomalyScoreDetails;
  // Compatibility fields if flattened
  sample_count?: number;
  current_mean?: string;
  current_variance?: string;
  mean_drift?: string | null;
  variance_ratio?: string | null;
  severity?: AnomalySeverity;
}

export interface ResidualBaseline {
  baseline_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  account_id?: string | null;
  currency?: string | null;
  sample_count: number;
  statistics: ResidualDistributionStatistics;
  created_at: string;
}
