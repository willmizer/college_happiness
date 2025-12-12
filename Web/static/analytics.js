let barChart = null;
let stateChart = null;
let distChart = null;
let pieChart = null;

document.addEventListener('DOMContentLoaded', init);

async function init() {
    const res = await fetch('/api/states');
    const states = await res.json();
    
    const select = document.getElementById('state-select');
    states.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.innerText = s;
        select.appendChild(opt);
    });

    // Listeners
    document.getElementById('state-select').addEventListener('change', updateDashboard);
    document.getElementById('feature-select').addEventListener('change', updateDashboard);
    
    updateDashboard();
}

async function updateDashboard() {
    const stateVal = document.getElementById('state-select').value;
    const feature = document.getElementById('feature-select').value;
    
    // Determine display text for state
    const stateDisplay = stateVal === "All" ? "the US" : stateVal;
    const stateForPrefix = stateVal === "All" ? "for All States" : `for ${stateVal}`;
    const stateInPrefix = stateVal === "All" ? "in the US" : `in ${stateVal}`;

    // Update Header
    document.getElementById('state-title').innerText = stateDisplay;
    document.getElementById('lead-feat').innerText = feature;
    
    // Update Dynamic Texts
    document.getElementById('state-feat').innerText = feature;
    
    // --- UPDATED SCORE DISTRIBUTION TEXT ---
    document.getElementById('dist-state').innerText = stateInPrefix;
    document.getElementById('dist-feat').innerText = feature; // <--- NEW UPDATE
    
    document.getElementById('avg-feat').innerText = feature;
    document.getElementById('pie-state').innerText = stateForPrefix;

    const res = await fetch('/api/analytics/rank', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
            state: stateVal, 
            feature: feature
        })
    });

    const data = await res.json();

    animateValue("pie-score", parseFloat(document.getElementById('pie-score').innerText), data.average_score, 1000);

    updateBarChart(data.top_schools, feature);
    updateStateChart(data.top_states, feature);
    updateDistChart(data.distribution, feature);
    updatePieChart(data.average_score);
}

// --- CHART FUNCTIONS ---

function updateBarChart(data, feature) {
    const ctx = document.getElementById('barChart').getContext('2d');
    const labels = data.map(d => d.school_name); 
    const values = data.map(d => d[feature]); 
    
    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const suggestedMin = Math.max(0, minVal - 0.5);

    if (barChart) {
        barChart.data.labels = labels;
        barChart.data.datasets[0].data = values;
        barChart.options.scales.x.min = suggestedMin;
        barChart.update();
    } else {
        barChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score',
                    data: values,
                    backgroundColor: '#4F46E5',
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1000, easing: 'easeOutQuart' },
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            }
                        }
                    }
                },
                scales: { 
                    x: { 
                        beginAtZero: false, 
                        min: suggestedMin, 
                        max: 5 
                    },
                    y: {
                        ticks: {
                            callback: function(value) {
                                const label = this.getLabelForValue(value);
                                if (label.length > 35) {
                                    return label.substring(0, 35) + '...';
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
}

function updateStateChart(data, feature) {
    const ctx = document.getElementById('stateBarChart').getContext('2d');
    const labels = data.map(d => d.state);
    const values = data.map(d => d.score); 

    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const suggestedMin = Math.max(0, minVal - 0.5);

    if (stateChart) {
        stateChart.data.labels = labels;
        stateChart.data.datasets[0].data = values;
        stateChart.options.scales.y.min = suggestedMin;
        stateChart.update();
    } else {
        stateChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Score',
                    data: values,
                    backgroundColor: '#10B981', 
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'x', 
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1000, easing: 'easeOutQuart' },
                plugins: { legend: { display: false } },
                scales: { 
                    y: { 
                        beginAtZero: false,
                        min: suggestedMin,
                        max: 5 
                    } 
                }
            }
        });
    }
}

function updateDistChart(distData, feature) {
    const ctx = document.getElementById('distChart').getContext('2d');
    
    if (distChart) {
        distChart.data.labels = distData.labels;
        distChart.data.datasets[0].data = distData.counts;
        distChart.options.scales.x.title.text = `${feature} Range`;
        distChart.update();
    } else {
        distChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: distData.labels,
                datasets: [{
                    label: 'Number of Schools',
                    data: distData.counts,
                    backgroundColor: '#8B5CF6',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 800 },
                plugins: { legend: { display: false } },
                scales: { 
                    y: { beginAtZero: true, title: {display:true, text:'Count'} },
                    x: { title: {display:true, text:`${feature} Range`} }
                }
            }
        });
    }
}

function updatePieChart(avgScore) {
    const ctx = document.getElementById('pieChart').getContext('2d');
    const remaining = 5 - avgScore;

    if (pieChart) {
        pieChart.data.datasets[0].data = [avgScore, remaining];
        pieChart.update();
    } else {
        pieChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Average Score', 'Gap'],
                datasets: [{
                    data: [avgScore, remaining],
                    backgroundColor: ['#F59E0B', '#F3F4F6'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                animation: { animateScale: true, animateRotate: true },
                plugins: { legend: { display: false }, tooltip: { enabled: false } }
            }
        });
    }
}

function animateValue(id, start, end, duration) {
    if (start === end) return;
    const obj = document.getElementById(id);
    const range = end - start;
    let current = start;
    const increment = end > start ? 0.05 : -0.05;
    const stepTime = Math.abs(Math.floor(duration / (range / increment)));
    
    const timer = setInterval(function() {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }
        obj.innerText = current.toFixed(2);
    }, stepTime);
}