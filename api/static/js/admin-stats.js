// The charts of the admin's user statistics (accounts/stats.py), drawn with
// Chart.js from the page's stats-charts JSON. Their colours are the page's
// CSS variables (.viz-root), so they are drawn again when the admin's theme
// changes. Every chart's numbers are also in its table view.
(() => {
    const root = document.querySelector(".viz-root");
    const specs = JSON.parse(document.getElementById("stats-charts").textContent);
    const drawn = [];

    function colors() {
        const style = getComputedStyle(root);
        const value = (name) => style.getPropertyValue(name).trim();
        return {
            surface: value("--surface-1"),
            text: value("--text-primary"),
            secondary: value("--text-secondary"),
            muted: value("--text-muted"),
            grid: value("--grid"),
            axis: value("--axis"),
            series: [value("--series-1"), value("--series-2")],
            good: value("--status-good"),
            warning: value("--status-warning"),
            critical: value("--status-critical"),
        };
    }

    // #rrggbb colours: a mixed with weight of b, and a with an alpha
    const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    const mix = (a, b, weight) => {
        const [x, y] = [rgb(a), rgb(b)];
        return `rgb(${x.map((value, i) => Math.round(value * (1 - weight) + y[i] * weight)).join(", ")})`;
    };
    const alpha = (hex, opacity) => `rgba(${rgb(hex).join(", ")}, ${opacity})`;

    const compact = new Intl.NumberFormat(undefined, { notation: "compact" });
    const number = (value, percent) => percent ? `${value} %` : value.toLocaleString();

    // A vertical hairline at the hovered point of line charts
    const crosshair = {
        id: "crosshair",
        afterDatasetsDraw(chart, _args, options) {
            const active = chart.tooltip?.getActiveElements();
            if (!options.color || !active?.length) {
                return;
            }
            const { ctx, chartArea } = chart;
            ctx.save();
            ctx.strokeStyle = options.color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(active[0].element.x, chartArea.top);
            ctx.lineTo(active[0].element.x, chartArea.bottom);
            ctx.stroke();
            ctx.restore();
        },
    };

    // The value at the end of each horizontal bar, in text colour
    const barValues = {
        id: "barValues",
        afterDatasetsDraw(chart, _args, options) {
            if (!options.color) {
                return;
            }
            const { ctx } = chart;
            ctx.save();
            ctx.fillStyle = options.color;
            ctx.font = `600 12px ${options.font}`;
            ctx.textBaseline = "middle";
            chart.getDatasetMeta(0).data.forEach((bar, i) => {
                ctx.fillText(number(chart.data.datasets[0].data[i], options.percent), bar.x + 6, bar.y);
            });
            ctx.restore();
        },
    };

    function config(spec, c) {
        const font = getComputedStyle(document.body).fontFamily;
        const line = spec.kind === "line";
        const horizontal = spec.kind === "hbar";
        const legend = spec.series.length > 1;

        const datasets = spec.series.map((series, i) => {
            const color = spec.colors ? spec.colors.map((name) => c[name]) : c.series[i];
            if (line) {
                return {
                    label: series.name, data: series.data, borderColor: color, pointBackgroundColor: color,
                    backgroundColor: spec.fill ? alpha(color, 0.1) : color,
                    fill: Boolean(spec.fill), borderWidth: 2, borderJoinStyle: "round", borderCapStyle: "round",
                    pointRadius: series.data.length === 1 ? 4 : 0, pointHoverRadius: 5,
                    pointBorderColor: c.surface, pointBorderWidth: 2, tension: 0,
                };
            }
            return {
                label: series.name, data: series.data, backgroundColor: color,
                // Hovered bars lighten towards the surface
                hoverBackgroundColor: Array.isArray(color) ? color.map((each) => mix(each, c.surface, 0.2)) : mix(color, c.surface, 0.2),
                borderRadius: 4, borderSkipped: "start", maxBarThickness: 24, borderWidth: 0,
            };
        });

        const valueAxis = {
            beginAtZero: true,
            max: spec.percent ? 100 : undefined,
            grid: { color: c.grid, drawTicks: false },
            border: { display: false },
            ticks: {
                color: c.muted, padding: 6, precision: 0, font: { family: font },
                callback: (value) => spec.percent ? `${value} %` : (value >= 1000 ? compact.format(value) : value),
            },
        };
        const categoryAxis = {
            grid: { display: false },
            border: { color: c.axis },
            ticks: { color: horizontal ? c.secondary : c.muted, font: { family: font }, autoSkip: true, maxRotation: 0 },
        };

        return {
            type: line ? "line" : "bar",
            data: { labels: spec.labels, datasets },
            plugins: [crosshair, barValues],
            options: {
                indexAxis: horizontal ? "y" : "x",
                maintainAspectRatio: false,
                animation: false,
                layout: { padding: { right: horizontal ? 48 : 8 } },
                interaction: line ? { mode: "index", intersect: false } : { mode: "nearest", axis: horizontal ? "y" : "x", intersect: false },
                scales: horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
                plugins: {
                    legend: {
                        display: legend, position: "top", align: "start",
                        labels: {
                            color: c.secondary, usePointStyle: true, pointStyle: line ? "line" : "rectRounded", boxWidth: 16, font: { family: font },
                            // A key in the series colour (the default takes the points' border, the surface)
                            generateLabels: (chart) => Chart.defaults.plugins.legend.labels.generateLabels(chart).map((item) => {
                                const dataset = chart.data.datasets[item.datasetIndex];
                                const color = line ? dataset.borderColor : dataset.backgroundColor;
                                return { ...item, strokeStyle: color, fillStyle: color, lineWidth: 2 };
                            }),
                        },
                    },
                    tooltip: {
                        backgroundColor: c.surface, titleColor: c.secondary, bodyColor: c.text,
                        borderColor: c.axis, borderWidth: 1, padding: 10, cornerRadius: 6,
                        titleFont: { family: font, weight: "normal" }, bodyFont: { family: font, weight: "600" },
                        usePointStyle: true, boxPadding: 6,
                        callbacks: {
                            // The value first, then what it is
                            label: (item) => `${number(item.raw, spec.percent)}  ${item.dataset.label}`,
                            labelPointStyle: () => ({ pointStyle: line ? "line" : "rectRounded", rotation: 0 }),
                            labelColor: (item) => {
                                const color = Array.isArray(item.dataset.backgroundColor) && !line
                                    ? item.dataset.backgroundColor[item.dataIndex]
                                    : (line ? item.dataset.borderColor : item.dataset.backgroundColor);
                                return { borderColor: color, backgroundColor: color, borderWidth: 2 };
                            },
                        },
                    },
                    crosshair: { color: line ? c.axis : "" },
                    barValues: { color: horizontal ? c.text : "", font, percent: spec.percent },
                },
            },
        };
    }

    function draw() {
        const c = colors();
        drawn.splice(0).forEach((chart) => chart.destroy());
        for (const spec of specs) {
            const canvas = root.querySelector(`canvas[data-chart="${spec.id}"]`);
            if (canvas) {
                drawn.push(new Chart(canvas, config(spec, c)));
            }
        }
    }

    draw();
    // The admin's theme switch, and the system's theme when it is on auto
    new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
})();
