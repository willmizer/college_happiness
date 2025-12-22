let currentSchool = "";
let baselineHappiness = 0;
let featureRankings = []; 
let selectedFeatures = new Set(); 
let debounceTimer; 

// Chart Global Variables
let strategyChart = null;
let fullChartData = []; 

document.addEventListener('DOMContentLoaded', init);

async function init() {
    // 1. Fetch Metadata
    const response = await fetch('/api/metadata');
    const meta = await response.json();
    
    // 2. Setup Components
    setupAutocomplete(document.getElementById("school-search"), meta.schools.sort());

    const deltaInput = document.getElementById('delta-input');
    const deltaSlider = document.getElementById('delta-slider');

    // Sync Slider -> Input (Debounced)
    deltaSlider.addEventListener('input', (e) => {
        deltaInput.value = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(refreshAllData, 500);
    });

    // Sync Input -> Slider (Debounced)
    deltaInput.addEventListener('input', (e) => {
        deltaSlider.value = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(refreshAllData, 500);
    });

    // --- NEW: Setup Chart Step Buttons Click Listeners ---
    document.querySelectorAll('.step-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Extract number from text (e.g. "5%" -> 5)
            const stepVal = parseInt(e.target.innerText);
            updateChartStep(stepVal);
        });
    });

    // 3. Load Default School
    loadSchool("Florida Polytechnic University");
}

async function loadSchool(name) {
    currentSchool = name;
    
    // Update Header
    document.getElementById('school-title').innerText = name;
    document.getElementById('school-search').value = name; 
    
    // Reset Selection
    resetSelections();
    
    // Call Turbo Endpoint
    await refreshAllData();
}

async function refreshAllData() {
    if (!currentSchool) return;

    // Loading State
    document.getElementById('cards-grid').style.opacity = '0.5';

    const deltaPercent = parseFloat(document.getElementById('delta-input').value);
    const deltaDecimal = deltaPercent / 100.0;

    // TURBO CALL
    const res = await fetch('/api/school_profile_full', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
            school_name: currentSchool, 
            delta: deltaDecimal 
        })
    });

    const data = await res.json();
    
    // 1. Baseline
    baselineHappiness = data.baseline_happiness;
    document.getElementById('baseline-disp').innerText = baselineHappiness.toFixed(2) + "%";

    // 2. Rankings (Cards)
    featureRankings = data.rankings;
    renderCards();
    updateTotalCalculation();
    document.getElementById('cards-grid').style.opacity = '1';

    // 3. Sweep (Chart) - FIXED LOGIC HERE
    fullChartData = data.sweep;

    // Check if there is an existing active button, otherwise default to 1
    const activeBtn = document.querySelector('.step-btn.active');
    const currentStep = activeBtn ? parseInt(activeBtn.innerText) : 5;
    
    updateChartStep(currentStep); 

    // 4. Marginal (Table)
    renderMarginalTable(data.marginal);
}

// --- RENDERING FUNCTIONS ---

function renderCards() {
    const grid = document.getElementById('cards-grid');
    grid.innerHTML = '';

    const maxMagnitude = Math.max(...featureRankings.map(r => Math.abs(r.gain_percent))) || 1;

    featureRankings.forEach(item => {
        const isSelected = selectedFeatures.has(item.feature);
        const isNegative = item.gain_percent < 0;
        
        let cardClasses = `feature-card`;
        if (isSelected) {
            cardClasses += ' selected';
            if (isNegative) cardClasses += ' negative-selection';
        }

        let gainClass = 'zero-gain';
        if (item.gain_percent > 0) gainClass = 'positive-gain';
        if (item.gain_percent < 0) gainClass = 'negative-gain';

        let gainText = `${item.gain_percent.toFixed(2)}%`;
        if (item.gain_percent > 0) gainText = `+${gainText}`;

        const barWidth = (Math.abs(item.gain_percent) / maxMagnitude) * 100;

        const card = document.createElement('div');
        card.className = cardClasses;

        card.innerHTML = `
            <div class="card-header-row">
                <span class="card-title">${item.feature}</span>
                <span class="current-badge" title="Current Level">
                    ${Math.round(item.current_percent)}%
                </span>
            </div>
            <div class="card-gain ${gainClass}">${gainText} Happiness</div>
            <div class="impact-bar-bg">
                <div class="impact-bar-fill ${isNegative ? 'negative' : ''}" style="width: ${barWidth}%"></div>
            </div>
        `;

        card.addEventListener('click', () => toggleFeature(item.feature));
        grid.appendChild(card);
    });
}

function updateTotalCalculation() {
    let totalScore = baselineHappiness;
    let addedPoints = 0;

    featureRankings.forEach(item => {
        if (selectedFeatures.has(item.feature)) {
            addedPoints += item.gain_percent;
        }
    });

    totalScore += addedPoints;

    document.getElementById('final-score').innerText = totalScore.toFixed(2) + "%";
    
    const diffEl = document.getElementById('score-diff');
    diffEl.className = 'score-diff'; 

    if (addedPoints > 0) {
        diffEl.innerText = `+${addedPoints.toFixed(2)}%`;
        diffEl.classList.add('diff-positive');
    } else if (addedPoints < 0) {
        diffEl.innerText = `${addedPoints.toFixed(2)}%`; 
        diffEl.classList.add('diff-negative');
    } else {
        diffEl.innerText = `+0.00%`;
        diffEl.classList.add('diff-neutral');
    }

    document.getElementById('active-count').innerText = selectedFeatures.size;
}

