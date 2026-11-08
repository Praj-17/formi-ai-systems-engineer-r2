"""Statistical analysis for experiment winner selection and drift detection."""
import math
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def bayesian_winner(variants: Dict[str, Tuple[int, int]], 
                    alpha_prior: float = 1.0,
                    beta_prior: float = 1.0,
                    min_samples: int = 100,
                    confidence_threshold: float = 0.95) -> Optional[str]:
    """
    Bayesian winner selection using Beta-Binomial model.
    
    Args:
        variants: {variant_id: (successes, trials)}
        alpha_prior: Beta prior alpha
        beta_prior: Beta prior beta  
        min_samples: Minimum samples per variant
        confidence_threshold: Probability threshold for declaring winner
    
    Returns:
        Winner variant ID or None if no clear winner
    """
    if not variants:
        return None
    
    # Filter variants with enough samples
    viable = {k: v for k, v in variants.items() if v[1] >= min_samples}
    if len(viable) < 2:
        return None
    
    # Compute posterior parameters
    posteriors = {}
    for variant_id, (successes, trials) in viable.items():
        alpha_post = alpha_prior + successes
        beta_post = beta_prior + (trials - successes)
        mean = alpha_post / (alpha_post + beta_post)
        posteriors[variant_id] = (alpha_post, beta_post, mean)
    
    # Find best mean
    best_id = max(posteriors.keys(), key=lambda k: posteriors[k][2])
    best_mean = posteriors[best_id][2]
    
    # Check if best is significantly better using approximate probability
    # that best > all others (simplified monte carlo approach)
    for other_id, (alpha_o, beta_o, mean_o) in posteriors.items():
        if other_id == best_id:
            continue
        
        # Approximate probability that best > other using normal approximation
        # to Beta distributions for large samples
        alpha_b, beta_b = posteriors[best_id][0], posteriors[best_id][1]
        
        var_b = (alpha_b * beta_b) / ((alpha_b + beta_b)**2 * (alpha_b + beta_b + 1))
        var_o = (alpha_o * beta_o) / ((alpha_o + beta_o)**2 * (alpha_o + beta_o + 1))
        
        mean_diff = best_mean - mean_o
        std_diff = math.sqrt(var_b + var_o)
        
        if std_diff > 0:
            z_score = mean_diff / std_diff
            # Approximate P(best > other) using z-score
            prob = normal_cdf(z_score)
            if prob < confidence_threshold:
                return None
    
    return best_id


def normal_cdf(z: float) -> float:
    """Approximate standard normal CDF."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def detect_drift(baseline: Tuple[int, int], 
                 current: Tuple[int, int],
                 threshold: float = 0.05,
                 min_samples: int = 50) -> bool:
    """
    Detect if current rate has drifted down from baseline.
    
    Args:
        baseline: (successes, trials) for baseline period
        current: (successes, trials) for current period
        threshold: Absolute drop threshold
        min_samples: Minimum samples to check
    
    Returns:
        True if significant drift detected
    """
    if current[1] < min_samples or baseline[1] < min_samples:
        return False
    
    baseline_rate = baseline[0] / baseline[1] if baseline[1] > 0 else 0
    current_rate = current[0] / current[1] if current[1] > 0 else 0
    
    drop = baseline_rate - current_rate
    return drop > threshold


def caller_id_health(caller_id: str, 
                     stats: Dict[str, Tuple[int, int]],
                     global_pickup: float,
                     threshold: float = 0.10,
                     min_samples: int = 100) -> bool:
    """
    Check if a caller ID's pickup rate is degraded.
    
    Args:
        caller_id: Caller ID to check
        stats: {caller_id: (connected, dials)}
        global_pickup: Overall pickup rate
        threshold: Relative drop threshold
        min_samples: Minimum dials to check
    
    Returns:
        True if caller ID is degraded
    """
    if caller_id not in stats:
        return False
    
    connected, dials = stats[caller_id]
    if dials < min_samples:
        return False
    
    pickup_rate = connected / dials if dials > 0 else 0
    relative_drop = (global_pickup - pickup_rate) / global_pickup if global_pickup > 0 else 0
    
    return relative_drop > threshold


def hallucination_spike(recent_halluc_rate: float,
                        historical_halluc_rate: float,
                        threshold: float = 0.015,
                        min_samples: int = 50) -> bool:
    """
    Detect hallucination spike.
    
    Args:
        recent_halluc_rate: Recent hallucination rate
        historical_halluc_rate: Historical baseline
        threshold: Absolute increase threshold
        min_samples: Minimum samples
    
    Returns:
        True if spike detected
    """
    increase = recent_halluc_rate - historical_halluc_rate
    return increase > threshold


class CohortAnalyzer:
    """Analyzes performance by cohort and variant."""
    
    def __init__(self):
        self.cohort_stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        self.variant_stats = defaultdict(lambda: [0, 0])
        self.caller_id_stats = defaultdict(lambda: [0, 0])
    
    def add_call(self, cohort_id: str, variant: Dict[str, str], 
                 connected: bool, engaged: bool, kpi: str):
        """Add a call result to statistics."""
        # Update cohort stats
        key = (cohort_id, tuple(sorted(variant.items())))
        if kpi == "pickup_rate":
            self.cohort_stats[cohort_id][key][1] += 1
            if connected:
                self.cohort_stats[cohort_id][key][0] += 1
        elif kpi == "engagement_rate" and connected:
            self.cohort_stats[cohort_id][key][1] += 1
            if engaged:
                self.cohort_stats[cohort_id][key][0] += 1
        
        # Update variant stats by dimension
        for dim, value in variant.items():
            if dim == "prompt_version":
                continue
            
            if kpi == "pickup_rate":
                self.variant_stats[(cohort_id, dim, value)][1] += 1
                if connected:
                    self.variant_stats[(cohort_id, dim, value)][0] += 1
            elif kpi == "engagement_rate" and connected:
                self.variant_stats[(cohort_id, dim, value)][1] += 1
                if engaged:
                    self.variant_stats[(cohort_id, dim, value)][0] += 1
        
        # Update caller ID stats
        caller_id = variant.get("caller_id")
        if caller_id:
            self.caller_id_stats[caller_id][1] += 1
            if connected:
                self.caller_id_stats[caller_id][0] += 1
    
    def get_best_variant(self, cohort_id: str, dimension: str, 
                         candidates: List[str], min_samples: int = 100) -> Optional[str]:
        """Find best variant for a dimension within a cohort."""
        variants = {}
        for value in candidates:
            key = (cohort_id, dimension, value)
            if key in self.variant_stats:
                stats = self.variant_stats[key]
                if stats[1] >= min_samples:
                    variants[value] = (stats[0], stats[1])
        
        if len(variants) < 2:
            return None
        
        return bayesian_winner(variants, min_samples=min_samples)
