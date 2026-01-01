"""
全自动对冲脚本 - Python 版本
使用 Selenium 控制两个浏览器，实现同步对冲交易
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
import time
import threading
import requests
import json


class HedgeBot:
    def __init__(self, driver, name, is_long=True, tp_value='3', sl_value='3'):
        self.driver = driver
        self.name = name
        self.is_long = is_long  # True=开多, False=开空（这个参数现在主要用于标识，实际方向会随机）
        self.has_position = False
        self.last_position_check = None  # 记录上次平仓时间
        self.tp_value = tp_value
        self.sl_value = sl_value
        self.current_direction = None  # 记录当前选择的方向（'long' 或 'short'）
        
    def has_position_now(self):
        """检查当前是否有持仓"""
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
            return len(elements) > 0
        except:
            return False
    
    def select_trading_pair(self, pair='BTC'):
        """选择交易币种（不打印消息，由调用者统一处理）"""
        try:
            # 首先检查是否已经有弹窗打开（币种选择弹窗）
            modal_open = False
            try:
                # 查找"Select an Asset"或类似的弹窗标题
                modal_titles = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select an Asset') or contains(text(), '选择资产') or contains(text(), '选择币种')]")
                if modal_titles:
                    modal_open = True
            except:
                pass
            
            # 如果弹窗已打开，直接在弹窗中选择
            if modal_open:
                time.sleep(0.5)
                
                # 方法1: 在弹窗中查找包含币种名称的行或按钮
                try:
                    # 查找包含币种文字的所有可点击元素
                    xpath = f"//*[contains(text(), '{pair}') and (self::button or self::div or self::span or self::a)]"
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    
                    for elem in elements:
                        # 确保在弹窗中，且包含币种信息
                        try:
                            # 检查是否在弹窗内（通过查找父元素中是否有"Select an Asset"文本）
                            parent = elem.find_element(By.XPATH, './ancestor::*[contains(text(), "Select") or contains(text(), "选择")]')
                            if parent:
                                # 滚动到元素可见
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                time.sleep(0.2)
                                elem.click()
                                time.sleep(0.5)
                                
                                # 等待弹窗关闭
                                time.sleep(0.5)
                                return {'success': True, 'method': '弹窗中直接选择'}
                        except:
                            continue
                except Exception as e:
                    pass
            
            # 如果弹窗未打开，尝试点击币种选择按钮打开弹窗
            if not modal_open:
                # 查找币种选择按钮（包含币种图标和文字的按钮）
                buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                pair_btn = None
                
                for btn in buttons:
                    btn_text = btn.text
                    btn_html = btn.get_attribute('innerHTML') or ''
                    
                    # 查找包含币种名称的按钮，且包含SVG图标和币种图片
                    if pair in btn_text and ('svg' in btn_html.lower() or 'bitcoin.png' in btn_html.lower() or 'coin-images' in btn_html.lower()):
                        # 确保不是其他地方的按钮（比如持仓列表）
                        try:
                            if btn.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                                continue
                        except:
                            pass
                        pair_btn = btn
                        break
                
                # 如果找到按钮，点击它打开弹窗
                if pair_btn:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pair_btn)
                    time.sleep(0.2)
                    pair_btn.click()
                    time.sleep(1)  # 等待弹窗打开
                    modal_open = True
                else:
                    return {'success': False, 'error': '未找到币种选择按钮'}
            
            # 在弹窗中选择币种
            if modal_open:
                time.sleep(0.5)
                
                # 方法1: 查找包含币种名称的行（表格行）
                try:
                    # 查找包含币种文字的行
                    xpath = f"//tr[.//*[contains(text(), '{pair}')]] | //div[contains(@class, 'row') and .//*[contains(text(), '{pair}')]]"
                    rows = self.driver.find_elements(By.XPATH, xpath)
                    
                    for row in rows:
                        try:
                            # 确保在弹窗中
                            row_text = row.text
                            if pair in row_text:
                                # 滚动到行可见
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                                time.sleep(0.2)
                                # 点击行或行中的币种文字
                                row.click()
                                time.sleep(0.5)
                                return {'success': True, 'method': '通过行点击'}
                        except:
                            continue
                except Exception as e:
                    pass
                
                # 方法2: 查找包含币种文字的可点击元素
                try:
                    xpath = f"//*[contains(text(), '{pair}') and (self::button or self::div or self::span or self::a or self::td)]"
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    
                    for elem in elements:
                        try:
                            elem_text = elem.text
                            if pair in elem_text and len(elem_text.strip()) < 20:  # 避免选择包含BTC的长文本
                                # 滚动到元素可见
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                time.sleep(0.2)
                                elem.click()
                                time.sleep(0.5)
                                return {'success': True, 'method': '通过元素点击'}
                        except:
                            continue
                except Exception as e:
                    pass
                
                return {'success': False, 'error': f'在弹窗中未找到 {pair}'}
            
            return {'success': False, 'error': '未知错误'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def select_order_direction(self, is_long=True):
        """选择开仓方向：开多（买）或开空（卖）"""
        try:
            # 查找包含"买"或"卖"的按钮
            buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            
            target_btn = None
            if is_long:
                # 开多：找包含"买"的按钮，且class包含"green"或"border-green"
                for btn in buttons:
                    btn_text = btn.text
                    btn_class = btn.get_attribute('class') or ''
                    if '买' in btn_text and ('green' in btn_class or 'border-green' in btn_class):
                        # 确保不是其他地方的按钮
                        try:
                            if btn.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                                continue
                        except:
                            pass
                        target_btn = btn
                        break
            else:
                # 开空：找包含"卖"的按钮
                for btn in buttons:
                    btn_text = btn.text
                    if '卖' in btn_text:
                        # 确保不是其他地方的按钮
                        try:
                            if btn.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                                continue
                        except:
                            pass
                        # 确保不是"买"按钮（有些按钮可能同时包含"买"和"卖"）
                        if '买' not in btn_text:
                            target_btn = btn
                            break
            
            if target_btn:
                # 检查按钮是否已选中（通过class判断）
                btn_class = target_btn.get_attribute('class') or ''
                if is_long:
                    # 开多按钮选中时应该有 border-green
                    if 'border-green' in btn_class and 'disabled' not in btn_class:
                        print(f"[{self.name}] 开多按钮已选中")
                        return True
                else:
                    # 开空按钮选中时可能没有特殊标记，或者有红色边框
                    if 'border-transparent' not in btn_class or 'text-red' in btn_class:
                        # 可能需要点击
                        pass
                
                target_btn.click()
                direction = "开多(买)" if is_long else "开空(卖)"
                self.current_direction = 'long' if is_long else 'short'
                print(f"[{self.name}] 已选择{direction}")
                time.sleep(0.5)
                return True
            else:
                print(f"[{self.name}] 未找到{'开多' if is_long else '开空'}按钮")
                return False
        except Exception as e:
            print(f"[{self.name}] 选择方向失败: {e}")
            return False
    
    def check_order_direction(self):
        """检查当前选择的订单方向（通过下单按钮文本判断）"""
        try:
            # 查找下单按钮（data-testid="submit-button"）
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
            if submit_btn:
                btn_text = submit_btn.text.strip()
                
                # 根据按钮文本判断方向
                if '买' in btn_text and 'BTC' in btn_text:
                    # "买 BTC" = 开多
                    self.current_direction = 'long'
                    return 'long'
                elif '卖' in btn_text and 'BTC' in btn_text:
                    # "卖 BTC" = 开空
                    self.current_direction = 'short'
                    return 'short'
            
            # 如果找不到下单按钮，尝试其他方法
            buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                btn_text = btn.text
                btn_class = btn.get_attribute('class') or ''
                
                # 检查是否是开多按钮（包含"买"且有绿色边框）
                if '买' in btn_text and 'border-green' in btn_class and 'disabled' not in btn_class:
                    self.current_direction = 'long'
                    return 'long'  # 开多
                # 检查是否是开空按钮（包含"卖"且可能被选中）
                elif '卖' in btn_text and '买' not in btn_text:
                    # 检查按钮是否被选中（可能有红色边框或特殊样式）
                    if 'border-transparent' not in btn_class or 'text-red' in btn_class or 'border-red' in btn_class:
                        self.current_direction = 'short'
                        return 'short'  # 开空
            
            # 如果无法从按钮状态判断，使用之前记录的方向
            return self.current_direction
        except Exception as e:
            print(f"[{self.name}] 检查方向时出错: {e}")
            return self.current_direction
    
    def fill_quantity(self, quantity):
        """填写开仓数量（不打印消息，由调用者统一处理）"""
        try:
            # 查找数量输入框
            quantity_input = self.driver.find_element(By.CSS_SELECTOR, 'input[data-testid="quantity-input"]')
            
            if quantity_input:
                # 清空并填写数量
                self.driver.execute_script("arguments[0].focus();", quantity_input)
                self.driver.execute_script("arguments[0].value = '';", quantity_input)
                self.driver.execute_script(f"arguments[0].value = '{quantity}';", quantity_input)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", quantity_input)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", quantity_input)
                time.sleep(0.3)
                return True
            else:
                return False
        except Exception as e:
            return False
    
    def check_insufficient_balance(self):
        """检查余额是否不足（通过检查下单按钮状态）"""
        try:
            # 查找下单按钮
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
            if submit_btn:
                # 检查按钮是否被禁用
                is_disabled = submit_btn.get_attribute('disabled') is not None
                btn_text = submit_btn.text.strip()
                
                # 检查按钮文本是否包含余额不足的提示
                insufficient_keywords = ['购买力超限', '余额不足', 'Insufficient', '余额不够', '资金不足']
                has_insufficient_text = any(keyword in btn_text for keyword in insufficient_keywords)
                
                if is_disabled or has_insufficient_text:
                    return True, btn_text
        except Exception as e:
            # 如果找不到按钮或出错，返回 False
            pass
        return False, None
    
    def fill_tp_sl(self, tp_value=None, sl_value=None):
        """填写止盈止损"""
        if tp_value is None:
            tp_value = self.tp_value
        if sl_value is None:
            sl_value = self.sl_value
        
        try:
            # 1. 点击"创建 TP/SL"按钮（如果还没展开）
            buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            toggle_btn = None
            for btn in buttons:
                if '创建 TP/SL' in btn.text or 'TP/SL' in btn.text:
                    # 确保不是持仓行里的按钮
                    try:
                        if btn.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                            continue
                    except:
                        pass
                    toggle_btn = btn
                    break
            
            if toggle_btn:
                toggle_btn.click()
                time.sleep(0.8)
            
            # 2. 填写输入框
            inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[data-testid="percentage-input"]')
            visible_inputs = [inp for inp in inputs if inp.is_displayed()]
            
            # 排除持仓行里的输入框
            position_inputs = []
            for inp in visible_inputs:
                try:
                    if inp.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                        continue
                except:
                    pass
                position_inputs.append(inp)
            
            # 填写所有可见的输入框
            for inp in position_inputs[:2]:  # 最多填两个
                self.driver.execute_script("arguments[0].focus();", inp)
                self.driver.execute_script("arguments[0].value = arguments[1];", inp, tp_value)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", inp)
                time.sleep(0.1)
            
            return True
        except Exception as e:
            print(f"[{self.name}] 填写TP/SL失败: {e}")
            return False
    
    def place_order(self):
        """下单（不打印消息，由调用者统一处理）"""
        try:
            # 只尝试一次点击，避免重复下单
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
                if btn:
                    # 检查按钮是否可见且可点击
                    if not btn.is_displayed():
                        time.sleep(0.4)
                        return False
                    
                    # 检查按钮是否被禁用
                    is_disabled = btn.get_attribute('disabled') is not None
                    if is_disabled:
                        # 如果按钮被禁用，说明可能正在处理中，等待一下再检查
                        time.sleep(0.5)
                        # 再次检查，如果仍然禁用，说明可能已经下单了
                        try:
                            btn_check = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
                            if btn_check.get_attribute('disabled') is not None:
                                return True  # 按钮被禁用，可能已经下单
                        except:
                            pass
                        return False
                    
                    # 保存点击前的按钮文本，用于后续比较
                    btn_text_before = btn.text.strip()
                    
                    # 尝试点击按钮
                    try:
                        btn.click()
                    except:
                        # 如果普通点击失败，使用JavaScript点击
                        self.driver.execute_script("arguments[0].click();", btn)
                    
                    # 点击后等待足够的时间，让页面有时间响应
                    time.sleep(1.0)  # 等待时间，确保页面有时间响应
                    
                    # 验证订单是否真正提交：检查按钮状态、页面变化或错误提示
                    try:
                        btn_after = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
                        btn_text_after = btn_after.text.strip()
                        
                        # 检查按钮是否被禁用（说明订单可能已提交）
                        if btn_after.get_attribute('disabled') is not None:
                            return True
                        
                        # 检查按钮文本是否变化（例如从"买入BTC"变成"提交中"等）
                        if btn_text_after and btn_text_after != btn_text_before:
                            return True
                        
                        # 检查是否有错误提示（说明订单可能被拒绝）
                        try:
                            error_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="error"], [class*="Error"], [data-testid*="error"]')
                            for elem in error_elements:
                                if elem.is_displayed() and elem.text.strip():
                                    # 如果有错误提示，返回False，让调用者知道下单可能失败
                                    return False
                        except:
                            pass
                        
                        # 如果按钮仍然可见且可点击，可能点击没有生效
                        # 但为了避免重复下单，我们假设点击已经生效，返回True
                        # 如果确实没有生效，会在后续的持仓检查中发现
                        return True
                    except:
                        # 如果找不到按钮了，可能说明页面状态变化，点击可能生效了
                        return True
                    
                    return True
            except Exception as e:
                return False
        except Exception as e:
            pass
        return False

    def _ensure_realized_pnl_tab(self):
        """确保已实现PnL标签被选中"""
        try:
            # 尝试多种方式查找"已实现PnL"标签
            visible_tab = None
            
            # 方式1: 通过文本内容查找所有按钮
            all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in all_buttons:
                try:
                    btn_text = btn.text.strip()
                    # 匹配 "已实现PnL" 或 "Realized PnL" 或 "已实现 PnL"
                    if ('已实现' in btn_text and 'PnL' in btn_text) or ('Realized' in btn_text and 'PnL' in btn_text):
                        if btn.is_displayed():
                            visible_tab = btn
                            break
                except:
                    continue
            
            # 方式2: 通过 role='tab' 属性查找
            if not visible_tab:
                tabs = self.driver.find_elements(By.CSS_SELECTOR, 'button[role="tab"]')
                for tab in tabs:
                    try:
                        tab_text = tab.text.strip()
                        if ('已实现' in tab_text and 'PnL' in tab_text) or ('Realized' in tab_text and 'PnL' in tab_text):
                            if tab.is_displayed():
                                visible_tab = tab
                                break
                    except:
                        continue
            
            # 方式3: 通过包含 span 的按钮查找
            if not visible_tab:
                spans = self.driver.find_elements(By.TAG_NAME, 'span')
                for span in spans:
                    try:
                        span_text = span.text.strip()
                        if ('已实现' in span_text and 'PnL' in span_text) or ('Realized' in span_text and 'PnL' in span_text):
                            # 找到包含这个 span 的可点击父元素
                            parent = span.find_element(By.XPATH, './ancestor::button')
                            if parent and parent.is_displayed():
                                visible_tab = parent
                                break
                    except:
                        continue
            
            if not visible_tab:
                raise Exception("未找到已实现PnL标签按钮")
            
            # 不再检查激活状态，直接点击标签（确保切换到正确的tab）
            # 滚动到标签可见并点击
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", visible_tab)
            time.sleep(0.3)
            
            # 强制使用 JS 点击，避免被其他元素遮挡
            self.driver.execute_script("arguments[0].click();", visible_tab)
            
            time.sleep(0.8)
            return True
        except Exception as e:
            print(f"[{self.name}] 切换到已实现PnL标签失败: {e}")
            return False

    def _ensure_positions_tab(self):
        """切换回仓位标签"""
        try:
            visible_tab = None
            
            # 通过文本内容查找"仓位"或"Positions"标签
            all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in all_buttons:
                try:
                    btn_text = btn.text.strip()
                    # 匹配 "仓位" 或 "Positions"
                    if btn_text == '仓位' or btn_text == 'Positions' or ('仓位' in btn_text and 'PnL' not in btn_text):
                        if btn.is_displayed():
                            visible_tab = btn
                            break
                except:
                    continue
            
            if not visible_tab:
                # 通过 role='tab' 属性查找
                tabs = self.driver.find_elements(By.CSS_SELECTOR, 'button[role="tab"]')
                for tab in tabs:
                    try:
                        tab_text = tab.text.strip()
                        if tab_text == '仓位' or tab_text == 'Positions':
                            if tab.is_displayed():
                                visible_tab = tab
                                break
                    except:
                        continue
            
            if not visible_tab:
                print(f"[{self.name}] 未找到仓位标签")
                return False
            
            # 强制使用 JS 点击
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", visible_tab)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", visible_tab)
            # 已切换回仓位标签（不打印，减少日志冗余）
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[{self.name}] 切换回仓位标签失败: {e}")
            return False

    def get_realized_pnl(self):
        """读取最新一条已实现PnL记录 (返回 amount, currency, raw_text)"""
        try:
            if not self._ensure_realized_pnl_tab():
                return None

            # 等待表格行出现（不强制要求可见，避免受容器滚动/遮挡影响）
            # 说明：有些情况下交易所写入已实现PnL记录会有数秒延迟，这里给足 15 秒缓冲，只在每轮平仓后调用一次，不影响平仓时效
            wait = WebDriverWait(self.driver, 15)
            row = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div[data-testid="transfers-table-row"]')
                )
            )

            columns = row.find_elements(By.CSS_SELECTOR, 'div.leading-6')
            if len(columns) < 3:
                print(f"[{self.name}] 未找到已实现PnL列数据")
                return None

            asset = columns[1].text.strip()
            amount_text = columns[2].text.strip()

            amount_value = None
            normalized_text = amount_text.replace(',', '').replace('USDC', '').strip()
            try:
                amount_value = float(normalized_text)
            except ValueError:
                pass

            return {
                'amount_text': amount_text,
                'amount_value': amount_value,
                'currency': asset or 'USDC'
            }
        except TimeoutException:
            # 超时多数是当前还没有任何已实现PnL记录（或记录尚未写入表格）
            print(f"[{self.name}] 读取已实现PnL超时（已等待15秒）：当前可能还没有PnL记录")
        except Exception as e:
            # 避免打印整段 Selenium 堆栈，只给简短提示
            msg = getattr(e, "msg", None) or str(e)
            print(f"[{self.name}] 读取已实现PnL失败: {msg}")
            return None

    def report_realized_pnl(self):
        """获取当前已实现PnL信息（返回数据，不打印）"""
        try:
            pnl = self.get_realized_pnl()
            if not pnl:
                return None

            currency = pnl['currency'] or 'USDC'
            if pnl['amount_value'] is not None:
                amount_display = f"{pnl['amount_value']:+.4f}"
            else:
                amount_display = pnl['amount_text']

            return {
                'amount_display': amount_display,
                'amount_value': pnl.get('amount_value'),  # 确保包含数值
                'currency': currency
            }
        finally:
            # 无论成功与否，都切换回仓位标签
            self._ensure_positions_tab()
    
    def close_position(self):
        """主动平仓"""
        try:
            print(f"[{self.name}] 开始平仓流程...")
            
            # 首先检查是否还有持仓（可能已经被TP/SL自动平仓）
            if not self.has_position_now():
                print(f"[{self.name}] ✅ 持仓已不存在，可能已被TP/SL自动平仓")
                return True
            
            # 尝试找到持仓行
            try:
                row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
            except:
                # 如果找不到持仓行，说明已经平仓了
                print(f"[{self.name}] ✅ 未找到持仓行，持仓可能已被平仓")
                return True
            
            buttons = row.find_elements(By.TAG_NAME, 'button')
            
            # 找"关闭"按钮（在持仓行中）
            close_btn = None
            for btn in buttons:
                btn_text = btn.text.strip()
                if btn_text == '关闭' or '关闭' in btn_text:
                    # 确保按钮可见且可点击
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            close_btn = btn
                            break
                    except:
                        pass
            
            if close_btn:
                print(f"[{self.name}] 找到关闭按钮，准备点击...")
                # 滚动到按钮可见（不等待）
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                
                # 点击关闭按钮
                try:
                    close_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", close_btn)
                
                print(f"[{self.name}] 已点击关闭按钮，等待平仓弹窗...")
                # 使用智能等待，最多等待1秒（加快速度）
                try:
                    wait = WebDriverWait(self.driver, 1)
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="close-position-button"]')))
                except:
                    time.sleep(0.3)  # 如果智能等待失败，短暂等待
                
                # 再次检查持仓状态（可能在点击关闭前已经被TP/SL平仓）
                if not self.has_position_now():
                    print(f"[{self.name}] ✅ 点击关闭后，持仓已消失，可能已被TP/SL自动平仓")
                    return True
                
                # 查找平仓确认按钮（使用 data-testid="close-position-button"）
                confirm_btn = None
                try:
                    # 使用 WebDriverWait 等待按钮出现（最多等待1秒，加快速度）
                    wait = WebDriverWait(self.driver, 1)
                    confirm_btn = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="close-position-button"]'))
                    )
                except:
                    # 如果等待超时，尝试直接查找
                    try:
                        confirm_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="close-position-button"]')
                    except:
                        pass
                
                if confirm_btn:
                    try:
                        if confirm_btn.is_displayed():
                            print(f"[{self.name}] 找到平仓确认按钮: {confirm_btn.text}")
                            # 滚动到按钮可见（不等待）
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_btn)
                            
                            # 点击确认按钮
                            try:
                                confirm_btn.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", confirm_btn)
                            
                            print(f"[{self.name}] ✅ 已点击平仓确认按钮")
                            # 使用智能等待持仓消失，最多等待1.5秒（加快速度）
                            try:
                                wait = WebDriverWait(self.driver, 1.5)
                                wait.until(lambda driver: not self.has_position_now())
                                print(f"[{self.name}] ✅ 平仓成功，持仓已消失")
                                return True
                            except:
                                # 如果智能等待失败，短暂等待后检查
                                time.sleep(0.3)
                                if not self.has_position_now():
                                    print(f"[{self.name}] ✅ 平仓成功，持仓已消失")
                                    return True
                                else:
                                    print(f"[{self.name}] ⚠️  点击确认后，持仓仍然存在")
                                    return False
                    except Exception as e:
                        print(f"[{self.name}] ⚠️  点击确认按钮时出错: {e}")
                
                # 如果找不到确认按钮，检查持仓状态
                print(f"[{self.name}] ⚠️  未找到平仓确认按钮，检查持仓状态...")
                time.sleep(0.2)  # 短暂等待（加快速度）
                
                # 再次检查持仓
                if not self.has_position_now():
                    print(f"[{self.name}] ✅ 持仓已消失，可能已被TP/SL自动平仓或已成功平仓")
                    return True
                
                # 如果持仓还在，尝试备用方法
                try:
                    # 检查是否还有持仓行
                    row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
                    # 如果还能找到持仓行，说明还没平仓，尝试备用方法
                    print(f"[{self.name}] 持仓行仍存在，尝试备用方法...")
                    all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                    for btn in all_buttons:
                        try:
                            if btn.is_displayed():
                                btn_text = btn.text
                                if ('平仓' in btn_text or 'Close' in btn_text) and 'close-position-button' in (btn.get_attribute('data-testid') or ''):
                                    print(f"[{self.name}] 找到备用平仓按钮: {btn_text}")
                                    try:
                                        btn.click()
                                        time.sleep(0.5)  # 减少等待时间（加快速度）
                                        if not self.has_position_now():
                                            return True
                                    except:
                                        pass
                        except:
                            continue
                except:
                    # 找不到持仓行，说明可能已经平仓了
                    print(f"[{self.name}] ✅ 持仓行已消失，可能已经平仓")
                    return True
            else:
                print(f"[{self.name}] ⚠️  未找到关闭按钮")
                # 即使找不到关闭按钮，也检查一下持仓状态
                if not self.has_position_now():
                    print(f"[{self.name}] ✅ 持仓已不存在，可能已被TP/SL自动平仓")
                    return True
        except Exception as e:
            print(f"[{self.name}] ❌ 平仓失败: {e}")
            # 即使出错，也检查一下持仓状态
            try:
                if not self.has_position_now():
                    print(f"[{self.name}] ✅ 虽然出错，但持仓已消失，可能已平仓")
                    return True
            except:
                pass
        return False
    
    def check_and_fix_tp_sl(self):
        """检查并补设TP/SL（返回状态信息，不直接打印）"""
        try:
            row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
            row_text = row.text
            
            # 如果已经有 (2) 订单，说明已设置
            if '(2)' in row_text:
                return {'success': False, 'already_set': True}
            
            # 点击"创建 TP/SL"按钮
            buttons = row.find_elements(By.TAG_NAME, 'button')
            add_btn = None
            for btn in buttons:
                btn_text = btn.text
                btn_title = btn.get_attribute('title') or ''
                btn_inner_html = btn.get_attribute('innerHTML') or ''
                
                # 多种方式查找"创建 TP/SL"按钮
                if ('创建 TP/SL' in btn_text or 
                    '创建 TP/SL' in btn_title or
                    ('TP' in btn_text and 'SL' in btn_text) or
                    ('创建' in btn_text and 'TP' in btn_text)):
                    # 确保按钮可见且可点击
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            add_btn = btn
                            break
                    except:
                        pass
                
                # 备用方法：通过SVG路径查找（用户提供的SVG特征）
                if not add_btn and 'M19 13H13V19H11V13H5V11H11V5H13V11H19V13Z' in btn_inner_html:
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            add_btn = btn
                            break
                    except:
                        pass
            
            if add_btn:
                # 滚动到按钮可见
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_btn)
                time.sleep(0.3)
                
                # 尝试多种点击方式
                try:
                    add_btn.click()
                except:
                    # 如果普通点击失败，使用JavaScript点击
                    self.driver.execute_script("arguments[0].click();", add_btn)
                
                time.sleep(1.5)  # 等待弹窗打开
                
                # 填写弹窗
                inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[data-testid="percentage-input"]')
                visible_inputs = [inp for inp in inputs if inp.is_displayed()]
                
                # 排除持仓行里的输入框
                modal_inputs = []
                for inp in visible_inputs:
                    try:
                        # 检查是否在弹窗中（不在持仓行中）
                        if not inp.find_element(By.XPATH, './ancestor::div[@data-testid="positions-table-row"]'):
                            modal_inputs.append(inp)
                    except:
                        # 如果找不到持仓行，说明不在持仓行中，可以添加
                        modal_inputs.append(inp)
                
                # 填写输入框（不打印，由调用者统一处理）
                filled_count = 0
                for i, inp in enumerate(modal_inputs[:2]):  # 最多填两个（止盈和止损）
                    try:
                        self.driver.execute_script("arguments[0].focus();", inp)
                        self.driver.execute_script(f"arguments[0].value = '{self.tp_value}';", inp)
                        self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", inp)
                        self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", inp)
                        filled_count += 1
                        time.sleep(0.2)
                    except Exception as e:
                        pass
                
                time.sleep(0.5)
                
                # 点击确认按钮
                submit_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
                visible_submits = [b for b in submit_btns if b.is_displayed()]
                
                if visible_submits:
                    # 找到弹窗中的确认按钮（通常是最新的或包含"TP"的）
                    confirm_btn = None
                    for btn in visible_submits:
                        btn_text = btn.text
                        if 'TP' in btn_text or '确认' in btn_text or 'Create' in btn_text:
                            confirm_btn = btn
                            break
                    
                    if not confirm_btn:
                        confirm_btn = visible_submits[-1]  # 使用最后一个可见的
                    
                    try:
                        confirm_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", confirm_btn)
                    
                    time.sleep(1)
                    
                    # 关闭弹窗（如果还在）
                    try:
                        close_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="close-button"]')
                        if close_btn.is_displayed():
                            close_btn.click()
                            time.sleep(0.5)
                    except:
                        pass
                    
                    # 返回成功状态和相关信息（不打印，由调用者统一处理）
                    return {
                        'success': True,
                        'input_count': len(modal_inputs),
                        'filled_count': filled_count,
                        'tp_value': self.tp_value
                    }
                else:
                    return {'success': False, 'error': '未找到确认按钮'}
            else:
                return {'success': False, 'error': '未找到创建 TP/SL 按钮'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        return {'success': False, 'error': '未知错误'}


class MoreLoginAPI:
    """MoreLogin API 客户端"""
    def __init__(self, api_url="http://127.0.0.1:40000", api_id=None, api_key=None):
        """
        初始化 MoreLogin API 客户端
        
        参数:
            api_url: MoreLogin API 地址，默认是本地 40000 端口
            api_id: MoreLogin API ID（用于认证）
            api_key: MoreLogin API Key（用于认证）
        """
        self.api_url = api_url.rstrip('/')
        self.api_id = api_id
        self.api_key = api_key
    
    def _get_headers(self):
        """获取请求头（包含认证信息）"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.api_id and self.api_key:
            # MoreLogin API 认证头格式
            # 根据常见 API 格式，使用 X-API-ID 和 X-API-Key
            api_id_str = str(self.api_id).strip()
            api_key_str = str(self.api_key).strip()
            
            headers['X-API-ID'] = api_id_str
            headers['X-API-Key'] = api_key_str
        return headers
    
    def start_env(self, env_id=None, unique_id=None, encrypt_key=None, is_headless=False, cdp_evasion=False):
        """
        启动浏览器环境
        
        参数:
            env_id: 环境ID
            unique_id: 环境序号
            encrypt_key: 密钥（如果环境开启了端对端加密）
            is_headless: 是否无头模式
            cdp_evasion: 是否启用CDP特征规避
        
        返回:
            dict: 包含 envId, debugPort, webdriver 路径
        """
        url = f"{self.api_url}/api/env/start"
        
        # 构建请求体，根据 MoreLogin API 文档格式
        # uniqueId 必须是 integer(int32) 类型
        # envId 必须是 string 类型
        data = {}
        if env_id:
            data["envId"] = str(env_id)  # envId 是 string 类型
        if unique_id:
            # uniqueId 必须是 integer(int32) 类型（根据 API 文档）
            try:
                data["uniqueId"] = int(unique_id)
            except (ValueError, TypeError):
                raise Exception(f"uniqueId 必须是整数类型，当前值: {unique_id} (类型: {type(unique_id)})")
        if encrypt_key:
            data["encryptKey"] = str(encrypt_key)
        if is_headless:
            data["isHeadless"] = bool(is_headless)
        if cdp_evasion:
            data["cdpEvasion"] = bool(cdp_evasion)
        
        # 确保至少有一个标识符
        if not data:
            raise Exception("必须提供 envId 或 uniqueId 之一")
        
        try:
            headers = self._get_headers()
            
            # 调试：打印请求信息（不打印敏感信息）
            print(f"[调试] 请求 URL: {url}")
            print(f"[调试] 请求数据: {data}")
            print(f"[调试] 使用认证: {'是' if (self.api_id and self.api_key) else '否'}")
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            # 检查响应状态
            print(f"[调试] 响应状态码: {response.status_code}")
            
            # 尝试解析 JSON
            try:
                result = response.json()
            except ValueError as e:
                # 如果无法解析 JSON，打印原始响应
                print(f"[调试] 响应内容: {response.text[:500]}")
                raise Exception(f"API 返回了无效的 JSON 格式。响应: {response.text[:200]}")
            
            print(f"[调试] API 响应: {result}")
            
            if result.get("code") == 0:
                return result.get("data", {})
            else:
                error_msg = result.get('msg', result.get('message', '未知错误'))
                raise Exception(f"启动环境失败: {error_msg}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"无法连接到 MoreLogin API ({self.api_url})。请确保：\n"
                          f"1. MoreLogin 客户端已启动\n"
                          f"2. MoreLogin 客户端已登录\n"
                          f"3. API 服务正在运行\n"
                          f"4. API URL 正确（在 MoreLogin API 设置中查看）\n"
                          f"或者使用其他方式（远程调试端口或浏览器路径）")
        except requests.exceptions.Timeout:
            raise Exception(f"连接 MoreLogin API 超时。请检查网络连接。")
        except Exception as e:
            # 重新抛出其他异常，但添加更多上下文
            error_msg = str(e)
            if "Http message not readable" in error_msg:
                raise Exception(f"API 请求格式错误: {error_msg}\n"
                              f"可能的原因：\n"
                              f"1. API ID 或 API Key 格式不正确\n"
                              f"2. 请求体格式不正确\n"
                              f"3. API 版本不匹配\n"
                              f"请检查 MoreLogin API 文档或使用远程调试端口方式")
            raise
    
    def close_env(self, env_id=None, unique_id=None):
        """关闭浏览器环境"""
        url = f"{self.api_url}/api/env/close"
        data = {}
        if env_id:
            data["envId"] = env_id
        if unique_id:
            data["uniqueId"] = unique_id
        
        headers = self._get_headers()
        response = requests.post(url, json=data, headers=headers)
        result = response.json()
        
        if result.get("code") == 0:
            return result.get("data", {})
        else:
            raise Exception(f"关闭环境失败: {result.get('msg', '未知错误')}")
    
    def get_env_status(self, env_id=None, unique_id=None):
        """
        获取浏览器环境运行状态
        
        参数:
            env_id: 环境ID（string）
            unique_id: 环境序号（integer）
        
        返回:
            dict: 包含 envId, status, localStatus, debugPort, webdriver
        """
        url = f"{self.api_url}/api/env/status"
        data = {}
        if env_id:
            data["envId"] = str(env_id)
        elif unique_id:
            # 注意：根据文档，status 接口只接受 envId，不接受 uniqueId
            # 所以如果只有 uniqueId，需要先通过其他方式获取 envId
            raise Exception("get_env_status 接口需要 envId，不支持 uniqueId。请使用 envId 或先通过其他方式获取 envId")
        else:
            raise Exception("必须提供 envId")
        
        try:
            headers = self._get_headers()
            response = requests.post(url, json=data, headers=headers, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                return result.get("data", {})
            else:
                error_msg = result.get('msg', result.get('message', '未知错误'))
                raise Exception(f"获取环境状态失败: {error_msg}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"无法连接到 MoreLogin API ({self.api_url})。请确保 MoreLogin 客户端已启动并登录。")
        except Exception as e:
            raise


class TelegramNotifier:
    """Telegram 推送通知类"""
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage" if bot_token else None
    
    def send_message(self, message):
        """发送消息到Telegram"""
        if not self.bot_token or not self.chat_id:
            return False
        
        try:
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(self.api_url, json=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                print(f"TG推送失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"TG推送异常: {e}")
            return False


class DualBrowserHedgeBot:
    def __init__(self, url, start_time=None, morelogin_port1=None, morelogin_port2=None, 
                 morelogin_path1=None, morelogin_path2=None, morelogin_env1=None, morelogin_env2=None,
                 morelogin_api_url="http://127.0.0.1:40000", morelogin_api_id=None, morelogin_api_key=None,
                 keep_browsers_open=False, tg_bot_token=None, tg_chat_id=None):
        """
        初始化对冲机器人
        
        参数:
            url: 交易页面URL
            start_time: 启动时间
            morelogin_port1/2: MoreLogin 远程调试端口（手动模式）
            morelogin_path1/2: MoreLogin 浏览器路径（手动模式）
            morelogin_env1/2: MoreLogin 环境ID或序号（API模式）
            morelogin_api_url: MoreLogin API 地址
            morelogin_api_id: MoreLogin API ID（用于认证）
            morelogin_api_key: MoreLogin API Key（用于认证）
        """
        self.url = url
        self.start_time = start_time
        self.bot1 = None  # 浏览器1
        self.bot2 = None  # 浏览器2
        self.running = False
        self.morelogin_port1 = morelogin_port1
        self.morelogin_port2 = morelogin_port2
        self.morelogin_path1 = morelogin_path1
        self.morelogin_path2 = morelogin_path2
        self.morelogin_env1 = morelogin_env1
        self.morelogin_env2 = morelogin_env2
        self.morelogin_api = MoreLoginAPI(morelogin_api_url, morelogin_api_id, morelogin_api_key) if (morelogin_env1 or morelogin_env2) else None
        self.morelogin_env_data1 = None  # 存储环境1的启动数据
        self.morelogin_env_data2 = None  # 存储环境2的启动数据
        self.tp_value = '3'  # 默认值，会从配置读取
        self.sl_value = '3'  # 默认值，会从配置读取
        self.order_interval = 10  # 默认值，会从配置读取
        self.cooldown_after_close = 120  # 默认值，会从配置读取
        self.wait_before_force_close = 30  # 默认值，会从配置读取
        self.trading_pair_selected = False  # 标记是否已选择过币种
        self.pnl_reported = False  # 标记当前这一轮平仓后的PnL是否已打印
        self.keep_browsers_open = keep_browsers_open  # 是否在脚本退出时保留浏览器
        self.tg_notifier = TelegramNotifier(tg_bot_token, tg_chat_id) if (tg_bot_token and tg_chat_id) else None
        self.push_count = 0  # 推送次数统计
        self.total_pnl = 0.0  # 累计总盈亏（USDC单位）
        self._opening_order = False  # 标记是否正在开新单，避免重复执行
        
    def init_drivers(self):
        """初始化两个浏览器"""
        chrome_options1 = Options()
        chrome_options2 = Options()
        driver1 = None
        driver2 = None

        # ========== 优先方式: 使用本地 Chrome + 用户数据目录（不依赖 MoreLogin）==========
        try:
            from config import LOCAL_CHROME_PATH, LOCAL_PROFILE1, LOCAL_PROFILE2, CHROMEDRIVER_PATH
        except ImportError:
            LOCAL_CHROME_PATH = None
            LOCAL_PROFILE1 = None
            LOCAL_PROFILE2 = None
            CHROMEDRIVER_PATH = None
        except Exception:
            LOCAL_CHROME_PATH = None
            LOCAL_PROFILE1 = None
            LOCAL_PROFILE2 = None
            CHROMEDRIVER_PATH = None

        if LOCAL_CHROME_PATH and LOCAL_PROFILE1 and LOCAL_PROFILE2:
            print("=" * 60)
            print("使用本地 Chrome 和用户数据目录启动两个浏览器...")
            print("=" * 60)

            # 浏览器1
            chrome_options1.binary_location = LOCAL_CHROME_PATH
            chrome_options1.add_argument(f'--user-data-dir={LOCAL_PROFILE1}')
            chrome_options1.add_argument('--no-first-run')
            chrome_options1.add_argument('--no-default-browser-check')

            # 浏览器2
            chrome_options2.binary_location = LOCAL_CHROME_PATH
            chrome_options2.add_argument(f'--user-data-dir={LOCAL_PROFILE2}')
            chrome_options2.add_argument('--no-first-run')
            chrome_options2.add_argument('--no-default-browser-check')

            # 启动两个 ChromeDriver
            if CHROMEDRIVER_PATH:
                print(f"使用指定的 ChromeDriver 路径: {CHROMEDRIVER_PATH}")
                driver1 = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options1)
                driver2 = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options2)
            else:
                print("未指定 CHROMEDRIVER_PATH，将使用系统 PATH 中的 chromedriver")
                driver1 = webdriver.Chrome(options=chrome_options1)
                driver2 = webdriver.Chrome(options=chrome_options2)

            print("正在启动本地浏览器1和浏览器2...")
            driver1.get(self.url)
            driver2.get(self.url)
            time.sleep(3)

            # 初始化 bot（本地浏览器方式）
            if driver1 and driver2:
                try:
                    from config import TP_VALUE, SL_VALUE, TRADING_PAIR, ORDER_QUANTITY
                    tp_val = TP_VALUE
                    sl_val = SL_VALUE
                    self.trading_pair = TRADING_PAIR
                    self.order_quantity = ORDER_QUANTITY
                except Exception:
                    tp_val = '3'
                    sl_val = '3'
                    self.trading_pair = 'BTC'
                    self.order_quantity = '0.01'

                self.bot1 = HedgeBot(driver1, "浏览器1", is_long=True, tp_value=tp_val, sl_value=sl_val)
                self.bot2 = HedgeBot(driver2, "浏览器2", is_long=False, tp_value=tp_val, sl_value=sl_val)

                try:
                    from config import ORDER_INTERVAL, COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
                    self.order_interval = ORDER_INTERVAL
                    self.cooldown_after_close = COOLDOWN_AFTER_CLOSE
                    self.wait_before_force_close = WAIT_BEFORE_FORCE_CLOSE
                except Exception:
                    pass

                print("✅ 两个本地浏览器已就绪！")
                return
        
        # ========== 方式1: 使用 MoreLogin API 启动环境（推荐）==========
        api_failed = False
        # 检查是否配置了 API 但未配置环境ID
        if (self.morelogin_api is not None) and not (self.morelogin_env1 or self.morelogin_env2):
            print("⚠️  警告: MoreLogin API 已初始化，但未配置环境ID")
            print("   请在 config.py 中配置 MORELOGIN_ENV1 和 MORELOGIN_ENV2")
            print("   环境ID 可以在 MoreLogin 客户端中查看")
        
        if self.morelogin_api and (self.morelogin_env1 or self.morelogin_env2):
            print("="*60)
            print("尝试使用 MoreLogin API 启动浏览器环境...")
            print("="*60)
            
            # 启动环境1
            if self.morelogin_env1:
                print(f"\n正在通过 API 启动环境1 (envId/uniqueId: {self.morelogin_env1})...")
                try:
                    # 判断是 envId 还是 uniqueId
                    # 根据文档：envId 是 string（通常是长数字字符串），uniqueId 是 integer(int32)（通常是 1, 2, 3...）
                    # 判断逻辑：如果数字很大（>1000），应该是 envId；如果数字很小（<=1000），可能是 uniqueId
                    is_digit = isinstance(self.morelogin_env1, int) or (isinstance(self.morelogin_env1, str) and self.morelogin_env1.isdigit())
                    
                    if is_digit:
                        num_value = int(self.morelogin_env1)
                        # 如果数字很大（>1000），应该是 envId（环境ID）
                        # 如果数字很小（<=1000），可能是 uniqueId（环境序号）
                        if num_value > 1000:
                            # 大数字，作为 envId 处理
                            print(f"  使用 envId (环境ID): {str(self.morelogin_env1)}")
                            self.morelogin_env_data1 = self.morelogin_api.start_env(env_id=str(self.morelogin_env1))
                        else:
                            # 小数字，作为 uniqueId 处理
                            print(f"  使用 uniqueId (环境序号): {num_value}")
                            self.morelogin_env_data1 = self.morelogin_api.start_env(unique_id=num_value)
                    else:
                        # 非纯数字，作为 envId 处理
                        print(f"  使用 envId (环境ID): {str(self.morelogin_env1)}")
                        self.morelogin_env_data1 = self.morelogin_api.start_env(env_id=str(self.morelogin_env1))
                    
                    # 从返回数据中提取信息
                    env_id1 = self.morelogin_env_data1.get("envId")
                    debug_port1 = self.morelogin_env_data1.get("debugPort")
                    webdriver_path1 = self.morelogin_env_data1.get("webdriver")
                    
                    if not debug_port1:
                        raise Exception("API 返回数据中缺少 debugPort")
                    
                    print(f"✅ 环境1启动成功:")
                    print(f"   envId: {env_id1}")
                    print(f"   debugPort: {debug_port1}")
                    print(f"   webdriver: {webdriver_path1 if webdriver_path1 else '未提供，将尝试获取'}")
                    
                    # 如果 webdriver 路径未提供，尝试通过 get_env_status 获取
                    if not webdriver_path1 and env_id1:
                        try:
                            print(f"  尝试通过 get_env_status 获取 webdriver 路径...")
                            status_data = self.morelogin_api.get_env_status(env_id=env_id1)
                            webdriver_path1 = status_data.get("webdriver")
                            if webdriver_path1:
                                print(f"  ✅ 成功获取 webdriver 路径: {webdriver_path1}")
                        except Exception as e:
                            print(f"  ⚠️  无法获取 webdriver 路径: {e}")
                    
                    # 使用返回的 webdriver 和 debugPort 连接浏览器
                    chrome_options1.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port1}")
                    if webdriver_path1:
                        print(f"  使用 MoreLogin 提供的 webdriver: {webdriver_path1}")
                        try:
                            driver1 = webdriver.Chrome(service=Service(webdriver_path1), options=chrome_options1)
                        except Exception as e:
                            print(f"  ⚠️  使用提供的 webdriver 失败: {e}")
                            print(f"  尝试使用系统默认 webdriver...")
                            try:
                                driver1 = webdriver.Chrome(options=chrome_options1)
                            except Exception as e2:
                                error_msg = str(e2)
                                if "version" in error_msg.lower() or "chromedriver" in error_msg.lower():
                                    # 版本不匹配，建议使用远程调试端口
                                    print(f"\n❌ ChromeDriver 版本不匹配！")
                                    print(f"  错误: {error_msg}")
                                    print(f"\n💡 解决方案：使用远程调试端口方式")
                                    print(f"  1. 在 config.py 中配置：")
                                    print(f"     MORELOGIN_PORT1 = {debug_port1}")
                                    print(f"  2. 或者手动在 MoreLogin 中启用远程调试端口")
                                    raise Exception(f"ChromeDriver 版本不匹配。请使用远程调试端口方式（端口: {debug_port1}）")
                                raise
                    else:
                        print(f"  ⚠️  API 未返回 webdriver 路径，尝试使用系统默认 webdriver")
                        try:
                            driver1 = webdriver.Chrome(options=chrome_options1)
                        except Exception as e:
                            error_msg = str(e)
                            if "version" in error_msg.lower() or "chromedriver" in error_msg.lower():
                                # 版本不匹配，建议使用远程调试端口
                                print(f"\n❌ ChromeDriver 版本不匹配！")
                                print(f"  错误: {error_msg}")
                                print(f"\n💡 解决方案：使用远程调试端口方式")
                                print(f"  1. 在 config.py 中配置：")
                                print(f"     MORELOGIN_PORT1 = {debug_port1}")
                                print(f"  2. 或者手动在 MoreLogin 中启用远程调试端口")
                                raise Exception(f"ChromeDriver 版本不匹配。请使用远程调试端口方式（端口: {debug_port1}）")
                            raise
                    
                    print("✅ 浏览器1已成功连接到 MoreLogin 环境")
                    
                    # 导航到目标URL
                    print(f"正在导航到交易页面: {self.url}")
                    driver1.get(self.url)
                    time.sleep(3)
                    print("✅ 浏览器1已导航到交易页面")
                except Exception as e:
                    print(f"❌ API 启动环境1失败: {e}")
                    print("\n提示: 如果 MoreLogin API 不可用，请使用以下方式之一：")
                    print("  1. 在 MoreLogin 中手动打开浏览器，然后使用远程调试端口连接（推荐）")
                    print("  2. 在 config.py 中配置 MORELOGIN_PORT1 和 MORELOGIN_PORT2")
                    print("  3. 在 config.py 中配置 MORELOGIN_PATH1 和 MORELOGIN_PATH2")
                    api_failed = True
            
            # 启动环境2
            if self.morelogin_env2 and not api_failed:
                print(f"\n正在通过 API 启动环境2 (envId/uniqueId: {self.morelogin_env2})...")
                try:
                    # 判断是 envId 还是 uniqueId
                    # 根据文档：envId 是 string（通常是长数字字符串），uniqueId 是 integer(int32)（通常是 1, 2, 3...）
                    # 判断逻辑：如果数字很大（>1000），应该是 envId；如果数字很小（<=1000），可能是 uniqueId
                    is_digit = isinstance(self.morelogin_env2, int) or (isinstance(self.morelogin_env2, str) and str(self.morelogin_env2).isdigit())
                    
                    if is_digit:
                        num_value = int(self.morelogin_env2)
                        # 如果数字很大（>1000），应该是 envId（环境ID）
                        # 如果数字很小（<=1000），可能是 uniqueId（环境序号）
                        if num_value > 1000:
                            # 大数字，作为 envId 处理
                            print(f"  使用 envId (环境ID): {str(self.morelogin_env2)}")
                            self.morelogin_env_data2 = self.morelogin_api.start_env(env_id=str(self.morelogin_env2))
                        else:
                            # 小数字，作为 uniqueId 处理
                            print(f"  使用 uniqueId (环境序号): {num_value}")
                            self.morelogin_env_data2 = self.morelogin_api.start_env(unique_id=num_value)
                    else:
                        # 非纯数字，作为 envId 处理
                        print(f"  使用 envId (环境ID): {str(self.morelogin_env2)}")
                        self.morelogin_env_data2 = self.morelogin_api.start_env(env_id=str(self.morelogin_env2))
                    
                    # 从返回数据中提取信息
                    env_id2 = self.morelogin_env_data2.get("envId")
                    debug_port2 = self.morelogin_env_data2.get("debugPort")
                    webdriver_path2 = self.morelogin_env_data2.get("webdriver")
                    
                    if not debug_port2:
                        raise Exception("API 返回数据中缺少 debugPort")
                    
                    print(f"✅ 环境2启动成功:")
                    print(f"   envId: {env_id2}")
                    print(f"   debugPort: {debug_port2}")
                    print(f"   webdriver: {webdriver_path2 if webdriver_path2 else '未提供，将尝试获取'}")
                    
                    # 如果 webdriver 路径未提供，尝试通过 get_env_status 获取
                    if not webdriver_path2 and env_id2:
                        try:
                            print(f"  尝试通过 get_env_status 获取 webdriver 路径...")
                            status_data = self.morelogin_api.get_env_status(env_id=env_id2)
                            webdriver_path2 = status_data.get("webdriver")
                            if webdriver_path2:
                                print(f"  ✅ 成功获取 webdriver 路径: {webdriver_path2}")
                        except Exception as e:
                            print(f"  ⚠️  无法获取 webdriver 路径: {e}")
                    
                    chrome_options2.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port2}")
                    if webdriver_path2:
                        print(f"  使用 MoreLogin 提供的 webdriver: {webdriver_path2}")
                        try:
                            driver2 = webdriver.Chrome(service=Service(webdriver_path2), options=chrome_options2)
                        except Exception as e:
                            print(f"  ⚠️  使用提供的 webdriver 失败: {e}")
                            print(f"  尝试使用系统默认 webdriver...")
                            try:
                                driver2 = webdriver.Chrome(options=chrome_options2)
                            except Exception as e2:
                                error_msg = str(e2)
                                if "version" in error_msg.lower() or "chromedriver" in error_msg.lower():
                                    # 版本不匹配，建议使用远程调试端口
                                    print(f"\n❌ ChromeDriver 版本不匹配！")
                                    print(f"  错误: {error_msg}")
                                    print(f"\n💡 解决方案：使用远程调试端口方式")
                                    print(f"  1. 在 config.py 中配置：")
                                    print(f"     MORELOGIN_PORT2 = {debug_port2}")
                                    print(f"  2. 或者手动在 MoreLogin 中启用远程调试端口")
                                    raise Exception(f"ChromeDriver 版本不匹配。请使用远程调试端口方式（端口: {debug_port2}）")
                                raise
                    else:
                        print(f"  ⚠️  API 未返回 webdriver 路径，尝试使用系统默认 webdriver")
                        try:
                            driver2 = webdriver.Chrome(options=chrome_options2)
                        except Exception as e:
                            error_msg = str(e)
                            if "version" in error_msg.lower() or "chromedriver" in error_msg.lower():
                                # 版本不匹配，建议使用远程调试端口
                                print(f"\n❌ ChromeDriver 版本不匹配！")
                                print(f"  错误: {error_msg}")
                                print(f"\n💡 解决方案：使用远程调试端口方式")
                                print(f"  1. 在 config.py 中配置：")
                                print(f"     MORELOGIN_PORT2 = {debug_port2}")
                                print(f"  2. 或者手动在 MoreLogin 中启用远程调试端口")
                                raise Exception(f"ChromeDriver 版本不匹配。请使用远程调试端口方式（端口: {debug_port2}）")
                            raise
                    
                    print("✅ 浏览器2已成功连接到 MoreLogin 环境")
                    
                    # 导航到目标URL
                    print(f"正在导航到交易页面: {self.url}")
                    driver2.get(self.url)
                    time.sleep(3)
                    print("✅ 浏览器2已导航到交易页面")
                except Exception as e:
                    print(f"❌ API 启动环境2失败: {e}")
                    api_failed = True
            
            # 如果 API 成功，初始化 bot 并返回
            if not api_failed and driver1 and driver2:
                try:
                    from config import TP_VALUE, SL_VALUE, TRADING_PAIR, ORDER_QUANTITY
                    tp_val = TP_VALUE
                    sl_val = SL_VALUE
                    self.trading_pair = TRADING_PAIR
                    self.order_quantity = ORDER_QUANTITY
                except:
                    tp_val = '3'
                    sl_val = '3'
                    self.trading_pair = 'BTC'
                    self.order_quantity = '0.01'
                
                self.bot1 = HedgeBot(driver1, "浏览器1", is_long=True, tp_value=tp_val, sl_value=sl_val)
                self.bot2 = HedgeBot(driver2, "浏览器2", is_long=False, tp_value=tp_val, sl_value=sl_val)
                
                try:
                    from config import ORDER_INTERVAL, COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
                    self.order_interval = ORDER_INTERVAL
                    self.cooldown_after_close = COOLDOWN_AFTER_CLOSE
                    self.wait_before_force_close = WAIT_BEFORE_FORCE_CLOSE
                except:
                    pass
                
                print("两个浏览器已就绪！")
                return
        
        # ========== 方式2: 使用手动配置的远程调试端口 ==========
        # 如果 API 失败，或者没有配置 API，尝试使用远程调试端口
        if api_failed or (not (self.morelogin_api and (self.morelogin_env1 or self.morelogin_env2)) and (self.morelogin_port1 or self.morelogin_port2)):
            if api_failed:
                print("\n" + "="*60)
                print("⚠️ MoreLogin API 不可用，尝试使用远程调试端口方式...")
                print("="*60 + "\n")
            if self.morelogin_port1:
                print(f"连接到 MoreLogin 浏览器1（端口 {self.morelogin_port1}）...")
                chrome_options1.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.morelogin_port1}")
                driver1 = webdriver.Chrome(options=chrome_options1)
                print("浏览器1已连接到 MoreLogin 实例")
                # 导航到目标URL（如果当前不在目标页面）
                try:
                    current_url = driver1.current_url
                    if self.url not in current_url:
                        print(f"正在导航到交易页面: {self.url}")
                        driver1.get(self.url)
                        time.sleep(3)
                        print("✅ 浏览器1已导航到交易页面")
                    else:
                        print(f"✅ 浏览器1已在目标页面: {current_url}")
                except Exception as e:
                    print(f"⚠️  导航到目标页面时出错: {e}，尝试重新导航...")
                    driver1.get(self.url)
                    time.sleep(3)
            else:
                # 如果未配置端口，不启动标准 Chrome，而是报错
                raise Exception("未配置浏览器1的远程调试端口！\n"
                              "请在 config.py 中配置 MORELOGIN_PORT1，或使用 MoreLogin API 方式。")
            
            if self.morelogin_port2:
                print(f"连接到 MoreLogin 浏览器2（端口 {self.morelogin_port2}）...")
                chrome_options2.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.morelogin_port2}")
                driver2 = webdriver.Chrome(options=chrome_options2)
                print("浏览器2已连接到 MoreLogin 实例")
                # 导航到目标URL（如果当前不在目标页面）
                try:
                    current_url = driver2.current_url
                    if self.url not in current_url:
                        print(f"正在导航到交易页面: {self.url}")
                        driver2.get(self.url)
                        time.sleep(3)
                        print("✅ 浏览器2已导航到交易页面")
                    else:
                        print(f"✅ 浏览器2已在目标页面: {current_url}")
                except Exception as e:
                    print(f"⚠️  导航到目标页面时出错: {e}，尝试重新导航...")
                    driver2.get(self.url)
                    time.sleep(3)
            else:
                # 如果未配置端口，不启动标准 Chrome，而是报错
                raise Exception("未配置浏览器2的远程调试端口！\n"
                              "请在 config.py 中配置 MORELOGIN_PORT2，或使用 MoreLogin API 方式。")
            
            # 初始化 bot（方式2）
            if driver1 and driver2:
                try:
                    from config import TP_VALUE, SL_VALUE, TRADING_PAIR, ORDER_QUANTITY
                    tp_val = TP_VALUE
                    sl_val = SL_VALUE
                    self.trading_pair = TRADING_PAIR
                    self.order_quantity = ORDER_QUANTITY
                except:
                    tp_val = '3'
                    sl_val = '3'
                    self.trading_pair = 'BTC'
                    self.order_quantity = '0.01'
                
                self.bot1 = HedgeBot(driver1, "浏览器1", is_long=True, tp_value=tp_val, sl_value=sl_val)
                self.bot2 = HedgeBot(driver2, "浏览器2", is_long=False, tp_value=tp_val, sl_value=sl_val)
                
                try:
                    from config import ORDER_INTERVAL, COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
                    self.order_interval = ORDER_INTERVAL
                    self.cooldown_after_close = COOLDOWN_AFTER_CLOSE
                    self.wait_before_force_close = WAIT_BEFORE_FORCE_CLOSE
                except:
                    pass
                
                print("两个浏览器已就绪！")
                return
        
        # ========== 方式3: 使用浏览器路径 ==========
        if (api_failed or (not (self.morelogin_api and (self.morelogin_env1 or self.morelogin_env2)) and not (self.morelogin_port1 or self.morelogin_port2))) and (self.morelogin_path1 or self.morelogin_path2):
            # 尝试从 config 中读取 CHROMEDRIVER_PATH（可选）
            try:
                from config import CHROMEDRIVER_PATH
            except ImportError:
                CHROMEDRIVER_PATH = None
            except Exception:
                CHROMEDRIVER_PATH = None

            if self.morelogin_path1:
                print(f"使用 MoreLogin 浏览器1路径: {self.morelogin_path1}")
                chrome_options1.binary_location = self.morelogin_path1
                # 使用本地已安装的 ChromeDriver
                if CHROMEDRIVER_PATH:
                    driver1 = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options1)
                else:
                    # 未配置 CHROMEDRIVER_PATH 时，依赖系统 PATH 或默认搜索路径
                    driver1 = webdriver.Chrome(options=chrome_options1)
            else:
                # 如果未配置路径，不启动标准 Chrome，而是报错
                raise Exception("未配置浏览器1的 MoreLogin 路径！\n"
                              "请在 config.py 中配置 MORELOGIN_PATH1，或使用远程调试端口方式。")
            
            print("正在启动 MoreLogin 浏览器1...")
            driver1.get(self.url)
            time.sleep(3)
            
            if self.morelogin_path2:
                print(f"使用 MoreLogin 浏览器2路径: {self.morelogin_path2}")
                chrome_options2.binary_location = self.morelogin_path2
                # 使用本地已安装的 ChromeDriver
                if CHROMEDRIVER_PATH:
                    driver2 = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_options2)
                else:
                    # 未配置 CHROMEDRIVER_PATH 时，依赖系统 PATH 或默认搜索路径
                    driver2 = webdriver.Chrome(options=chrome_options2)
            else:
                # 如果未配置路径，不启动标准 Chrome，而是报错
                raise Exception("未配置浏览器2的 MoreLogin 路径！\n"
                              "请在 config.py 中配置 MORELOGIN_PATH2，或使用远程调试端口方式。")
            
            print("正在启动 MoreLogin 浏览器2...")
            driver2.get(self.url)
            time.sleep(3)
            
            # 初始化 bot（方式3）
            if driver1 and driver2:
                try:
                    from config import TP_VALUE, SL_VALUE, TRADING_PAIR, ORDER_QUANTITY
                    tp_val = TP_VALUE
                    sl_val = SL_VALUE
                    self.trading_pair = TRADING_PAIR
                    self.order_quantity = ORDER_QUANTITY
                except:
                    tp_val = '3'
                    sl_val = '3'
                    self.trading_pair = 'BTC'
                    self.order_quantity = '0.01'
                
                self.bot1 = HedgeBot(driver1, "浏览器1", is_long=True, tp_value=tp_val, sl_value=sl_val)
                self.bot2 = HedgeBot(driver2, "浏览器2", is_long=False, tp_value=tp_val, sl_value=sl_val)
                
                try:
                    from config import ORDER_INTERVAL, COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
                    self.order_interval = ORDER_INTERVAL
                    self.cooldown_after_close = COOLDOWN_AFTER_CLOSE
                    self.wait_before_force_close = WAIT_BEFORE_FORCE_CLOSE
                except:
                    pass
                
                print("两个浏览器已就绪！")
                return
        
        # ========== 检查是否成功初始化浏览器 ==========
        # 如果所有 MoreLogin 方式都失败，直接报错，不使用标准 Chrome
        if not driver1 or not driver2:
            error_msg = "❌ 无法连接到 MoreLogin 浏览器！\n\n"
            error_msg += "请使用以下方式之一配置 MoreLogin：\n\n"
            
            # 检查是否尝试了 API 方式
            tried_api = self.morelogin_api and (self.morelogin_env1 or self.morelogin_env2)
            if tried_api:
                if api_failed:
                    error_msg += "方式1（API）失败，请尝试方式2：\n\n"
                else:
                    error_msg += "方式1（API）未成功启动，可能的原因：\n"
                    error_msg += "  1. MoreLogin 客户端未启动或未登录\n"
                    error_msg += "  2. API 服务未运行（检查端口 40000）\n"
                    error_msg += "  3. 环境ID 或环境序号不正确\n"
                    error_msg += "  4. API ID 或 API Key 不正确\n\n"
                    error_msg += "请尝试方式2（推荐）：\n\n"
            elif self.morelogin_api is not None:
                error_msg += "⚠️  已配置 MoreLogin API，但未配置环境ID！\n"
                error_msg += "  请在 config.py 中配置 MORELOGIN_ENV1 和 MORELOGIN_ENV2\n"
                error_msg += "  环境ID 可以在 MoreLogin 客户端中查看\n\n"
                error_msg += "或者使用方式2（推荐）：\n\n"
            
            error_msg += "方式2（推荐）：使用远程调试端口 ⭐⭐⭐\n"
            error_msg += "  1. 在 MoreLogin 中手动打开两个浏览器窗口\n"
            error_msg += "  2. 导航到交易页面: https://omni.variational.io/perpetual/BTC\n"
            error_msg += "  3. 在 MoreLogin 中，右键浏览器 -> 设置 -> 启用远程调试\n"
            error_msg += "  4. 记录下端口号（例如: 9222, 9223）\n"
            error_msg += "  5. 在 config.py 中配置：\n"
            error_msg += "     MORELOGIN_PORT1 = 9222  # 浏览器1的端口\n"
            error_msg += "     MORELOGIN_PORT2 = 9223  # 浏览器2的端口\n\n"
            
            error_msg += "方式3：使用浏览器路径\n"
            error_msg += "  在 config.py 中配置 MORELOGIN_PATH1 和 MORELOGIN_PATH2\n"
            
            raise Exception(error_msg)
        
        # 从配置读取 TP/SL 值和其他参数
        try:
            from config import TP_VALUE, SL_VALUE, TRADING_PAIR, ORDER_QUANTITY
            tp_val = TP_VALUE
            sl_val = SL_VALUE
            self.trading_pair = TRADING_PAIR
            self.order_quantity = ORDER_QUANTITY
        except:
            tp_val = '3'
            sl_val = '3'
            self.trading_pair = 'BTC'
            self.order_quantity = '0.01'
        
        self.bot1 = HedgeBot(driver1, "浏览器1", is_long=True, tp_value=tp_val, sl_value=sl_val)
        self.bot2 = HedgeBot(driver2, "浏览器2", is_long=False, tp_value=tp_val, sl_value=sl_val)
        
        # 从配置读取其他参数
        try:
            from config import ORDER_INTERVAL, COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
            self.order_interval = ORDER_INTERVAL
            self.cooldown_after_close = COOLDOWN_AFTER_CLOSE
            self.wait_before_force_close = WAIT_BEFORE_FORCE_CLOSE
        except:
            pass
        
        print("两个浏览器已就绪！")
    
    def wait_for_start_time(self):
        """等待启动时间"""
        if not self.start_time:
            return
        
        now = datetime.now()
        target = datetime.strptime(f"{datetime.now().strftime('%Y-%m-%d')} {self.start_time}", "%Y-%m-%d %H:%M:%S")
        if target < now:
            target += timedelta(days=1)
        
        diff = (target - now).total_seconds()
        if diff > 0:
            print(f"等待启动时间 {self.start_time}，还有 {int(diff)} 秒...")
            time.sleep(diff)
        print("启动时间到，开始运行！")
    
    def sync_place_orders(self):
        """同步下单：两个浏览器在同一时间点下单"""
        # 计算下一个整点时间（根据配置的间隔）
        now = datetime.now()
        current_seconds = now.second
        interval = self.order_interval
        next_target_seconds = ((current_seconds // interval) + 1) * interval
        if next_target_seconds >= 60:
            next_target_seconds = 0
            target_time = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        else:
            target_time = now.replace(second=next_target_seconds, microsecond=0)
        
        delay = (target_time - now).total_seconds()
        if delay < 1:
            delay += 10
        
        print(f"等待 {delay:.1f} 秒后同步下单... ({target_time.strftime('%H:%M:%S')})")
        time.sleep(delay)
        
        # 同时下单
        print("🚀 同步下单！")
        result1 = [None]  # 使用列表以便在线程中修改
        result2 = [None]
        error1 = [None]
        error2 = [None]
        
        def place_order_bot1():
            try:
                result1[0] = self.bot1.place_order()
            except Exception as e:
                error1[0] = str(e)
                result1[0] = False
        
        def place_order_bot2():
            try:
                result2[0] = self.bot2.place_order()
            except Exception as e:
                error2[0] = str(e)
                result2[0] = False
        
        thread1 = threading.Thread(target=place_order_bot1)
        thread2 = threading.Thread(target=place_order_bot2)
        
        # 同时启动线程，确保真正的同步
        thread1.start()
        thread2.start()
        
        # 等待两个线程都完成，但设置超时（最多等待5秒）
        thread1.join(timeout=5)
        thread2.join(timeout=5)
        
        # 如果线程还在运行，说明可能卡住了
        if thread1.is_alive() or thread2.is_alive():
            print("⚠️ 下单操作超时，可能某个浏览器响应缓慢")
        
        # 如果结果还是None，说明可能出错了
        if result1[0] is None:
            result1[0] = False
        if result2[0] is None:
            result2[0] = False
        
        # 统一打印消息
        if result1[0] and result2[0]:
            print(f"✅ [浏览器1] 和 [浏览器2] 已点击下单按钮")
        elif result1[0]:
            error_msg2 = f" ({error2[0]})" if error2[0] else ""
            print(f"✅ [浏览器1] 已点击下单按钮，❌ [浏览器2] 下单失败{error_msg2}")
        elif result2[0]:
            error_msg1 = f" ({error1[0]})" if error1[0] else ""
            print(f"❌ [浏览器1] 下单失败{error_msg1}，✅ [浏览器2] 已点击下单按钮")
        else:
            error_msg1 = f" ({error1[0]})" if error1[0] else ""
            error_msg2 = f" ({error2[0]})" if error2[0] else ""
            print(f"❌ [浏览器1] 和 [浏览器2] 下单都失败{error_msg1} / {error_msg2}")
        
        return result1[0], result2[0]
    
    def run_cycle(self):
        """运行一个完整周期"""
        # 1. 检查两个浏览器的持仓状态
        pos1 = self.bot1.has_position_now()
        pos2 = self.bot2.has_position_now()
        
        # 2. 如果两个都有持仓，检查是否需要补设TP/SL（同时进行）
        if pos1 and pos2:
            if not self.bot1.has_position or not self.bot2.has_position:
                print("✅ 检测到新持仓，同时为两个浏览器设置TP/SL...")
                # 使用线程同时执行
                import threading
                
                result1 = [None]
                result2 = [None]
                
                def set_tp_sl_bot1():
                    if not self.bot1.has_position:
                        result1[0] = self.bot1.check_and_fix_tp_sl()
                
                def set_tp_sl_bot2():
                    if not self.bot2.has_position:
                        result2[0] = self.bot2.check_and_fix_tp_sl()
                
                # 创建线程
                thread1 = threading.Thread(target=set_tp_sl_bot1)
                thread2 = threading.Thread(target=set_tp_sl_bot2)
                
                # 同时启动
                thread1.start()
                thread2.start()
                
                # 等待完成
                thread1.join()
                thread2.join()
                
                # 统一打印结果
                r1 = result1[0]
                r2 = result2[0]
                
                if r1 and r1.get('success'):
                    if r2 and r2.get('success'):
                        # 两个都成功
                        print(f"✅ 浏览器1，2已点击创建 TP/SL 按钮")
                        print(f"✅ 浏览器1，2找到 {r1.get('input_count', 0)} 个弹窗输入框，已填写 {r1.get('filled_count', 0)} 个: {r1.get('tp_value', '')}%")
                        print(f"✅ 浏览器1，2已点击确认按钮")
                        print(f"✅ 浏览器1，2 TP/SL 设置完成")
                    else:
                        # 只有浏览器1成功
                        print(f"✅ 浏览器1已点击创建 TP/SL 按钮，❌ 浏览器2{'已设置' if r2 and r2.get('already_set') else '设置失败'}")
                        if r1.get('input_count', 0) > 0:
                            print(f"✅ 浏览器1找到 {r1.get('input_count', 0)} 个弹窗输入框，已填写 {r1.get('filled_count', 0)} 个: {r1.get('tp_value', '')}%")
                            print(f"✅ 浏览器1已点击确认按钮")
                        print(f"✅ 浏览器1 TP/SL 设置完成")
                elif r2 and r2.get('success'):
                    # 只有浏览器2成功
                    print(f"❌ 浏览器1{'已设置' if r1 and r1.get('already_set') else '设置失败'}，✅ 浏览器2已点击创建 TP/SL 按钮")
                    if r2.get('input_count', 0) > 0:
                        print(f"✅ 浏览器2找到 {r2.get('input_count', 0)} 个弹窗输入框，已填写 {r2.get('filled_count', 0)} 个: {r2.get('tp_value', '')}%")
                        print(f"✅ 浏览器2已点击确认按钮")
                    print(f"✅ 浏览器2 TP/SL 设置完成")
                else:
                    # 两个都失败或已设置
                    if r1 and r1.get('already_set') and r2 and r2.get('already_set'):
                        print("✅ 浏览器1，2 TP/SL 已设置，无需重复设置")
                    elif r1 and r1.get('already_set'):
                        print(f"✅ 浏览器1 TP/SL 已设置，❌ 浏览器2设置失败: {r2.get('error', '未知错误') if r2 else '未知错误'}")
                    elif r2 and r2.get('already_set'):
                        print(f"❌ 浏览器1设置失败: {r1.get('error', '未知错误') if r1 else '未知错误'}，✅ 浏览器2 TP/SL 已设置")
                    else:
                        error1 = r1.get('error', '未知错误') if r1 else '未知错误'
                        error2 = r2.get('error', '未知错误') if r2 else '未知错误'
                        print(f"❌ 浏览器1，2 TP/SL 设置失败: {error1} / {error2}")
        
        # 3. 检测持仓状态变化：从有持仓变成没持仓
        if self.bot1.has_position and not pos1:
            print("[浏览器1] ✅ 持仓已平仓（止损/止盈触发）！")
            # 如果浏览器2还有持仓，立即平掉它（不等待）
            if pos2:
                print("[浏览器2] ⚡ 检测到浏览器1已平仓，立即平掉浏览器2的持仓...")
                # 不等待，立即平仓（加快速度）
                if self.bot2.has_position_now():
                    print("[浏览器2] 正在主动平仓...")
                    success = self.bot2.close_position()
                    if success:
                        print("[浏览器2] ✅ 平仓成功")
                    else:
                        print("[浏览器2] ⚠️  平仓失败，将在下次循环重试")
                else:
                    print("[浏览器2] 持仓已自动平仓")
            # 记录平仓时间，用于冷却
            self.bot1.last_position_check = datetime.now()
        
        if self.bot2.has_position and not pos2:
            print("[浏览器2] ✅ 持仓已平仓（止损/止盈触发）！")
            # 如果浏览器1还有持仓，立即平掉它（不等待）
            if pos1:
                print("[浏览器1] ⚡ 检测到浏览器2已平仓，立即平掉浏览器1的持仓...")
                # 不等待，立即平仓（加快速度）
                if self.bot1.has_position_now():
                    print("[浏览器1] 正在主动平仓...")
                    success = self.bot1.close_position()
                    if success:
                        print("[浏览器1] ✅ 平仓成功")
                    else:
                        print("[浏览器1] ⚠️  平仓失败，将在下次循环重试")
                else:
                    print("[浏览器1] 持仓已自动平仓")
            # 记录平仓时间，用于冷却
            self.bot2.last_position_check = datetime.now()
        
        # 4. 更新状态
        self.bot1.has_position = pos1
        self.bot2.has_position = pos2
        
        # 5. 如果两个都没有持仓，准备开新单
        if not pos1 and not pos2:
            # 如果正在开新单，跳过本次循环，避免重复下单
            if self._opening_order:
                return
            
            # 标记正在开新单，避免重复执行
            self._opening_order = True
            
            # 记录进入"空仓状态"这一刻的时间，用来计算冷却时间基准，避免统计PnL时的等待占用冷却时间
            empty_state_time = datetime.now()

            # 只有在本轮"确实发生过平仓"（last_position_check 非空）时，才统计一次PnL
            if (self.bot1.last_position_check or self.bot2.last_position_check) and not self.pnl_reported:
                print("本轮持仓已全部平仓，统计已实现PnL（最多等待15秒，不影响冷却时间）...")
                pnl1 = None
                pnl2 = None
                try:
                    pnl1 = self.bot1.report_realized_pnl()
                except Exception as e:
                    print(f"[浏览器1] 统计PnL时出错: {e}")
                try:
                    pnl2 = self.bot2.report_realized_pnl()
                except Exception as e:
                    print(f"[浏览器2] 统计PnL时出错: {e}")
                
                # 合并打印PnL信息并计算总和
                pnl_message = ""
                round_pnl = None  # 本轮盈亏总和
                round_pnl_display = ""
                
                if pnl1 and pnl2:
                    currency1 = pnl1['currency']
                    currency2 = pnl2['currency']
                    currency = currency1 if currency1 == currency2 else f"{currency1}/{currency2}"
                    unit1 = 'u' if currency1.upper() == 'USDC' else currency1
                    unit2 = 'u' if currency2.upper() == 'USDC' else currency2
                    pnl_message = f"浏览器1，2已实现盈亏：{pnl1['amount_display']}{unit1} 和 {pnl2['amount_display']}{unit2}"
                    
                    # 计算本轮盈亏总和（如果都是USDC）
                    if currency1.upper() == 'USDC' and currency2.upper() == 'USDC':
                        try:
                            amount1 = pnl1.get('amount_value')
                            amount2 = pnl2.get('amount_value')
                            if amount1 is not None and amount2 is not None:
                                round_pnl = amount1 + amount2
                                round_pnl_display = f"{round_pnl:+.4f}u"
                                # 累计到总盈亏
                                self.total_pnl += round_pnl
                        except:
                            pass
                    
                    print(pnl_message)
                    if round_pnl_display:
                        print(f"本轮盈亏总和：{round_pnl_display}，累计总盈亏：{self.total_pnl:+.4f}u")
                elif pnl1:
                    currency1 = pnl1['currency']
                    unit1 = 'u' if currency1.upper() == 'USDC' else currency1
                    pnl_message = f"浏览器1已实现盈亏：{pnl1['amount_display']}{unit1}，浏览器2未能获取"
                    print(pnl_message)
                    # 如果只有浏览器1的数据，也尝试累计
                    if currency1.upper() == 'USDC':
                        try:
                            amount1 = pnl1.get('amount_value')
                            if amount1 is not None:
                                round_pnl = amount1
                                round_pnl_display = f"{round_pnl:+.4f}u"
                                self.total_pnl += round_pnl
                                print(f"本轮盈亏总和：{round_pnl_display}，累计总盈亏：{self.total_pnl:+.4f}u")
                        except:
                            pass
                elif pnl2:
                    currency2 = pnl2['currency']
                    unit2 = 'u' if currency2.upper() == 'USDC' else currency2
                    pnl_message = f"浏览器1未能获取，浏览器2已实现盈亏：{pnl2['amount_display']}{unit2}"
                    print(pnl_message)
                    # 如果只有浏览器2的数据，也尝试累计
                    if currency2.upper() == 'USDC':
                        try:
                            amount2 = pnl2.get('amount_value')
                            if amount2 is not None:
                                round_pnl = amount2
                                round_pnl_display = f"{round_pnl:+.4f}u"
                                self.total_pnl += round_pnl
                                print(f"本轮盈亏总和：{round_pnl_display}，累计总盈亏：{self.total_pnl:+.4f}u")
                        except:
                            pass
                
                # 推送到Telegram
                if pnl_message and self.tg_notifier:
                    self.push_count += 1
                    # 构建TG消息
                    tg_message = f"<b>第 {self.push_count} 轮平仓</b>\n\n{pnl_message}"
                    if round_pnl_display:
                        tg_message += f"\n\n<b>本轮盈亏：{round_pnl_display}</b>"
                        tg_message += f"\n<b>累计总盈亏：{self.total_pnl:+.4f}u</b>"
                    else:
                        tg_message += f"\n\n<i>（无法计算盈亏总和，可能币种不一致）</i>"
                    
                    if self.tg_notifier.send_message(tg_message):
                        print(f"✅ 已推送到Telegram（第 {self.push_count} 轮）")
                    else:
                        print(f"⚠️ TG推送失败（第 {self.push_count} 轮）")
                
                self.pnl_reported = True

            # 检查是否刚平仓（需要等待冷却）
            cooldown_time = self.cooldown_after_close
            need_cooldown = False
            if self.bot1.last_position_check:
                elapsed = (empty_state_time - self.bot1.last_position_check).total_seconds()
                if elapsed < cooldown_time:
                    need_cooldown = True
                    wait_time = cooldown_time - elapsed
                    print(f"等待 {int(wait_time)} 秒冷却后再开新单...")
                    time.sleep(wait_time)
            
            if self.bot2.last_position_check and not need_cooldown:
                elapsed = (empty_state_time - self.bot2.last_position_check).total_seconds()
                if elapsed < cooldown_time:
                    wait_time = cooldown_time - elapsed
                    print(f"等待 {int(wait_time)} 秒冷却后再开新单...")
                    time.sleep(wait_time)
            
            print("准备开新单...")
            
            # 从配置读取币种和数量
            try:
                from config import TRADING_PAIR, ORDER_QUANTITY
                trading_pair = TRADING_PAIR
                order_quantity = ORDER_QUANTITY
            except:
                trading_pair = 'BTC'
                order_quantity = '0.01'
            
            # 1. 选择币种（只在第一次选择）
            if not self.trading_pair_selected:
                print(f"首次选择交易币种: {trading_pair}")
                self.bot1.select_trading_pair(trading_pair)
                self.bot2.select_trading_pair(trading_pair)
                time.sleep(0.5)
                self.trading_pair_selected = True
                print("✅ 币种已选择，后续循环将跳过币种选择")
            else:
                print(f"币种已选择 ({trading_pair})，跳过币种选择步骤")
            
            # 2. 随机分配开仓方向（确保对冲）
            import random
            # 随机决定哪个浏览器开多，哪个开空
            bot1_is_long = random.choice([True, False])
            bot2_is_long = not bot1_is_long  # 确保方向相反
            
            direction_text = "开多" if bot1_is_long else "开空"
            print(f"随机分配方向：浏览器1 {direction_text}，浏览器2 {'开多' if bot2_is_long else '开空'}")
            
            self.bot1.select_order_direction(is_long=bot1_is_long)
            self.bot2.select_order_direction(is_long=bot2_is_long)
            time.sleep(0.5)
            
            # 3. 检查对冲状态
            print("检查对冲状态...")
            dir1 = self.bot1.check_order_direction()
            dir2 = self.bot2.check_order_direction()
            
            if (dir1 == 'long' and dir2 == 'short') or (dir1 == 'short' and dir2 == 'long'):
                print(f"✅ 对冲检查通过：浏览器1{'开多' if dir1 == 'long' else '开空'}，浏览器2{'开多' if dir2 == 'long' else '开空'}")
            else:
                print(f"⚠️ 无法确认方向：浏览器1={dir1}, 浏览器2={dir2}")
                print("继续执行，但请手动确认方向是否正确")
            
            # 4. 填写数量
            print(f"填写开仓数量: {order_quantity}")
            result1 = self.bot1.fill_quantity(order_quantity)
            result2 = self.bot2.fill_quantity(order_quantity)
            if result1 and result2:
                print(f"✅ [浏览器1] 和 [浏览器2] 已填写开仓数量: {order_quantity}")
            elif result1:
                print(f"✅ [浏览器1] 已填写开仓数量: {order_quantity}，❌ [浏览器2] 填写失败")
            elif result2:
                print(f"❌ [浏览器1] 填写失败，✅ [浏览器2] 已填写开仓数量: {order_quantity}")
            else:
                print(f"❌ [浏览器1] 和 [浏览器2] 填写数量都失败")
            time.sleep(0.5)
            
            # 检查余额是否不足（在下单前检查）
            insufficient1, msg1 = self.bot1.check_insufficient_balance()
            insufficient2, msg2 = self.bot2.check_insufficient_balance()
            
            if insufficient1 or insufficient2:
                error_msg = "❌ 检测到余额不足，无法开仓：\n"
                if insufficient1:
                    error_msg += f"   [浏览器1] {msg1 if msg1 else '余额不足（按钮已禁用）'}\n"
                if insufficient2:
                    error_msg += f"   [浏览器2] {msg2 if msg2 else '余额不足（按钮已禁用）'}\n"
                error_msg += "💡 请检查账户余额，确保有足够的资金开仓"
                print(error_msg)
                # 如果已经有持仓，平掉以避免单边风险
                if self.bot1.has_position_now():
                    print("正在平掉浏览器1的持仓以避免单边风险...")
                    self.bot1.close_position()
                    time.sleep(2)
                if self.bot2.has_position_now():
                    print("正在平掉浏览器2的持仓以避免单边风险...")
                    self.bot2.close_position()
                    time.sleep(2)
                # 重置状态，等待下次循环
                self.bot1.has_position = False
                self.bot2.has_position = False
                self._opening_order = False  # 重置开新单标志
                return  # 退出本次循环，等待下次
            
            # 5. 填写TP/SL
            print("填写止盈止损...")
            self.bot1.fill_tp_sl()
            self.bot2.fill_tp_sl()
            time.sleep(1)
            
            # 5.5. 填写TP/SL后，再次检查余额（因为填写TP/SL可能会影响按钮状态）
            insufficient1, msg1 = self.bot1.check_insufficient_balance()
            insufficient2, msg2 = self.bot2.check_insufficient_balance()
            
            if insufficient1 or insufficient2:
                error_msg = "❌ 检测到余额不足，无法开仓：\n"
                if insufficient1:
                    error_msg += f"   [浏览器1] {msg1 if msg1 else '余额不足（按钮已禁用）'}\n"
                if insufficient2:
                    error_msg += f"   [浏览器2] {msg2 if msg2 else '余额不足（按钮已禁用）'}\n"
                error_msg += "💡 请检查账户余额，确保有足够的资金开仓"
                print(error_msg)
                # 如果已经有持仓，平掉以避免单边风险
                if self.bot1.has_position_now():
                    print("正在平掉浏览器1的持仓以避免单边风险...")
                    self.bot1.close_position()
                    time.sleep(2)
                if self.bot2.has_position_now():
                    print("正在平掉浏览器2的持仓以避免单边风险...")
                    self.bot2.close_position()
                    time.sleep(2)
                # 重置状态，等待下次循环
                self.bot1.has_position = False
                self.bot2.has_position = False
                self._opening_order = False  # 重置开新单标志
                return  # 退出本次循环，等待下次
            
            # 6. 同步下单前，最后确认按钮状态
            print("下单前最后确认按钮状态...")
            insufficient1_final, msg1_final = self.bot1.check_insufficient_balance()
            insufficient2_final, msg2_final = self.bot2.check_insufficient_balance()
            
            if insufficient1_final or insufficient2_final:
                error_msg = "❌ 下单前最后检查：检测到余额不足，取消下单：\n"
                if insufficient1_final:
                    error_msg += f"   [浏览器1] {msg1_final if msg1_final else '余额不足（按钮已禁用）'}\n"
                if insufficient2_final:
                    error_msg += f"   [浏览器2] {msg2_final if msg2_final else '余额不足（按钮已禁用）'}\n"
                error_msg += "💡 请检查账户余额，确保有足够的资金开仓"
                print(error_msg)
                # 如果已经有持仓，平掉以避免单边风险
                if self.bot1.has_position_now():
                    print("正在平掉浏览器1的持仓以避免单边风险...")
                    self.bot1.close_position()
                    time.sleep(2)
                if self.bot2.has_position_now():
                    print("正在平掉浏览器2的持仓以避免单边风险...")
                    self.bot2.close_position()
                    time.sleep(2)
                # 重置状态，等待下次循环
                self.bot1.has_position = False
                self.bot2.has_position = False
                self._opening_order = False  # 重置开新单标志
                return  # 退出本次循环，等待下次
            
            # 6. 同步下单
            order_result1, order_result2 = self.sync_place_orders()
            
            # 等待持仓出现
            print("等待持仓确认...")
            max_wait = 20  # 最多等10秒
            both_success = False
            for i in range(max_wait):
                pos1 = self.bot1.has_position_now()
                pos2 = self.bot2.has_position_now()
                
                if pos1 and pos2:
                    print("✅ 两个浏览器都已开仓成功！")
                    # 重置平仓时间标记和PnL统计标记
                    self.bot1.last_position_check = None
                    self.bot2.last_position_check = None
                    self.pnl_reported = False
                    self._opening_order = False  # 重置开新单标志
                    both_success = True
                    break
                
                time.sleep(0.5)
            
            # 如果等待超时，不进行任何操作，让下一个循环自然处理
            if not both_success:
                pos1 = self.bot1.has_position_now()
                pos2 = self.bot2.has_position_now()
                if pos1 or pos2:
                    print("⚠️ 等待超时：持仓确认未完成，将在下次循环中继续检查")
                else:
                    print("⚠️ 等待超时：两个浏览器都没有持仓，将在下次循环中继续检查")
            
            # 无论成功与否，都要重置开新单标志
            self._opening_order = False
    
    def run(self):
        """主循环"""
        self.init_drivers()
        self.wait_for_start_time()
        
        self.running = True
        print("开始监控循环...")
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(1)  # 每1秒检查一次，提高响应速度
        except KeyboardInterrupt:
            print("\n收到停止信号，正在关闭...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        if self.keep_browsers_open:
            print("检测到 KEEP_BROWSERS_OPEN=True，本次退出不关闭浏览器窗口，也不通过 API 关闭 MoreLogin 环境。")
            print("如果需要，请在 MoreLogin 客户端中手动关闭环境或浏览器。")
            return

        print("正在关闭浏览器...")
        
        # 如果使用 MoreLogin API，先通过 API 关闭环境
        if self.morelogin_api:
            if self.morelogin_env_data1:
                try:
                    env_id1 = self.morelogin_env_data1.get("envId")
                    if env_id1:
                        self.morelogin_api.close_env(env_id=env_id1)
                        print("已通过 API 关闭环境1")
                except Exception as e:
                    print(f"关闭环境1失败: {e}")
            
            if self.morelogin_env_data2:
                try:
                    env_id2 = self.morelogin_env_data2.get("envId")
                    if env_id2:
                        self.morelogin_api.close_env(env_id=env_id2)
                        print("已通过 API 关闭环境2")
                except Exception as e:
                    print(f"关闭环境2失败: {e}")
        
        # 关闭 Selenium 驱动
        if self.bot1 and self.bot1.driver:
            try:
                self.bot1.driver.quit()
            except:
                pass
        if self.bot2 and self.bot2.driver:
            try:
                self.bot2.driver.quit()
            except:
                pass
        
        print("已关闭所有浏览器")


if __name__ == "__main__":
    # ========== 从配置文件读取参数 ==========
    try:
        from config import (
            URL, START_TIME,
            MORELOGIN_ENV1, MORELOGIN_ENV2, MORELOGIN_API_URL,
            MORELOGIN_API_ID, MORELOGIN_API_KEY,
            MORELOGIN_PORT1, MORELOGIN_PORT2,
            MORELOGIN_PATH1, MORELOGIN_PATH2,
            TRADING_PAIR, ORDER_QUANTITY,
            TP_VALUE, SL_VALUE, ORDER_INTERVAL,
            COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE,
            KEEP_BROWSERS_OPEN, TG_BOT_TOKEN, TG_CHAT_ID
        )
        print("✅ 已从 config.py 加载配置")
        print(f"   交易币种: {TRADING_PAIR}, 开仓数量: {ORDER_QUANTITY}")
        print(f"   止盈止损: {TP_VALUE}% / {SL_VALUE}%")
        if MORELOGIN_ENV1 or MORELOGIN_ENV2:
            if not MORELOGIN_API_ID or not MORELOGIN_API_KEY:
                print("⚠️  警告: 使用 MoreLogin API 需要配置 MORELOGIN_API_ID 和 MORELOGIN_API_KEY")
                print("   请在 MoreLogin 客户端中：设置 -> API -> 查看 API ID 和 API Key")
        elif MORELOGIN_API_ID and MORELOGIN_API_KEY:
            print("⚠️  提示: 已配置 MoreLogin API 认证信息，但未配置环境ID")
            print("   请在 config.py 中配置 MORELOGIN_ENV1 和 MORELOGIN_ENV2")
            print("   环境ID 可以在 MoreLogin 客户端中查看（通常是长数字字符串）")
            print("   或者使用环境序号（整数，如 1, 2, 3...）")
    except ImportError:
        print("❌ 错误: 找不到 config.py 配置文件！")
        print("请确保 config.py 文件存在于当前目录。")
        exit(1)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        exit(1)
    
    # ========== 启动脚本 ==========
    # 检查TG配置
    if TG_BOT_TOKEN and TG_CHAT_ID:
        print(f"✅ 已配置Telegram推送 (Bot Token: {TG_BOT_TOKEN[:10]}..., Chat ID: {TG_CHAT_ID})")
    else:
        print("ℹ️  未配置Telegram推送（可选，在config.py中配置TG_BOT_TOKEN和TG_CHAT_ID）")
    
    bot = DualBrowserHedgeBot(
        URL, 
        START_TIME,
        morelogin_port1=MORELOGIN_PORT1,
        morelogin_port2=MORELOGIN_PORT2,
        morelogin_path1=MORELOGIN_PATH1,
        morelogin_path2=MORELOGIN_PATH2,
        morelogin_env1=MORELOGIN_ENV1,
        morelogin_env2=MORELOGIN_ENV2,
        morelogin_api_url=MORELOGIN_API_URL,
        morelogin_api_id=MORELOGIN_API_ID,
        morelogin_api_key=MORELOGIN_API_KEY,
        keep_browsers_open=KEEP_BROWSERS_OPEN,
        tg_bot_token=TG_BOT_TOKEN,
        tg_chat_id=TG_CHAT_ID
    )
    bot.run()

