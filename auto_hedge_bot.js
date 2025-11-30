// ============================================================================
// 全自动对冲循环脚本 (Auto Hedge Bot) 
// 适用平台: omni.variational.io
// 功能: 自动识别现有持仓并补设TP/SL -> 空仓时自动开单 -> 循环监控
// ============================================================================

(async function autoHedgeBotV3_9() {
    console.clear();
    console.log("%c🤖 脚本已启动 V3.9 (宽容检测版)", "color: #00ff00; font-size: 16px; font-weight: bold;");

    // === 配置区域 ===
    const CONFIG = {
        startTime: '11:06:00', 
        tpValue: '3',         
        slValue: '3',         
        interval: 10,         
        
        orderBtnSelector: 'button[data-testid="submit-button"]', 
        tpSlInputSelector: 'input[data-testid="percentage-input"]', 
        positionRowSelector: 'div[data-testid="positions-table-row"]',
        modalSubmitBtnSelector: 'button[data-testid="submit-button"]' 
    };

    let lastFixAttemptTime = 0; 

    if (CONFIG.startTime) {
        await waitForStartTime(CONFIG.startTime);
    }

    while (true) {
        try {
            await runLifeCycle();
        } catch (e) {
            console.error("❌ 循环发生错误:", e);
            await sleep(5000); 
        }
        await sleep(2000); // 增加主循环间隔，减少CPU占用
    }

    async function runLifeCycle() {
        const hasPos = hasPosition();
        if (hasPos) {
            // === 延长冷却时间到 60 秒 ===
            // 如果最近60秒内尝试过补设，就不再动了，防止刷屏
            if (Date.now() - lastFixAttemptTime > 60000) {
                console.log("🔍 检测到持仓，检查是否需要补设 TP/SL...");
                try {
                    const fixed = await checkAndFixTpSlForExistingPosition();
                    if (fixed) {
                        lastFixAttemptTime = Date.now();
                        console.log("✅ 补设操作结束，进入 60秒 冷却...");
                    }
                } catch (err) {
                    console.error("补设过程出错:", err);
                    lastFixAttemptTime = Date.now(); 
                }
            } else {
                // 处于冷却中，安安静静等待
                // console.log("...监控持仓中 (冷却)...");
            }
        } else {
            console.log("✨ 当前空仓，准备开新单...");
            await openNewPositionFlow();
        }
    }

    async function openNewPositionFlow() {
        console.log("准备下单：正在填写 TP/SL...");
        await fillOrderPanelTpSl();

        console.log("准备下单：等待同步触发...");
        const clicked = await waitAndClickOrder();
        
        if (!clicked) {
            console.warn("下单未成功，重试...");
            return; 
        }

        console.log("下单已触发，等待持仓上链...");
        const positionAppeared = await waitForPositionToAppear(10000); 
        
        if (!positionAppeared) {
            console.error("❌ 下单后10秒内未检测到持仓，可能下单失败。");
        }
    }

    async function checkAndFixTpSlForExistingPosition() {
        const row = document.querySelector(CONFIG.positionRowSelector);
        if (!row) return false;
        
        // === 极度宽容的检测逻辑 ===
        const rowText = row.innerText || "";
        
        // 只要包含 (2) 就认为设置好了 (误判概率极低，因为其他地方很少会出现 (2))
        if (rowText.includes("(2)")) {
            // console.log("✅ 检测到 (2)，跳过补设。");
            return false; 
        }
        
        // 也可以检测 span
        const spans = Array.from(row.querySelectorAll('span'));
        const hasTwo = spans.some(s => s.innerText.includes('(2)'));
        if (hasTwo) return false;

        console.log("⚠️ 未检测到 TP/SL 标记，准备补设...");

        let visibleInputs = Array.from(document.querySelectorAll(CONFIG.tpSlInputSelector))
            .filter(input => input.offsetParent !== null && !input.closest(CONFIG.positionRowSelector));
        
        if (visibleInputs.length < 2) {
             const allRowBtns = Array.from(row.querySelectorAll('button'));
             let addBtn = allRowBtns.find(b => b.getAttribute('title') === '创建 TP/SL');
             if (!addBtn) addBtn = allRowBtns.find(b => b.innerText.includes('创建 TP/SL'));
             if (!addBtn) addBtn = allRowBtns.find(b => b.innerHTML.includes('path d="M19 13H13V19H11V13H5V11H11V5H13V11H19V13Z"'));

             if (addBtn) {
                 console.log("点击打开设置弹窗...");
                 addBtn.click();
                 await sleep(1000); 
                 visibleInputs = Array.from(document.querySelectorAll(CONFIG.tpSlInputSelector))
                    .filter(input => input.offsetParent !== null && !input.closest(CONFIG.positionRowSelector));
             } else {
                 console.error("❌ 找不到设置按钮，本轮放弃");
                 return true; // 返回true以触发冷却，防止一直报错
             }
        }

        console.log(`找到 ${visibleInputs.length} 个输入框，填充中...`);
        
        let filledCount = 0;
        for (const input of visibleInputs) {
            if (input.offsetParent === null) continue;
            try {
                input.focus();
                input.value = CONFIG.tpValue; 
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.blur();
                filledCount++;
            } catch (e) {
                console.warn("填充失败:", e);
            }
        }

        if (filledCount > 0) {
            await sleep(500);
            const submitBtns = Array.from(document.querySelectorAll(CONFIG.modalSubmitBtnSelector))
                                    .filter(b => b.offsetParent !== null);
            let confirmBtn = submitBtns.find(b => b.innerText.includes("TP")); 
            if (!confirmBtn) confirmBtn = submitBtns[submitBtns.length - 1]; 

            if (confirmBtn && !confirmBtn.disabled) {
                confirmBtn.click();
                console.log("✅ 已点击确认。");
                await sleep(1500); 
                const closeBtn = document.querySelector('button[data-testid="close-button"]');
                if(closeBtn && closeBtn.offsetParent) closeBtn.click();
                return true;
            } else {
                console.warn("⚠️ 确认按钮不可用");
                if (confirmBtn) confirmBtn.click();
                const closeBtn = document.querySelector('button[data-testid="close-button"]');
                if(closeBtn && closeBtn.offsetParent) closeBtn.click();
                return true; 
            }
        } else {
            return true; 
        }
    }

    async function fillOrderPanelTpSl() {
        const allButtons = Array.from(document.querySelectorAll('button'));
        const toggleBtn = allButtons.find(b => !b.closest(CONFIG.positionRowSelector) && b.innerText.includes('创建 TP/SL'));

        let getPanelInputs = () => Array.from(document.querySelectorAll(CONFIG.tpSlInputSelector))
            .filter(input => input.offsetParent !== null && !input.closest(CONFIG.positionRowSelector) && !input.closest('.bg-darkblue-400'));

        let visibleInputs = getPanelInputs();

        if (visibleInputs.length < 2 && toggleBtn) {
            toggleBtn.click();
            await sleep(800);
            visibleInputs = getPanelInputs();
        }

        for (const input of visibleInputs) {
            input.focus();
            input.value = CONFIG.tpValue;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function waitForStartTime(timeStr) {
        const now = new Date();
        const [h, m, s] = timeStr.split(':').map(Number);
        const target = new Date(now);
        target.setHours(h||0, m||0, s||0, 0);
        let diff = target.getTime() - now.getTime();
        if (diff <= 0) { console.warn("⚠️ 时间已过，立即启动"); return; }
        console.log(`⏳ 等待启动: ${timeStr} (还有 ${Math.round(diff/1000)}秒)`);
        await new Promise(r => setTimeout(r, diff));
    }

    function hasPosition() {
        return document.querySelectorAll(CONFIG.positionRowSelector).length > 0;
    }

    async function waitForPositionToAppear(timeoutMs) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            if (hasPosition()) return true;
            await sleep(500);
        }
        return false;
    }

    async function waitAndClickOrder() {
        const btn = document.querySelector(CONFIG.orderBtnSelector);
        if (!btn) return false;
        const now = new Date();
        const delay = (CONFIG.interval - (now.getSeconds() % CONFIG.interval)) * 1000 - now.getMilliseconds();
        const finalDelay = delay < 1000 ? delay + (CONFIG.interval * 1000) : delay;
        const triggerTime = new Date(now.getTime() + finalDelay);
        console.log(`等待 ${Math.round(finalDelay/1000)} 秒后点击... (${triggerTime.toLocaleTimeString()})`);
        await sleep(finalDelay);
        const actionBtn = document.querySelector(CONFIG.orderBtnSelector);
        if (actionBtn) { actionBtn.click(); return true; }
        return false;
    }

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

})();

