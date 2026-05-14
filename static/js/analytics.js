const AnalyticsCharts = {
  defaultColors: [
    'rgba(102, 126, 234, 0.8)',
    'rgba(118, 75, 162, 0.8)',
    'rgba(236, 72, 153, 0.8)',
    'rgba(16, 185, 129, 0.8)',
    'rgba(245, 158, 11, 0.8)',
    'rgba(59, 130, 246, 0.8)',
    'rgba(239, 68, 68, 0.8)',
    'rgba(34, 197, 94, 0.8)'
  ],

  defaultBorderColors: [
    'rgb(102, 126, 234)',
    'rgb(118, 75, 162)',
    'rgb(236, 72, 153)',
    'rgb(16, 185, 129)',
    'rgb(245, 158, 11)',
    'rgb(59, 130, 246)',
    'rgb(239, 68, 68)',
    'rgb(34, 197, 94)'
  ],

  createLineChart(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
      console.error(`Canvas element with id "${canvasId}" not found`);
      return null;
    }

    const defaultOptions = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            font: { family: 'Inter, sans-serif', size: 12 },
            color: '#4B5563',
            padding: 15
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleFont: { family: 'Inter, sans-serif', size: 14 },
          bodyFont: { family: 'Inter, sans-serif', size: 12 },
          padding: 12,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: 'Inter, sans-serif', size: 11 },
            color: '#6B7280'
          }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: {
            font: { family: 'Inter, sans-serif', size: 11 },
            color: '#6B7280'
          }
        }
      },
      animation: {
        duration: 750,
        easing: 'easeInOutQuart'
      }
    };

    const mergedOptions = this.deepMerge(defaultOptions, options);

    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets.map((ds, idx) => ({
          label: ds.label || `Dataset ${idx + 1}`,
          data: ds.data,
          borderColor: ds.borderColor || this.defaultBorderColors[idx % this.defaultBorderColors.length],
          backgroundColor: ds.backgroundColor || this.defaultColors[idx % this.defaultColors.length],
          fill: ds.fill !== undefined ? ds.fill : false,
          tension: ds.tension !== undefined ? ds.tension : 0.3,
          pointRadius: ds.pointRadius !== undefined ? ds.pointRadius : 3,
          pointHoverRadius: ds.pointHoverRadius !== undefined ? ds.pointHoverRadius : 6
        }))
      },
      options: mergedOptions
    });
  },

  createBarChart(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
      console.error(`Canvas element with id "${canvasId}" not found`);
      return null;
    }

    const defaultOptions = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            font: { family: 'Inter, sans-serif', size: 12 },
            color: '#4B5563',
            padding: 15
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleFont: { family: 'Inter, sans-serif', size: 14 },
          bodyFont: { family: 'Inter, sans-serif', size: 12 },
          padding: 12,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: 'Inter, sans-serif', size: 11 },
            color: '#6B7280'
          }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: {
            font: { family: 'Inter, sans-serif', size: 11 },
            color: '#6B7280'
          }
        }
      },
      animation: {
        duration: 750,
        easing: 'easeInOutQuart'
      }
    };

    const mergedOptions = this.deepMerge(defaultOptions, options);

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: datasets.map((ds, idx) => ({
          label: ds.label || `Dataset ${idx + 1}`,
          data: ds.data,
          backgroundColor: ds.backgroundColor || this.defaultColors[idx % this.defaultColors.length],
          borderColor: ds.borderColor || this.defaultBorderColors[idx % this.defaultBorderColors.length],
          borderWidth: ds.borderWidth !== undefined ? ds.borderWidth : 1,
          borderRadius: ds.borderRadius !== undefined ? ds.borderRadius : 4
        }))
      },
      options: mergedOptions
    });
  },

  createPieChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
      console.error(`Canvas element with id "${canvasId}" not found`);
      return null;
    }

    const defaultOptions = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: true,
          position: 'right',
          labels: {
            font: { family: 'Inter, sans-serif', size: 12 },
            color: '#4B5563',
            padding: 15,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleFont: { family: 'Inter, sans-serif', size: 14 },
          bodyFont: { family: 'Inter, sans-serif', size: 12 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      },
      animation: {
        duration: 750,
        easing: 'easeInOutQuart'
      }
    };

    const mergedOptions = this.deepMerge(defaultOptions, options);

    return new Chart(ctx, {
      type: 'pie',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: this.defaultColors.slice(0, labels.length),
          borderColor: this.defaultBorderColors.slice(0, labels.length),
          borderWidth: 2
        }]
      },
      options: mergedOptions
    });
  },

  createDoughnutChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) {
      console.error(`Canvas element with id "${canvasId}" not found`);
      return null;
    }

    const defaultOptions = {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '60%',
      plugins: {
        legend: {
          display: true,
          position: 'right',
          labels: {
            font: { family: 'Inter, sans-serif', size: 12 },
            color: '#4B5563',
            padding: 15,
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleFont: { family: 'Inter, sans-serif', size: 14 },
          bodyFont: { family: 'Inter, sans-serif', size: 12 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      },
      animation: {
        duration: 750,
        easing: 'easeInOutQuart'
      }
    };

    const mergedOptions = this.deepMerge(defaultOptions, options);

    return new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: this.defaultColors.slice(0, labels.length),
          borderColor: this.defaultBorderColors.slice(0, labels.length),
          borderWidth: 2
        }]
      },
      options: mergedOptions
    });
  },

  destroyChart(chartInstance) {
    if (chartInstance) {
      chartInstance.destroy();
    }
  },

  updateChart(chartInstance, newData) {
    if (chartInstance) {
      chartInstance.data = newData;
      chartInstance.update();
    }
  },

  deepMerge(target, source) {
    const output = { ...target };
    if (this.isObject(target) && this.isObject(source)) {
      Object.keys(source).forEach(key => {
        if (this.isObject(source[key])) {
          if (!(key in target)) {
            output[key] = source[key];
          } else {
            output[key] = this.deepMerge(target[key], source[key]);
          }
        } else {
          output[key] = source[key];
        }
      });
    }
    return output;
  },

  isObject(item) {
    return item && typeof item === 'object' && !Array.isArray(item);
  },

  formatCurrency(value, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(value);
  },

  formatNumber(value, decimals = 0) {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(value);
  },

  formatPercentage(value, decimals = 1) {
    return `${value.toFixed(decimals)}%`;
  },

  formatDate(date, format = 'short') {
    const d = new Date(date);
    if (format === 'short') {
      return d.toLocaleDateString();
    } else if (format === 'long') {
      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } else if (format === 'datetime') {
      return d.toLocaleString();
    }
    return d.toLocaleDateString();
  },

  generateDateLabels(days) {
    const labels = [];
    const today = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    }
    return labels;
  },

  generateWeeklyLabels(weeks) {
    const labels = [];
    const today = new Date();
    for (let i = weeks - 1; i >= 0; i--) {
      const weekStart = new Date(today);
      weekStart.setDate(weekStart.getDate() - (i * 7));
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekEnd.getDate() + 6);
      labels.push(`${weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`);
    }
    return labels;
  },

  generateMonthlyLabels(months) {
    const labels = [];
    const today = new Date();
    for (let i = months - 1; i >= 0; i--) {
      const date = new Date(today.getFullYear(), today.getMonth() - i, 1);
      labels.push(date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }));
    }
    return labels;
  },

  exportChartAsImage(chartInstance, filename = 'chart.png') {
    if (chartInstance) {
      const link = document.createElement('a');
      link.download = filename;
      link.href = chartInstance.toBase64Image();
      link.click();
    }
  }
};

window.AnalyticsCharts = AnalyticsCharts;
