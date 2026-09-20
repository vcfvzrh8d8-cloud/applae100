const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// ===== STATE =====
let state = {
    balance: 0,
    sessionId: 0,
    currentBetChoice: '',
    handOpen: false,
    isExpanded: false,
    history: [],
    chartData: [],
    chartType: 'xiu'
};

// ===== GỬI DỮ LIỆU VỀ BOT =====
function sendToBot(action, data = {}) {
    const payload = { action, ...data };
    tg.sendData(JSON.stringify(payload));
}

// ===== NHẬN DỮ LIỆU TỪ BOT =====
tg.onEvent('web_app_data', function(data) {
    try {
        const parsed = JSON.parse(data);
        handleBotResponse(parsed);
    } catch (e) {
        console.error('Lỗi parse data:', e);
    }
});

function handleBotResponse(data) {
    // Cập nhật số dư
    if (data.balance !== undefined) {
        state.balance = data.balance;
        updateBalanceDisplay();
    }

    // Cập nhật số tiền cược Tài/Xỉu
    if (data.tai_amount !== undefined) {
        document.getElementById('tai-amount').innerText = formatMoney(data.tai_amount) + 'đ';
    }
    if (data.xiu_amount !== undefined) {
        document.getElementById('xiu-amount').innerText = formatMoney(data.xiu_amount) + 'đ';
    }

    // Cập nhật số người chơi
    if (data.player_count !== undefined) {
        document.getElementById('player-count').innerText = '👥 ' + data.player_count;
    }

    // Cập nhật phiên
    if (data.session_id !== undefined) {
        state.sessionId = data.session_id;
        document.getElementById('session-info').innerText = 'Phiên #' + data.session_id;
    }

    // Hiệu ứng nhấp nháy kết quả
    if (data.result) {
        showResultBlink(data.result);
    }

    // Lịch sử cược
    if (data.bet_history) {
        renderBetHistory(data.bet_history);
    }

    // Lịch sử phiên (chart)
    if (data.chart_data) {
        state.chartData = data.chart_data;
        drawChart();
    }

    // Kết quả gần đây
    if (data.recent_results) {
        renderRecentResults(data.recent_results);
    }

    // Thông báo
    if (data.message) {
        tg.showAlert(data.message);
    }
}

