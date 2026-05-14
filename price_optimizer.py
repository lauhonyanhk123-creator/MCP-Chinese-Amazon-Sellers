"""
AI-Powered Price Optimization Engine
智能价格优化引擎

This module provides intelligent pricing recommendations based on:
- Competitor price analysis
- Cost structure and margin targets
- Market position strategy (aggressive/balanced/premium)
- Price elasticity and demand patterns
"""

import os
import json
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from database import get_product_profile, get_all_product_profiles


@dataclass
class CompetitorData:
    asin: str
    title: str
    price: float
    rating: Optional[float]
    review_count: int
    seller: str


@dataclass
class PriceRange:
    minimum: float
    maximum: float
    optimal: float
    strategy_applied: str


@dataclass
class PriceRecommendation:
    sku: str
    asin: str
    current_price: float
    cost_usd: float
    competitor_analysis: Dict[str, Any]
    optimal_price: float
    price_range: Dict[str, float]
    recommended_price: float
    strategy: str
    target_margin: float
    expected_margin: float
    profit_per_unit: float
    action: str
    confidence: float
    generated_at: str


@dataclass
class CompetitiveThreat:
    asin: str
    title: str
    current_price: float
    threat_level: str
    price_difference_percent: float
    threat_type: str
    recommended_response: str


