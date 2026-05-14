"""
历史数据分析引擎 - 用于趋势分析和预测
Historical Data Analytics Engine - For trend analysis and forecasting
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from database import get_latest_snapshot, get_snapshots, save_snapshot


@dataclass
class TrendResult:
    direction: str
    change_percent: float
    values: list[float]
    dates: list[str]
    avg_value: float
    min_value: float
    max_value: float
    volatility: float


@dataclass
class StockoutPrediction:
    sku: str
    current_stock: int
    sales_velocity: float
    days_until_stockout: float
    recommended_reorder: int
    risk_level: str
    confidence: float


@dataclass
class GrowthRate:
    metric: str
    current_value: float
    previous_value: float
    growth_rate: float
    period_days: int
    is_positive: bool
    trend: str


class HistoricalDataAnalyzer:
    """Analyzer for historical data trends and forecasting"""

    def __init__(self):
        self.snapshot_types = ['inventory', 'orders', 'reviews', 'competitors']

    def calculate_trends(self, metric: str, days: int = 30) -> TrendResult:
        """Calculate trends for a specific metric
        
        Args:
            metric: Metric name ('low_stock_count', 'pending_orders', 'revenue', etc.)
            days: Number of days to analyze
        
        Returns:
            TrendResult with trend analysis
        """
        snapshots = get_snapshots('inventory', start_date=None, end_date=None)

        if not snapshots:
            return self._empty_trend_result(metric)

        snapshots = sorted(snapshots, key=lambda x: x['snapshot_date'])
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        snapshots = [s for s in snapshots if s['snapshot_date'] >= cutoff_date]

        if len(snapshots) < 2:
            return self._empty_trend_result(metric)

        values = []
        dates = []

        for snapshot in snapshots:
            data = snapshot.get('data', {})
            value = self._extract_metric_value(data, metric)
            if value is not None:
                values.append(value)
                dates.append(snapshot['snapshot_date'])

        if len(values) < 2:
            return self._empty_trend_result(metric)

        first_val = values[0]
        last_val = values[-1]

        if first_val == 0:
            change_percent = 100.0 if last_val > 0 else 0.0
        else:
            change_percent = ((last_val - first_val) / first_val) * 100

        if change_percent > 5:
            direction = 'up'
        elif change_percent < -5:
            direction = 'down'
        else:
            direction = 'stable'

        avg_value = sum(values) / len(values)
        min_value = min(values)
        max_value = max(values)
        variance = sum((v - avg_value) ** 2 for v in values) / len(values)
        volatility = math.sqrt(variance) / avg_value if avg_value > 0 else 0

        return TrendResult(
            direction=direction,
            change_percent=round(change_percent, 2),
            values=values,
            dates=dates,
            avg_value=round(avg_value, 2),
            min_value=min_value,
            max_value=max_value,
            volatility=round(volatility, 3)
        )

    def _extract_metric_value(self, data: dict, metric: str) -> float | None:
        """Extract a specific metric value from snapshot data"""
        if metric in data:
            value = data[metric]
            return float(value) if value is not None else None

        for key, value in data.items():
            if metric in key.lower():
                return float(value) if value is not None else None

        return None

    def _empty_trend_result(self, metric: str) -> TrendResult:
        """Return an empty trend result"""
        return TrendResult(
            direction='stable',
            change_percent=0.0,
            values=[],
            dates=[],
            avg_value=0.0,
            min_value=0.0,
            max_value=0.0,
            volatility=0.0
        )

    def predict_stockout(
        self,
        sku: str,
        current_stock: int,
        sales_velocity: float,
        lead_time_days: int = 14
    ) -> StockoutPrediction:
        """Predict when a SKU will run out of stock
        
        Args:
            sku: Product SKU
            current_stock: Current inventory level
            sales_velocity: Average units sold per day
            lead_time_days: Days needed to reorder (default: 14)
        
        Returns:
            StockoutPrediction with forecast
        """
        if sales_velocity <= 0:
            return StockoutPrediction(
                sku=sku,
                current_stock=current_stock,
                sales_velocity=sales_velocity,
                days_until_stockout=float('inf'),
                recommended_reorder=0,
                risk_level='low',
                confidence=0.0
            )

        days_until_stockout = current_stock / sales_velocity

        reorder_buffer = max(lead_time_days * 1.5, 7)
        safety_stock = sales_velocity * lead_time_days
        recommended_reorder = int(safety_stock + (current_stock * 0.3))

        if days_until_stockout <= 3:
            risk_level = 'critical'
        elif days_until_stockout <= lead_time_days:
            risk_level = 'high'
        elif days_until_stockout <= lead_time_days * 2:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        confidence = self._calculate_prediction_confidence(sales_velocity, current_stock)

        return StockoutPrediction(
            sku=sku,
            current_stock=current_stock,
            sales_velocity=sales_velocity,
            days_until_stockout=round(days_until_stockout, 1),
            recommended_reorder=recommended_reorder,
            risk_level=risk_level,
            confidence=confidence
        )

    def _calculate_prediction_confidence(
        self,
        sales_velocity: float,
        current_stock: int
    ) -> float:
        """Calculate confidence level for stockout prediction"""
        if sales_velocity <= 0 or current_stock <= 0:
            return 0.0

        coefficient_of_variation = 0.3

        historical_data = get_snapshots('orders',
            start_date=(datetime.now() - timedelta(days=30)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )
        if len(historical_data) >= 7:
            velocity_values = []
            for snapshot in historical_data[-7:]:
                data = snapshot.get('data', {})
                orders = data.get('order_count', data.get('total_orders', 0))
                velocity_values.append(float(orders))

            if velocity_values:
                mean = sum(velocity_values) / len(velocity_values)
                if mean > 0:
                    variance = sum((v - mean) ** 2 for v in velocity_values) / len(velocity_values)
                    std_dev = math.sqrt(variance)
                    coefficient_of_variation = std_dev / mean if mean > 0 else 0.3

        confidence = max(0.0, min(1.0, 1.0 - coefficient_of_variation))

        return round(confidence, 2)

    def calculate_growth_rate(
        self,
        metric: str,
        period: int = 30
    ) -> GrowthRate:
        """Calculate growth rate for a metric over a period
        
        Args:
            metric: Metric name
            period: Period in days (compares to same period before)
        
        Returns:
            GrowthRate with analysis
        """
        end_date = datetime.now().date().isoformat()
        start_date = (datetime.now() - timedelta(days=period)).date().isoformat()
        prev_end_date = (datetime.now() - timedelta(days=period)).date().isoformat()
        prev_start_date = (datetime.now() - timedelta(days=period * 2)).date().isoformat()

        current_snapshots = get_snapshots('inventory', start_date, end_date)
        previous_snapshots = get_snapshots('inventory', prev_start_date, prev_end_date)

        current_value = self._calculate_period_average(current_snapshots, metric)
        previous_value = self._calculate_period_average(previous_snapshots, metric)

        if previous_value == 0:
            growth_rate = 100.0 if current_value > 0 else 0.0
        else:
            growth_rate = ((current_value - previous_value) / previous_value) * 100

        is_positive = growth_rate > 0

        if metric in ['low_stock_count', 'negative_reviews']:
            trend = 'improving' if growth_rate < 0 else 'worsening'
            is_positive = not is_positive
        elif growth_rate > 10:
            trend = 'growing'
        elif growth_rate < -10:
            trend = 'declining'
        else:
            trend = 'stable'

        return GrowthRate(
            metric=metric,
            current_value=round(current_value, 2),
            previous_value=round(previous_value, 2),
            growth_rate=round(growth_rate, 2),
            period_days=period,
            is_positive=is_positive,
            trend=trend
        )

    def _calculate_period_average(
        self,
        snapshots: list[dict],
        metric: str
    ) -> float:
        """Calculate average value for a metric across snapshots"""
        if not snapshots:
            return 0.0

        values = []
        for snapshot in snapshots:
            data = snapshot.get('data', {})
            value = self._extract_metric_value(data, metric)
            if value is not None:
                values.append(value)

        return sum(values) / len(values) if values else 0.0

    def get_comparative_stats(
        self,
        current_period: int = 7,
        previous_period: int = 7
    ) -> dict[str, Any]:
        """Get comparative statistics between current and previous period
        
        Args:
            current_period: Days in current period (default: 7)
            previous_period: Days in previous period (default: 7)
        
        Returns:
            Dictionary with comparative statistics
        """
        now = datetime.now()
        current_end = now.date().isoformat()
        current_start = (now - timedelta(days=current_period)).date().isoformat()

        previous_end = (now - timedelta(days=current_period)).date().isoformat()
        previous_start = (now - timedelta(days=current_period + previous_period)).date().isoformat()

        stats = {}

        for snapshot_type in ['inventory', 'orders', 'reviews']:
            current_data = get_snapshots(snapshot_type, current_start, current_end)
            previous_data = get_snapshots(snapshot_type, previous_start, previous_end)

            current_metrics = self._aggregate_metrics(current_data)
            previous_metrics = self._aggregate_metrics(previous_data)

            comparison = {}
            for key in current_metrics:
                curr = current_metrics[key]
                prev = previous_metrics.get(key, 0)

                if prev == 0:
                    change = 100.0 if curr > 0 else 0.0
                else:
                    change = ((curr - prev) / prev) * 100

                comparison[key] = {
                    'current': round(curr, 2),
                    'previous': round(prev, 2),
                    'change_percent': round(change, 2),
                    'change_direction': 'up' if change > 5 else ('down' if change < -5 else 'stable')
                }

            stats[snapshot_type] = comparison

        return stats

    def _aggregate_metrics(self, snapshots: list[dict]) -> dict[str, float]:
        """Aggregate metrics from multiple snapshots"""
        metrics = {
            'count': len(snapshots),
            'total_value': 0.0,
            'avg_value': 0.0
        }

        values = []
        for snapshot in snapshots:
            data = snapshot.get('data', {})
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    values.append(float(value))
                    if key not in metrics:
                        metrics[key] = 0.0
                    metrics[key] += float(value)

        if values:
            metrics['total_value'] = sum(values)
            metrics['avg_value'] = sum(values) / len(values)

        return metrics

    def generate_forecast(
        self,
        metric: str,
        days_ahead: int = 7
    ) -> dict[str, Any]:
        """Generate simple forecast for a metric
        
        Args:
            metric: Metric to forecast
            days_ahead: Number of days to forecast
        
        Returns:
            Dictionary with forecast data
        """
        trend = self.calculate_trends(metric, days=14)

        if not trend.values:
            return {
                'metric': metric,
                'forecast': [],
                'confidence': 0.0,
                'method': 'no_data'
            }

        forecast_values = []
        last_value = trend.values[-1] if trend.values else 0
        avg_change = (trend.values[-1] - trend.values[0]) / len(trend.values) if len(trend.values) > 1 else 0

        dates = []
        for i in range(1, days_ahead + 1):
            forecast_date = datetime.now() + timedelta(days=i)
            dates.append(forecast_date.date().isoformat())

            predicted = last_value + (avg_change * i)

            margin = trend.volatility * last_value * math.sqrt(i)
            confidence = max(0.1, 1.0 - (i * 0.1))

            forecast_values.append({
                'date': dates[-1],
                'predicted_value': round(predicted, 2),
                'upper_bound': round(predicted + margin, 2),
                'lower_bound': round(max(0, predicted - margin), 2),
                'confidence': round(confidence, 2)
            })

        return {
            'metric': metric,
            'forecast': forecast_values,
            'confidence': round(1.0 - trend.volatility, 2) if trend.volatility < 1.0 else 0.5,
            'method': 'linear_regression',
            'avg_daily_change': round(avg_change, 3),
            'current_value': last_value
        }

    def calculate_days_of_supply(self, sku: str) -> dict[str, Any]:
        """Calculate days of supply for a SKU based on sales velocity
        
        Args:
            sku: Product SKU
        
        Returns:
            Dictionary with days of supply info
        """
        from database import get_latest_snapshot

        latest = get_latest_snapshot('inventory')
        current_stock = 0

        if latest:
            data = latest.get('data', {})
            products = data.get('products', data.get('inventory', []))
            for product in products:
                if product.get('sku') == sku:
                    current_stock = product.get('current_stock', 0)
                    break

        order_snapshots = get_snapshots('orders',
            start_date=(datetime.now() - timedelta(days=30)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )

        total_orders = 0
        for snapshot in order_snapshots:
            snapshot_data = snapshot.get('data', {})
            total_orders += snapshot_data.get('order_count',
                           snapshot_data.get('total_orders', 0))

        avg_daily_orders = total_orders / 30 if total_orders > 0 else 0

        if avg_daily_orders > 0:
            days_of_supply = current_stock / avg_daily_orders
        else:
            days_of_supply = float('inf')

        return {
            'sku': sku,
            'current_stock': current_stock,
            'avg_daily_demand': round(avg_daily_orders, 2),
            'days_of_supply': round(days_of_supply, 1) if days_of_supply != float('inf') else float('inf'),
            'status': 'critical' if days_of_supply < 7 else ('warning' if days_of_supply < 14 else 'good')
        }

    def predict_stockout_with_velocity(
        self,
        sku: str,
        current_stock: int,
        sales_velocity: float,
        lead_time_days: int = 14
    ) -> StockoutPrediction:
        """Predict when a SKU will run out of stock based on sales velocity
        
        Args:
            sku: Product SKU
            current_stock: Current inventory level
            sales_velocity: Units sold per day
            lead_time_days: Days needed to reorder (default: 14)
        
        Returns:
            StockoutPrediction with forecast
        """
        if sales_velocity <= 0:
            return StockoutPrediction(
                sku=sku,
                current_stock=current_stock,
                sales_velocity=sales_velocity,
                days_until_stockout=float('inf'),
                recommended_reorder=0,
                risk_level='low',
                confidence=0.0
            )

        days_until_stockout = current_stock / sales_velocity

        safety_stock = sales_velocity * lead_time_days * 0.5
        recommended_reorder = int(safety_stock + (current_stock * 0.5) + (sales_velocity * lead_time_days))

        if days_until_stockout <= 3:
            risk_level = 'critical'
        elif days_until_stockout <= lead_time_days:
            risk_level = 'high'
        elif days_until_stockout <= lead_time_days * 2:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        confidence = self._calculate_prediction_confidence(sales_velocity, current_stock)

        return StockoutPrediction(
            sku=sku,
            current_stock=current_stock,
            sales_velocity=sales_velocity,
            days_until_stockout=round(days_until_stockout, 1),
            recommended_reorder=recommended_reorder,
            risk_level=risk_level,
            confidence=confidence
        )

    def calculate_reorder_quantity(
        self,
        sku: str,
        sales_velocity: float,
        lead_time: int = 14,
        target_days: int = 30
    ) -> dict[str, Any]:
        """Calculate optimal reorder quantity
        
        Args:
            sku: Product SKU
            sales_velocity: Units sold per day
            lead_time: Lead time in days
            target_days: Target days of supply to maintain
        
        Returns:
            Dictionary with reorder recommendation
        """
        if sales_velocity <= 0:
            return {
                'sku': sku,
                'reorder_quantity': 0,
                'safety_stock': 0,
                'reorder_point': 0,
                'urgency': 'none',
                'explanation': 'No sales data available'
            }

        safety_stock = int(sales_velocity * lead_time * 0.5)
        target_stock = int(sales_velocity * target_days)
        reorder_point = int(sales_velocity * lead_time)

        urgency = 'critical' if lead_time >= 14 else ('high' if lead_time >= 7 else 'medium')

        return {
            'sku': sku,
            'reorder_quantity': target_stock,
            'safety_stock': safety_stock,
            'reorder_point': reorder_point,
            'lead_time_days': lead_time,
            'target_days_supply': target_days,
            'urgency': urgency,
            'daily_velocity': round(sales_velocity, 2)
        }

    def get_inventory_health_score(self, products: list[dict] = None) -> dict[str, Any]:
        """Calculate overall inventory health score
        
        Args:
            products: Optional list of products to analyze
        
        Returns:
            Dictionary with health score and breakdown
        """
        snapshots = get_snapshots('inventory',
            start_date=(datetime.now() - timedelta(days=30)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )

        if not products:
            latest = get_latest_snapshot('inventory')
            if latest:
                products = latest.get('data', {}).get('products', [])

        total_score = 0
        max_score = 100
        factors = {}

        if products:
            critical_count = sum(1 for p in products if p.get('current_stock', 0) <= 0)
            warning_count = sum(1 for p in products if 0 < p.get('current_stock', 0) <= (p.get('threshold', 10)))
            healthy_count = sum(1 for p in products if p.get('current_stock', 0) > (p.get('threshold', 10)))
            total_products = len(products)

            health_ratio = healthy_count / total_products if total_products > 0 else 0
            if health_ratio >= 0.8:
                factors['stock_levels'] = {'score': 30, 'status': 'good', 'detail': f'{healthy_count}/{total_products} healthy'}
                total_score += 30
            elif health_ratio >= 0.5:
                factors['stock_levels'] = {'score': 15, 'status': 'warning', 'detail': f'{healthy_count}/{total_products} healthy'}
                total_score += 15
            else:
                factors['stock_levels'] = {'score': 0, 'status': 'critical', 'detail': f'{healthy_count}/{total_products} healthy'}

            if critical_count == 0:
                factors['critical_items'] = {'score': 25, 'status': 'good'}
                total_score += 25
            elif critical_count <= 2:
                factors['critical_items'] = {'score': 10, 'status': 'warning'}
                total_score += 10
            else:
                factors['critical_items'] = {'score': 0, 'status': 'critical'}
        else:
            factors['stock_levels'] = {'score': 0, 'status': 'unknown', 'detail': 'No products'}
            factors['critical_items'] = {'score': 0, 'status': 'unknown'}

        low_stock_trend = self.calculate_trends('low_stock_count', days=14)
        if low_stock_trend.direction == 'down':
            factors['trend'] = {'score': 20, 'status': 'improving'}
            total_score += 20
        elif low_stock_trend.direction == 'stable':
            factors['trend'] = {'score': 10, 'status': 'stable'}
            total_score += 10
        else:
            factors['trend'] = {'score': 0, 'status': 'worsening'}

        snapshot_frequency = len(snapshots)
        if snapshot_frequency >= 20:
            factors['data_quality'] = {'score': 25, 'status': 'good'}
            total_score += 25
        elif snapshot_frequency >= 10:
            factors['data_quality'] = {'score': 15, 'status': 'adequate'}
            total_score += 15
        else:
            factors['data_quality'] = {'score': 5, 'status': 'insufficient'}
            total_score += 5

        if total_score >= 70:
            status = 'good'
        elif total_score >= 40:
            status = 'moderate'
        else:
            status = 'needs_attention'

        return {
            'score': total_score,
            'max_score': max_score,
            'status': status,
            'factors': factors,
            'percentage': round((total_score / max_score) * 100, 1)
        }

    def identify_risk_products(self, threshold_days: int = 14) -> list[dict[str, Any]]:
        """Identify products at risk of stockout
        
        Args:
            threshold_days: Days threshold for risk identification
        
        Returns:
            List of at-risk products with details
        """
        risk_products = []

        order_snapshots = get_snapshots('orders',
            start_date=(datetime.now() - timedelta(days=30)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )

        total_orders = 0
        for snapshot in order_snapshots:
            snapshot_data = snapshot.get('data', {})
            total_orders += snapshot_data.get('order_count',
                           snapshot_data.get('total_orders', 0))

        avg_daily_velocity = total_orders / 30 if total_orders > 0 else 1

        latest = get_latest_snapshot('inventory')
        if latest:
            products = latest.get('data', {}).get('products', [])

            for product in products:
                sku = product.get('sku', 'Unknown')
                current_stock = product.get('current_stock', 0)

                days_until_stockout = current_stock / avg_daily_velocity if avg_daily_velocity > 0 else float('inf')

                if days_until_stockout <= threshold_days:
                    if days_until_stockout <= 3:
                        risk_level = 'critical'
                    elif days_until_stockout <= 7:
                        risk_level = 'high'
                    elif days_until_stockout <= 14:
                        risk_level = 'medium'
                    else:
                        risk_level = 'low'

                    risk_products.append({
                        'sku': sku,
                        'product_name': product.get('product_name', 'Unknown'),
                        'current_stock': current_stock,
                        'days_until_stockout': round(days_until_stockout, 1),
                        'risk_level': risk_level,
                        'predicted_stockout_date': (datetime.now() + timedelta(days=int(days_until_stockout))).date().isoformat() if days_until_stockout != float('inf') else None,
                        'recommended_reorder': int(avg_daily_velocity * 30),
                        'urgency': 'immediate' if risk_level == 'critical' else ('soon' if risk_level in ['high', 'medium'] else 'normal')
                    })

        risk_products.sort(key=lambda x: (
            0 if x['risk_level'] == 'critical' else
            1 if x['risk_level'] == 'high' else
            2 if x['risk_level'] == 'medium' else 3,
            x['days_until_stockout']
        ))

        return risk_products


analyzer = HistoricalDataAnalyzer()


@dataclass
class PriceChangeEvent:
    asin: str
    change_type: str
    previous_price: float
    new_price: float
    change_percent: float
    date: str
    severity: str


@dataclass
class MarketPosition:
    asin: str
    current_price: float
    price_rank: int
    total_competitors: int
    percentile: float
    price_distance_from_lowest: float
    price_distance_from_highest: float
    relative_position: str


@dataclass
class TrendPrediction:
    asin: str
    direction: str
    confidence: float
    predicted_price_7d: float
    predicted_price_14d: float
    predicted_price_30d: float
    factors: list[str]


class CompetitorAnalyzer:
    """Analyzer for competitor price trends and market positioning"""

    def __init__(self):
        self.price_history: dict[str, list[dict]] = {}
        self.alert_threshold_percent = 10.0
        self.min_history_for_trend = 7

    def track_price_changes(self, asin: str, days: int = 90) -> list[PriceChangeEvent]:
        """Track price changes for a specific ASIN over time
        
        Args:
            asin: Amazon ASIN to track
            days: Number of days to analyze
        
        Returns:
            List of PriceChangeEvent objects
        """
        snapshots = get_snapshots('competitors',
            start_date=(datetime.now() - timedelta(days=days)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )

        if asin not in self.price_history:
            self.price_history[asin] = []

        price_events = []
        prev_price = None

        for snapshot in sorted(snapshots, key=lambda x: x['snapshot_date']):
            data = snapshot.get('data', {})
            competitors = data.get('competitors', [])

            for comp in competitors:
                if comp.get('asin') == asin or comp.get('asin', '').startswith(asin[:10]):
                    current_price = comp.get('price')
                    if current_price and current_price > 0:
                        snapshot_date = snapshot['snapshot_date']

                        self.price_history[asin].append({
                            'date': snapshot_date,
                            'price': current_price
                        })

                        if prev_price is not None and prev_price != current_price:
                            change_percent = ((current_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0

                            if abs(change_percent) >= 1.0:
                                change_type = 'increase' if change_percent > 0 else 'decrease'

                                severity = 'minor'
                                if abs(change_percent) >= 20:
                                    severity = 'major'
                                elif abs(change_percent) >= 10:
                                    severity = 'moderate'

                                price_events.append(PriceChangeEvent(
                                    asin=asin,
                                    change_type=change_type,
                                    previous_price=prev_price,
                                    new_price=current_price,
                                    change_percent=round(change_percent, 2),
                                    date=snapshot_date,
                                    severity=severity
                                ))

                        prev_price = current_price
                        break

        return price_events

    def identify_price_trends(self, asin: str) -> dict[str, Any]:
        """Identify price trend direction for an ASIN
        
        Args:
            asin: Amazon ASIN to analyze
        
        Returns:
            Dictionary with trend analysis
        """
        if asin not in self.price_history or len(self.price_history[asin]) < self.min_history_for_trend:
            self.track_price_changes(asin, days=30)

        history = self.price_history.get(asin, [])

        if len(history) < 3:
            return {
                'asin': asin,
                'trend': 'unknown',
                'direction': 'stable',
                'change_percent': 0,
                'volatility': 0,
                'confidence': 0
            }

        prices = [h['price'] for h in history]
        dates = [h['date'] for h in history]

        first_price = prices[0]
        last_price = prices[-1]
        overall_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0

        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        volatility = (math.sqrt(variance) / avg_price * 100) if avg_price > 0 else 0

        recent_prices = prices[-7:] if len(prices) >= 7 else prices
        if len(recent_prices) >= 2:
            recent_trend = ((recent_prices[-1] - recent_prices[0]) / recent_prices[0]) * 100 if recent_prices[0] > 0 else 0
        else:
            recent_trend = 0

        if recent_trend > 5:
            direction = 'increasing'
        elif recent_trend < -5:
            direction = 'decreasing'
        else:
            direction = 'stable'

        if abs(overall_change) < 5:
            trend = 'stable'
        elif abs(overall_change) >= 20:
            trend = 'volatile'
        else:
            trend = 'moderate'

        confidence = min(1.0, len(history) / 30)

        return {
            'asin': asin,
            'trend': trend,
            'direction': direction,
            'change_percent': round(overall_change, 2),
            'recent_change_percent': round(recent_trend, 2),
            'volatility': round(volatility, 2),
            'current_price': last_price,
            'avg_price': round(avg_price, 2),
            'min_price': min(prices),
            'max_price': max(prices),
            'data_points': len(history),
            'confidence': round(confidence, 2),
            'dates': dates,
            'prices': prices
        }

    def detect_competitive_movements(self, asins: list[str]) -> list[dict[str, Any]]:
        """Detect significant competitive movements across multiple ASINs
        
        Args:
            asins: List of ASINs to analyze
        
        Returns:
            List of detected movements with details
        """
        movements = []

        for asin in asins:
            price_changes = self.track_price_changes(asin, days=14)

            for event in price_changes:
                if event.severity in ['moderate', 'major']:
                    movements.append({
                        'asin': event.asin,
                        'type': event.change_type,
                        'severity': event.severity,
                        'previous_price': event.previous_price,
                        'new_price': event.new_price,
                        'change_percent': event.change_percent,
                        'date': event.date,
                        'description': self._get_movement_description(event)
                    })

        movements.sort(key=lambda x: (
            0 if x['severity'] == 'major' else 1,
            abs(x['change_percent']),
            x['date']
        ), reverse=True)

        return movements[:20]

    def _get_movement_description(self, event: PriceChangeEvent) -> str:
        """Generate description for a price movement event"""
        if event.change_type == 'increase':
            if event.severity == 'major':
                return f"Major price increase of {abs(event.change_percent):.1f}%"
            else:
                return f"Price increased by {abs(event.change_percent):.1f}%"
        elif event.severity == 'major':
            return f"Major price drop of {abs(event.change_percent):.1f}% - potential price war"
        else:
            return f"Price decreased by {abs(event.change_percent):.1f}%"

    def calculate_market_position(self, asin: str, competitors: list[dict]) -> MarketPosition:
        """Calculate market position for an ASIN among competitors
        
        Args:
            asin: Target ASIN
            competitors: List of competitor data with prices
        
        Returns:
            MarketPosition object with positioning details
        """
        prices = []
        asin_price = None

        for comp in competitors:
            price = comp.get('price')
            if price and price > 0:
                prices.append(price)
                if comp.get('asin') == asin:
                    asin_price = price

        if not prices or asin_price is None:
            return MarketPosition(
                asin=asin,
                current_price=0,
                price_rank=0,
                total_competitors=0,
                percentile=0,
                price_distance_from_lowest=0,
                price_distance_from_highest=0,
                relative_position='unknown'
            )

        prices.sort()
        total = len(prices)
        rank = sum(1 for p in prices if p < asin_price) + 1
        percentile = ((total - rank + 1) / total) * 100 if total > 0 else 0

        lowest_price = min(prices)
        highest_price = max(prices)

        distance_from_lowest = ((asin_price - lowest_price) / lowest_price * 100) if lowest_price > 0 else 0
        distance_from_highest = ((highest_price - asin_price) / highest_price * 100) if highest_price > 0 else 0

        if percentile >= 75:
            position = 'premium'
        elif percentile >= 50:
            position = 'upper_mid'
        elif percentile >= 25:
            position = 'lower_mid'
        else:
            position = 'budget'

        return MarketPosition(
            asin=asin,
            current_price=asin_price,
            price_rank=rank,
            total_competitors=total,
            percentile=round(percentile, 1),
            price_distance_from_lowest=round(distance_from_lowest, 2),
            price_distance_from_highest=round(distance_from_highest, 2),
            relative_position=position
        )

    def predict_price_movements(self, asin: str) -> TrendPrediction:
        """Predict future price movements for an ASIN
        
        Args:
            asin: Amazon ASIN to predict
        
        Returns:
            TrendPrediction with forecast
        """
        trend_data = self.identify_price_trends(asin)

        if trend_data['confidence'] < 0.3:
            return TrendPrediction(
                asin=asin,
                direction='unknown',
                confidence=0,
                predicted_price_7d=trend_data.get('current_price', 0),
                predicted_price_14d=trend_data.get('current_price', 0),
                predicted_price_30d=trend_data.get('current_price', 0),
                factors=['Insufficient data for prediction']
            )

        current_price = trend_data.get('current_price', 0)
        direction = trend_data['direction']
        volatility = trend_data.get('volatility', 0) / 100

        factors = []

        if direction == 'increasing':
            daily_rate = trend_data.get('recent_change_percent', 0) / 7
            predicted_7d = current_price * (1 + (daily_rate / 100) * 7)
            predicted_14d = current_price * (1 + (daily_rate / 100) * 14)
            predicted_30d = current_price * (1 + (daily_rate / 100) * 30)
            factors.append('Upward momentum detected')
        elif direction == 'decreasing':
            daily_rate = trend_data.get('recent_change_percent', 0) / 7
            predicted_7d = current_price * (1 + (daily_rate / 100) * 7)
            predicted_14d = current_price * (1 + (daily_rate / 100) * 14)
            predicted_30d = current_price * (1 + (daily_rate / 100) * 30)
            factors.append('Downward pressure detected')
        else:
            margin = volatility * current_price
            predicted_7d = current_price
            predicted_14d = current_price
            predicted_30d = current_price
            factors.append('Price is stable')

        if volatility > 20:
            factors.append('High volatility may cause unpredictable movements')
        elif volatility < 5:
            factors.append('Low volatility suggests stable pricing')

        avg_price = trend_data.get('avg_price', current_price)
        if current_price > avg_price * 1.1:
            factors.append('Price above average - potential resistance')
        elif current_price < avg_price * 0.9:
            factors.append('Price below average - room for increase')

        confidence = trend_data['confidence'] * (1 - min(volatility, 0.5))

        return TrendPrediction(
            asin=asin,
            direction=direction,
            confidence=round(confidence, 2),
            predicted_price_7d=round(predicted_7d, 2),
            predicted_price_14d=round(predicted_14d, 2),
            predicted_price_30d=round(predicted_30d, 2),
            factors=factors
        )

    def get_price_alerts(self, asins: list[str]) -> list[dict[str, Any]]:
        """Get significant price change alerts across all tracked ASINs
        
        Args:
            asins: List of ASINs to check
        
        Returns:
            List of significant alerts
        """
        alerts = []

        for asin in asins:
            movements = self.detect_competitive_movements([asin])

            for movement in movements:
                if movement['severity'] in ['moderate', 'major']:
                    alert = {
                        'type': 'price_change',
                        'asin': movement['asin'],
                        'severity': movement['severity'],
                        'message': movement['description'],
                        'change_percent': movement['change_percent'],
                        'previous_price': movement['previous_price'],
                        'new_price': movement['new_price'],
                        'date': movement['date'],
                        'trend_indicator': '📈' if movement['type'] == 'increase' else '📉'
                    }
                    alerts.append(alert)

        return sorted(alerts, key=lambda x: (
            0 if x['severity'] == 'major' else 1,
            abs(x['change_percent'])
        ), reverse=True)

    def detect_new_entrants(self, current_competitors: list[str], historical_competitors: list[str]) -> list[str]:
        """Detect new competitors that weren't in historical data
        
        Args:
            current_competitors: Current list of competitor ASINs
            historical_competitors: Historical list of competitor ASINs
        
        Returns:
            List of new entrant ASINs
        """
        historical_set = set(historical_competitors)
        new_entrants = []

        for asin in current_competitors:
            if asin not in historical_set:
                new_entrants.append(asin)

        return new_entrants

    def detect_market_share_shifts(self, asin: str, competitors: list[dict], days: int = 30) -> dict[str, Any]:
        """Detect shifts in market positioning
        
        Args:
            asin: Target ASIN
            competitors: Current competitor data
            days: Historical period to compare
        
        Returns:
            Dictionary with market share shift analysis
        """
        snapshots = get_snapshots('competitors',
            start_date=(datetime.now() - timedelta(days=days)).date().isoformat(),
            end_date=datetime.now().date().isoformat()
        )

        if not snapshots:
            return {
                'asin': asin,
                'has_shift': False,
                'shift_direction': None,
                'shift_magnitude': 0,
                'description': 'Insufficient data for market share analysis'
            }

        historical_prices = {}
        for snapshot in snapshots:
            data = snapshot.get('data', {})
            comps = data.get('competitors', [])
            for comp in comps:
                asin_key = comp.get('asin', '')
                price = comp.get('price', 0)
                if asin_key and price > 0:
                    if asin_key not in historical_prices:
                        historical_prices[asin_key] = []
                    historical_prices[asin_key].append(price)

        avg_historical = {k: sum(v) / len(v) for k, v in historical_prices.items() if v}

        current_prices = {c.get('asin'): c.get('price', 0) for c in competitors if c.get('price', 0) > 0}

        if asin not in avg_historical or asin not in current_prices:
            return {
                'asin': asin,
                'has_shift': False,
                'shift_direction': None,
                'shift_magnitude': 0,
                'description': 'ASIN not found in historical data'
            }

        historical_avg = avg_historical[asin]
        current_price = current_prices[asin]

        price_change = ((current_price - historical_avg) / historical_avg) * 100 if historical_avg > 0 else 0

        historical_ranking = sorted(avg_historical.items(), key=lambda x: x[1])
        current_ranking = sorted(current_prices.items(), key=lambda x: x[1])

        hist_rank = next((i + 1 for i, (a, _) in enumerate(historical_ranking) if a == asin), 0)
        curr_rank = next((i + 1 for i, (a, _) in enumerate(current_ranking) if a == asin), 0)

        rank_change = hist_rank - curr_rank

        if abs(rank_change) >= 2 or abs(price_change) >= 15:
            has_shift = True
            if rank_change > 0 or price_change < -10:
                direction = 'lost_position'
            elif rank_change < 0 or price_change > 10:
                direction = 'gained_position'
            else:
                direction = 'stable'
        else:
            has_shift = False
            direction = 'stable'

        descriptions = {
            'lost_position': f'Dropped {abs(rank_change)} rank positions',
            'gained_position': f'Gained {abs(rank_change)} rank positions',
            'stable': 'Market position remains stable'
        }

        return {
            'asin': asin,
            'has_shift': has_shift,
            'shift_direction': direction,
            'shift_magnitude': round(abs(price_change), 2),
            'rank_change': rank_change,
            'historical_rank': hist_rank,
            'current_rank': curr_rank,
            'price_change_percent': round(price_change, 2),
            'description': descriptions.get(direction, 'Position unchanged')
        }


competitor_analyzer = CompetitorAnalyzer()


def take_daily_snapshot() -> dict[str, int]:
    """Take daily snapshots for all types
    
    Returns:
        Dictionary mapping snapshot types to their IDs
    """
    snapshot_ids = {}

    for snapshot_type in ['inventory', 'orders', 'reviews', 'competitors']:
        try:
            snapshot_id = save_snapshot(snapshot_type, {})
            snapshot_ids[snapshot_type] = snapshot_id
        except Exception:
            snapshot_ids[snapshot_type] = None

    return snapshot_ids