// ===== FORMAT TIỀN =====
function formatMoney(amount) {
    return amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

function updateBalanceDisplay() {
    document.getElementById('balance').innerText = formatMoney(state.balance);
    document.getElementById('bet-balance').innerText = formatMoney(state.balance);
}

// ===== MỞ MÀN HÌNH ĐẶT CƯỢC =====
function openBetScreen(choice) {
    state.currentBetChoice = choice;
    document.getElementById('bet-choice-label').innerText = choice;
    document.getElementById('bet-amount-input').value = '';
    switchScreen('bet-screen');
}

function closeBetScreen() {
    switchScreen('main-screen');
}

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

// ===== NHẬP SỐ TIỀN =====
function setAmount(amount) {
    document.getElementById('bet-amount-input').value = amount;
}

function allIn() {
    document.getElementById('bet-amount-input').value = state.balance;
}

// ===== XÁC NHẬN ĐẶT CƯỢC =====
function confirmBet() {
    const amount = parseInt(document.getElementById('bet-amount-input').value);
    if (!amount || amount < 1000) {
        tg.showAlert('Số tiền cược tối thiểu là 1,000đ');
        return;
    }
    if (amount > state.balance) {
        tg.showAlert('Số dư không đủ!');
        return;
    }

    sendToBot('place_bet', {
        choice: state.currentBetChoice,
        amount: amount
    });

    // Trừ tạm số dư trên UI
    state.balance -= amount;
    updateBalanceDisplay();

    tg.showAlert(`Đã đặt ${formatMoney(amount)}đ vào ${state.currentBetChoice}`);
    closeBetScreen();
}

// ===== NÚT BÀN TAY (MỞ BÁT) =====
function toggleHand() {
    state.handOpen = !state.handOpen;
    const btn = document.getElementById('hand-btn');
    if (state.handOpen) {
        btn.classList.remove('locked');
        btn.classList.add('open');
    } else {
        btn.classList.add('locked');
        btn.classList.remove('open');
    }
    sendToBot('toggle_hand', { open: state.handOpen });
}

// ===== HIỆU ỨNG NHẤP NHÁY KẾT QUẢ =====
function showResultBlink(result) {
    const diceBox = document.getElementById('dice-result');
    diceBox.innerText = result;
    diceBox.classList.remove('blink');
    void diceBox.offsetWidth; // Trigger reflow
    diceBox.classList.add('blink');

    setTimeout(() => {
        diceBox.classList.remove('blink');
    }, 2500);
}

// ===== OVERLAY =====
function toggleOverlay(id) {
    const overlay = document.getElementById(id);
    if (overlay.classList.contains('active')) {
        overlay.classList.remove('active');
    } else {
        document.querySelectorAll('.overlay').forEach(o => o.classList.remove('active'));
        overlay.classList.add('active');

        // Gọi dữ liệu tương ứng
        if (id === 'bet-history') {
            sendToBot('get_bet_history');
        } else if (id === 'session-history') {
            sendToBot('get_session_history');
        }
    }
}

function closeOverlay() {
    document.querySelectorAll('.overlay').forEach(o => o.classList.remove('active'));
}

// ===== LỊCH SỬ CƯỢC =====
function renderBetHistory(history) {
    const tbody = document.getElementById('bet-history-body');
    tbody.innerHTML = '';
    if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">Chưa có lịch sử</td></tr>';
        return;
    }
    history.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>#${item.session}</td>
            <td>${item.time}</td>
            <td>${item.choice}</td>
            <td>${item.result}</td>
            <td>${formatMoney(item.bet)}đ</td>
            <td class="${item.win > 0 ? 'win' : 'lose'}">${item.win > 0 ? '+' : ''}${formatMoney(item.win)}đ</td>
        `;
        tbody.appendChild(tr);
    });
}

// ===== CHART (LỊCH SỬ PHIÊN) =====
function switchChart(type) {
    state.chartType = type;
    document.querySelectorAll('.chart-tabs .tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    sendToBot('get_session_history', { type: type });
}

function drawChart() {
    const canvas = document.getElementById('chart-canvas');
    const ctx = canvas.getContext('2d');
    const data = state.chartData;

    // Resize canvas
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!data || data.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Chưa có dữ liệu', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Vẽ grid
    const cols = 15;
    const rows = 6;
    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    for (let i = 0; i <= cols; i++) {
        ctx.beginPath();
        ctx.moveTo(i * cellW, 0);
        ctx.lineTo(i * cellW, canvas.height);
        ctx.stroke();
    }
    for (let j = 0; j <= rows; j++) {
        ctx.beginPath();
        ctx.moveTo(0, j * cellH);
        ctx.lineTo(canvas.width, j * cellH);
        ctx.stroke();
    }

    // Vẽ đường dây
    ctx.beginPath();
    ctx.strokeStyle = '#d4af37';
    ctx.lineWidth = 2;

    data.forEach((point, index) => {
        if (index >= cols) return;
        const x = index * cellW + cellW / 2;
        const y = canvas.height - (point.value / 18) * canvas.height;
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    // Vẽ điểm
    data.forEach((point, index) => {
        if (index >= cols) return;
        const x = index * cellW + cellW / 2;
        const y = canvas.height - (point.value / 18) * canvas.height;
        ctx.beginPath();
        ctx.fillStyle = point.type === 'tai' ? '#0055ff' : '#ff0000';
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = '10px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(point.value, x, y - 8);
    });
}

function toggleExpandChart() {
    state.isExpanded = !state.isExpanded;
    const btn = document.getElementById('expand-btn');
    const area = document.getElementById('chart-area');
    if (state.isExpanded) {
        btn.innerText = '▲ Thu gọn';
        area.style.minHeight = '500px';
        document.getElementById('chart-canvas').height = 500;
    } else {
        btn.innerText = '▼ Mở rộng';
        area.style.minHeight = '300px';
        document.getElementById('chart-canvas').height = 300;
    }
    sendToBot('get_session_history', { type: state.chartType, expanded: state.isExpanded });
}

// ===== KẾT QUẢ GẦN ĐÂY =====
function renderRecentResults(results) {
    const container = document.getElementById('recent-results');
    container.innerHTML = '';
    results.forEach(r => {
        const dot = document.createElement('div');
        dot.className = 'result-dot ' + (r === 'T' ? 'tai' : 'xiu');
        dot.innerText = r;
        container.appendChild(dot);
    });
}

// ===== ĐÓNG APP =====
function closeApp() {
    tg.close();
}

// ===== KHỞI TẠO =====
sendToBot('init');