class PriceOptimizer:
    """
    AI-powered price optimization engine for cross-border e-commerce.

    Analyzes competitor prices, calculates optimal pricing strategies,
    and generates actionable recommendations.
    """

    def __init__(self):
        self.default_exchange_rate = float(os.getenv("USD_CNY_EXCHANGE_RATE", "7.2"))
        self.default_referral_fee = float(os.getenv("AMAZON_REFERRAL_FEE_PERCENT", "15.0"))
        self.default_fba_fee = float(os.getenv("FBA_FEE_USD", "3.5"))
        self.default_shipping = float(os.getenv("SHIPPING_COST_USD", "2.0"))

    def get_exchange_rate(self) -> float:
        return self.default_exchange_rate

    def analyze_competition(self, asin: str, limit: int = 10) -> Dict[str, Any]:
        """
        Analyze competitor prices for a given ASIN or keyword.

        Args:
            asin: Product ASIN or search keyword
            limit: Maximum number of competitors to analyze

        Returns:
            Dictionary containing competitor analysis data
        """
        competitors = self._fetch_competitor_data(asin, limit)

        if not competitors:
            return {
                "asin": asin,
                "competitors_found": 0,
                "analysis_available": False,
                "message": "No competitor data available"
            }

        prices = [c.price for c in competitors if c.price > 0]

        if not prices:
            return {
                "asin": asin,
                "competitors_found": len(competitors),
                "analysis_available": False,
                "message": "No valid competitor prices found"
            }

        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        median_price = self._calculate_median(prices)

        price_distribution = self._analyze_price_distribution(competitors)

        return {
            "asin": asin,
            "competitors_found": len(competitors),
            "analysis_available": True,
            "competitors": [asdict(c) for c in competitors],
            "price_statistics": {
                "minimum": round(min_price, 2),
                "maximum": round(max_price, 2),
                "average": round(avg_price, 2),
                "median": round(median_price, 2),
                "count": len(prices)
            },
            "price_distribution": price_distribution,
            "market_position": self._determine_market_position(min_price, max_price, avg_price),
            "analyzed_at": datetime.now().isoformat()
        }

    def _fetch_competitor_data(self, asin: str, limit: int) -> List[CompetitorData]:
        """
        Fetch competitor data from Amazon catalog.
        In production, this would call the Amazon API.
        """
        mock_competitors = [
            CompetitorData(
                asin=f"COMP{i:03d}",
                title=f"Similar Product Variant {i} - {asin[:8]}",
                price=round(15.0 + (i * 2.5) + (hash(asin + str(i)) % 100) / 10, 2),
                rating=round(3.5 + (hash(asin + str(i)) % 30) / 10, 1),
                review_count=50 + (hash(asin + str(i)) % 500),
                seller=f"Seller_{(i * 17) % 100}"
            )
            for i in range(1, min(limit + 1, 8))
        ]
        return mock_competitors

    def _calculate_median(self, prices: List[float]) -> float:
        """Calculate median price from list."""
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        if n == 0:
            return 0.0
        if n % 2 == 0:
            return (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2
        return sorted_prices[n // 2]

    def _analyze_price_distribution(self, competitors: List[CompetitorData]) -> Dict[str, Any]:
        """Analyze the distribution of competitor prices."""
        prices = [c.price for c in competitors if c.price > 0]
        if not prices:
            return {"tier": "unknown", "spread_percent": 0}

        min_price = min(prices)
        max_price = max(prices)
        spread_percent = ((max_price - min_price) / min_price * 100) if min_price > 0 else 0

        if spread_percent < 15:
            tier = "stable"
        elif spread_percent < 30:
            tier = "competitive"
        else:
            tier = "fragmented"

        return {
            "tier": tier,
            "spread_percent": round(spread_percent, 2),
            "low_segment_count": sum(1 for p in prices if p <= min(prices) * 1.1),
            "mid_segment_count": sum(1 for p in prices if min(prices) * 1.1 < p <= max(prices) * 0.9),
            "high_segment_count": sum(1 for p in prices if p > max(prices) * 0.9)
        }

    def _determine_market_position(self, min_price: float, max_price: float, avg_price: float) -> Dict[str, Any]:
        """Determine the market position relative to competitors."""
        mid_point = (min_price + max_price) / 2

        if avg_price <= min_price * 1.15:
            position = "budget"
            description = "Price-sensitive segment"
        elif avg_price >= max_price * 0.85:
            position = "premium"
            description = "Quality-focused segment"
        else:
            position = "mid-market"
            description = "Value-focused segment"

        return {
            "position": position,
            "description": description,
            "market_midpoint": round(mid_point, 2),
            "price_gap_to_low": round(((avg_price - min_price) / min_price * 100), 2) if min_price > 0 else 0
        }

    def calculate_optimal_price(
        self,
        cost: float,
        competitor_prices: List[float],
        target_margin: float,
        strategy: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Calculate optimal price based on cost, competition, and strategy.

        Args:
            cost: Product cost in USD
            competitor_prices: List of competitor prices
            target_margin: Target profit margin percentage
            strategy: Pricing strategy - 'aggressive', 'balanced', or 'premium'

        Returns:
            Dictionary containing optimal price calculation
        """
        if not competitor_prices:
            competitor_prices = [cost * 1.5]

        valid_prices = [p for p in competitor_prices if p > 0]
        if not valid_prices:
            valid_prices = [cost * 1.5]

        min_comp = min(valid_prices)
        max_comp = max(valid_prices)
        avg_comp = sum(valid_prices) / len(valid_prices)

        strategy_multipliers = {
            "aggressive": {"price_adjust": 0.95, "margin_adjust": 0.9},
            "balanced": {"price_adjust": 1.0, "margin_adjust": 1.0},
            "premium": {"price_adjust": 1.1, "margin_adjust": 1.1}
        }

        params = strategy_multipliers.get(strategy, strategy_multipliers["balanced"])

        price_floor = max(cost * 1.2, min_comp * 0.92)
        price_ceiling = max_comp * 1.15

        target_price = avg_comp * params["price_adjust"]
        adjusted_target = max(price_floor, min(target_price, price_ceiling))

        adjusted_margin = target_margin * params["margin_adjust"]

        fees = adjusted_target * (self.default_referral_fee / 100) + self.default_fba_fee
        net_after_fees = adjusted_target - cost - self.default_shipping - fees

        if adjusted_target > 0:
            actual_margin = (net_after_fees / adjusted_target) * 100
        else:
            actual_margin = 0

        optimal_price = round(adjusted_target, 2)
        break_even = cost + self.default_shipping + fees

        low_price = round(max(break_even * 1.15, min_comp * 0.95), 2)
        high_price = round(min(break_even * 1.5, max_comp * 1.05), 2)

        return {
            "cost_usd": round(cost, 2),
            "target_margin_percent": target_margin,
            "strategy": strategy,
            "optimal_price": optimal_price,
            "break_even_price": round(break_even, 2),
            "price_range": {
                "minimum": low_price,
                "recommended": optimal_price,
                "maximum": high_price
            },
            "competitor_context": {
                "min_competitor": round(min_comp, 2),
                "avg_competitor": round(avg_comp, 2),
                "max_competitor": round(max_comp, 2)
            },
            "margin_analysis": {
                "target_margin": target_margin,
                "estimated_margin": round(actual_margin, 2),
                "meets_target": actual_margin >= target_margin * 0.85
            },
            "calculated_at": datetime.now().isoformat()
        }

    def get_price_recommendation(
        self,
        sku: str,
        strategy: str = "balanced",
        custom_cost: Optional[float] = None,
        target_margin: Optional[float] = None
    ) -> PriceRecommendation:
        """
        Get comprehensive price recommendation for a SKU.

        Args:
            sku: Product SKU
            strategy: Pricing strategy - 'aggressive', 'balanced', or 'premium'
            custom_cost: Override cost in USD
            target_margin: Target margin percentage

        Returns:
            PriceRecommendation object with full analysis
        """
        profile = get_product_profile(sku)

        if custom_cost:
            cost_usd = custom_cost
        elif profile and profile.get("cost_cny"):
            cost_usd = profile["cost_cny"] / self.get_exchange_rate()
        else:
            cost_usd = 10.0

        if target_margin is None:
            target_margin = 25.0

        asin = sku.replace("SKU", "ASIN")
        competitor_analysis = self.analyze_competition(asin)

        competitor_prices = []
        if competitor_analysis.get("competitors"):
            competitor_prices = [c["price"] for c in competitor_analysis["competitors"] if c["price"] > 0]

        price_calc = self.calculate_optimal_price(cost_usd, competitor_prices, target_margin, strategy)

        current_price = cost_usd * 2.5

        recommended_price = price_calc["optimal_price"]

        diff_from_current = ((recommended_price - current_price) / current_price * 100) if current_price > 0 else 0

        if abs(diff_from_current) < 3:
            action = "MAINTAIN"
        elif diff_from_current > 0:
            action = "INCREASE"
        else:
            action = "DECREASE"

        confidence = self._calculate_recommendation_confidence(
            competitor_analysis, price_calc, target_margin
        )

        return PriceRecommendation(
            sku=sku,
            asin=asin,
            current_price=round(current_price, 2),
            cost_usd=round(cost_usd, 2),
            competitor_analysis=competitor_analysis,
            optimal_price=recommended_price,
            price_range=price_calc["price_range"],
            recommended_price=recommended_price,
            strategy=strategy,
            target_margin=target_margin,
            expected_margin=price_calc["margin_analysis"]["estimated_margin"],
            profit_per_unit=round(recommended_price - price_calc["break_even_price"], 2),
            action=action,
            confidence=confidence,
            generated_at=datetime.now().isoformat()
        )

    def _calculate_recommendation_confidence(
        self,
        competitor_analysis: Dict[str, Any],
        price_calc: Dict[str, Any],
        target_margin: float
    ) -> float:
        """Calculate confidence score for the recommendation."""
        confidence = 0.5

        if competitor_analysis.get("competitors_found", 0) >= 5:
            confidence += 0.2

        if competitor_analysis.get("price_statistics", {}).get("average"):
            confidence += 0.15

        if price_calc["margin_analysis"]["meets_target"]:
            confidence += 0.1

        if target_margin and 15 <= target_margin <= 40:
            confidence += 0.05

        return min(confidence, 0.95)

    def analyze_price_sensitivity(
        self,
        demand: float,
        elasticity: float = -1.5,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Analyze price sensitivity and demand elasticity.

        Args:
            demand: Current demand level (units per day/week)
            elasticity: Price elasticity of demand (typically -0.5 to -3.0)
            current_price: Current price if known

        Returns:
            Dictionary with sensitivity analysis
        """
        if current_price is None:
            current_price = 25.0

        price_changes = [-20, -15, -10, -5, 0, 5, 10, 15, 20]

        sensitivity_curve = []
        for pct_change in price_changes:
            price_factor = 1 + (pct_change / 100)
            new_price = current_price * price_factor

            quantity_change = elasticity * pct_change
            new_demand = demand * (1 + quantity_change / 100)
            new_demand = max(0, new_demand)

            revenue_current = current_price * demand
            revenue_new = new_price * new_demand
            revenue_change = ((revenue_new - revenue_current) / revenue_current * 100) if revenue_current > 0 else 0

            sensitivity_curve.append({
                "price_change_percent": pct_change,
                "new_price": round(new_price, 2),
                "expected_demand": round(new_demand, 2),
                "revenue_change_percent": round(revenue_change, 2),
                "optimal_for": "revenue" if revenue_change > 0 else "volume"
            })

        optimal_price_for_revenue = current_price * (1 + (1 / abs(elasticity))) if elasticity < 0 else current_price

        return {
            "current_demand": demand,
            "current_price": current_price,
            "elasticity": elasticity,
            "sensitivity_curve": sensitivity_curve,
            "optimal_price_for_revenue": round(optimal_price_for_revenue, 2),
            "elasticity_interpretation": self._interpret_elasticity(elasticity),
            "recommendations": self._generate_sensitivity_recommendations(elasticity, demand)
        }

    def _interpret_elasticity(self, elasticity: float) -> str:
        """Interpret elasticity value."""
        abs_val = abs(elasticity)
        if abs_val < 0.8:
            return "inelastic - Price changes have minimal impact on demand"
        elif abs_val < 1.5:
            return "moderately elastic - Some sensitivity to price changes"
        elif abs_val < 2.5:
            return "highly elastic - Strong response to price changes"
        else:
            return "very highly elastic - Extreme sensitivity to pricing"

    def _generate_sensitivity_recommendations(
        self,
        elasticity: float,
        demand: float
    ) -> List[str]:
        """Generate recommendations based on elasticity."""
        recommendations = []

        if abs(elasticity) < 1:
            recommendations.append("Consider raising prices - demand is relatively stable")
            recommendations.append("Focus on value propositions rather than discounting")
        elif abs(elasticity) < 2:
            recommendations.append("Price optimization can significantly impact revenue")
            recommendations.append("Test price points in small increments")
        else:
            recommendations.append("High price sensitivity - be cautious with price increases")
            recommendations.append("Competitive pricing is crucial for this product")
            recommendations.append("Monitor competitor prices closely")

        if demand < 10:
            recommendations.append("Low current demand - consider promotional pricing")
        elif demand > 100:
            recommendations.append("High volume product - even small price changes have large impact")

        return recommendations

    def detect_competitive_threats(
        self,
        asin: str,
        current_price: Optional[float] = None,
        threshold_percent: float = 15.0
    ) -> List[CompetitiveThreat]:
        """
        Detect competitive threats from low-priced competitors.

        Args:
            asin: Product ASIN to analyze
            current_price: Your current selling price
            threshold_percent: Price difference threshold for threat detection

        Returns:
            List of CompetitiveThreat objects
        """
        if current_price is None:
            current_price = 25.0

        competitor_analysis = self.analyze_competition(asin)

        threats = []

        if not competitor_analysis.get("competitors"):
            return []

        for comp in competitor_analysis["competitors"]:
            if comp["price"] <= 0:
                continue

            price_diff_pct = ((comp["price"] - current_price) / current_price * 100) if current_price > 0 else 0

            if price_diff_pct <= -threshold_percent:
                threat_level = "critical" if price_diff_pct <= -25 else "high" if price_diff_pct <= -20 else "medium"

                if threat_level == "critical":
                    threat_type = "price_undercut"
                    response = "Consider matching or beating their price, or differentiate through value-added services"
                elif threat_level == "high":
                    threat_type = "price_gap"
                    response = "Review your cost structure and consider selective price adjustments"
                else:
                    threat_type = "competitive_pressure"
                    response = "Monitor the situation and prepare competitive response if needed"

                if comp.get("rating") and comp["rating"] >= 4.5:
                    threat_level = "critical"
                    threat_type = "low_price_high_rating"
                    response = "URGENT: High-rated competitor with significantly lower price"

                threats.append(CompetitiveThreat(
                    asin=comp["asin"],
                    title=comp["title"],
                    current_price=comp["price"],
                    threat_level=threat_level,
                    price_difference_percent=round(price_diff_pct, 2),
                    threat_type=threat_type,
                    recommended_response=response
                ))

        threats.sort(key=lambda x: abs(x.price_difference_percent), reverse=True)

        return threats

    def calculate_multi_sku_recommendations(
        self,
        skus: List[str],
        strategy: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Calculate price recommendations for multiple SKUs.

        Args:
            skus: List of SKU identifiers
            strategy: Pricing strategy for all SKUs

        Returns:
            Dictionary with recommendations for all SKUs
        """
        recommendations = []

        for sku in skus:
            rec = self.get_price_recommendation(sku, strategy=strategy)
            recommendations.append(asdict(rec))

        total_current_value = sum(r["current_price"] for r in recommendations)
        total_recommended_value = sum(r["recommended_price"] for r in recommendations)
        avg_margin = sum(r["expected_margin"] for r in recommendations) / len(recommendations) if recommendations else 0

        return {
            "sku_count": len(recommendations),
            "strategy": strategy,
            "recommendations": recommendations,
            "summary": {
                "total_current_value": round(total_current_value, 2),
                "total_recommended_value": round(total_recommended_value, 2),
                "average_expected_margin": round(avg_margin, 2),
                "action_required_count": sum(1 for r in recommendations if r["action"] != "MAINTAIN")
            },
            "generated_at": datetime.now().isoformat()
        }


optimizer = PriceOptimizer()


def get_price_recommendation(sku: str, strategy: str = "balanced") -> Dict[str, Any]:
    """Convenience function for getting price recommendation."""
    rec = optimizer.get_price_recommendation(sku, strategy=strategy)
    return asdict(rec)


def analyze_competitor_prices(asin: str, limit: int = 10) -> Dict[str, Any]:
    """Convenience function for competitor analysis."""
    return optimizer.analyze_competition(asin, limit=limit)


def detect_threats(asin: str, current_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Convenience function for threat detection."""
    threats = optimizer.detect_competitive_threats(asin, current_price=current_price)
    return [asdict(t) for t in threats]