function toggleFeature(featureName) {
    if (selectedFeatures.has(featureName)) selectedFeatures.delete(featureName);
    else selectedFeatures.add(featureName);
    renderCards(); 
    updateTotalCalculation(); 
}

function resetSelections() {
    selectedFeatures.clear();
    renderCards();
    updateTotalCalculation();
}

function updateChartStep(stepSize) {
    // Update Active Button State
    document.querySelectorAll('.step-btn').forEach(btn => {
        if (btn.innerText.includes(`${stepSize}%`)) btn.classList.add('active');
        else btn.classList.remove('active');
    });

    // Filter Data based on step size
    // Note: We use Math.round to avoid floating point modulo errors (e.g. 5.0000001 % 5)
    const filteredData = fullChartData.filter(d => Math.round(d.delta) % stepSize === 0);
    
    renderChartJS(filteredData);
    renderCustomLegend(filteredData);
}

function renderChartJS(data) {
    const ctx = document.getElementById('strategyChart').getContext('2d');
    if (strategyChart) strategyChart.destroy();

    const labels = data.map(d => `${d.delta}%`);
    const gains = data.map(d => d.gain_percent);
    const features = data.map(d => d.best_feature);
    
    const featureColors = getFeatureColorMap();
    const pointColors = features.map(f => featureColors[f] || '#9CA3AF');

    strategyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Happiness Gain',
                data: gains,
                borderColor: '#9CA3AF',
                borderWidth: 2,
                pointBackgroundColor: pointColors,
                pointRadius: 6,
                pointHoverRadius: 8,
                fill: true,
                backgroundColor: 'rgba(243, 244, 246, 0.5)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }, 
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const feat = features[idx];
                            return `Best: ${feat} (+${context.raw.toFixed(2)}%)`;
                        }
                    },
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#111827',
                    bodyColor: '#111827',
                    borderColor: '#E5E7EB',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: true,
                    boxPadding: 6,
                    usePointStyle: true
                }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: '#F3F4F6' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function renderCustomLegend(data) {
    const container = document.getElementById('custom-legend');
    container.innerHTML = '';
    const uniqueFeatures = [...new Set(data.map(d => d.best_feature))];
    const colorMap = getFeatureColorMap();

    uniqueFeatures.forEach(feat => {
        const color = colorMap[feat] || '#9CA3AF';
        const badge = document.createElement('div');
        badge.className = 'legend-item';
        badge.innerHTML = `<div class="legend-dot" style="background: ${color}"></div><span>${feat}</span>`;
        container.appendChild(badge);
    });
}

function renderMarginalTable(data) {
    const tbody = document.querySelector('#marginal-table tbody');
    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center">No significant gains found.</td></tr>`;
        return;
    }

    data.forEach(row => {
        const tr = document.createElement('tr');
        let type = 'Standard';
        let badgeClass = 'badge-neutral';
        
        if (row.optimal_delta <= 10) { type = 'Quick Win'; badgeClass = 'badge-success'; }
        else if (row.optimal_delta >= 35) { type = 'Long Term'; badgeClass = 'badge-warning'; }
        else { type = 'Strategic'; badgeClass = 'badge-primary'; }

        tr.innerHTML = `
            <td class="fw-bold" style="text-transform: capitalize">${row.feature}</td>
            <td>${row.optimal_delta}%</td>
            <td style="color: var(--success); font-weight: 700">+${row.jump_size.toFixed(3)}%</td>
            <td><span class="badge ${badgeClass}">${type}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function getFeatureColorMap() {
    return {
        'facilities': '#4F46E5', 'location': '#10B981', 'opportunities': '#F59E0B',
        'clubs': '#EF4444', 'social': '#8B5CF6', 'safety': '#EC4899', 'food': '#06B6D4', 'internet': '#6366F1'
    };
}

function setupAutocomplete(inp, arr) {
    let currentFocus;
    inp.addEventListener("input", function(e) {
        let val = this.value;
        closeAllLists();
        if (!val) return false;
        let a = document.createElement("DIV");
        a.setAttribute("id", "autocomplete-list");
        a.setAttribute("class", "autocomplete-items");
        this.parentNode.appendChild(a);
        let count = 0;
        for (let i = 0; i < arr.length; i++) {
            if (arr[i].toUpperCase().includes(val.toUpperCase())) {
                if (count > 5) break;
                let b = document.createElement("DIV");
                b.innerHTML = arr[i];
                b.innerHTML += "<input type='hidden' value='" + arr[i] + "'>";
                b.addEventListener("click", function(e) {
                    loadSchool(this.getElementsByTagName("input")[0].value);
                    closeAllLists();
                });
                a.appendChild(b);
                count++;
            }
        }
    });
    function closeAllLists(elmnt) {
        var x = document.getElementsByClassName("autocomplete-items");
        for (var i = 0; i < x.length; i++) {
            if (elmnt != x[i] && elmnt != inp) x[i].parentNode.removeChild(x[i]);
        }
    }
    document.addEventListener("click", function (e) { closeAllLists(e.target); });
}