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
from datetime import datetime, timedelta
import time
import threading
import requests
import json

# 可选：自动管理 ChromeDriver（需要先安装: pip install webdriver-manager）
try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_AUTO_DRIVER = True
except ImportError:
    USE_AUTO_DRIVER = False
    print("提示: 安装 webdriver-manager 可自动管理 ChromeDriver: pip install webdriver-manager")

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
        """选择交易币种"""
        try:
            # 首先检查是否已经有弹窗打开（币种选择弹窗）
            modal_open = False
            try:
                # 查找"Select an Asset"或类似的弹窗标题
                modal_titles = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select an Asset') or contains(text(), '选择资产') or contains(text(), '选择币种')]")
                if modal_titles:
                    modal_open = True
                    print(f"[{self.name}] 检测到币种选择弹窗已打开")
            except:
                pass
            
            # 如果弹窗已打开，直接在弹窗中选择
            if modal_open:
                print(f"[{self.name}] 在弹窗中查找并选择 {pair}...")
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
                                print(f"[{self.name}] 已在弹窗中选择 {pair}")
                                time.sleep(0.5)
                                
                                # 等待弹窗关闭
                                time.sleep(0.5)
                                return True
                        except:
                            continue
                except Exception as e:
                    print(f"[{self.name}] 在弹窗中选择失败: {e}")
            
            # 如果弹窗未打开，尝试点击币种选择按钮打开弹窗
            if not modal_open:
                print(f"[{self.name}] 尝试打开币种选择弹窗...")
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
                    print(f"[{self.name}] 已点击币种选择按钮，等待弹窗打开...")
                    time.sleep(1)  # 等待弹窗打开
                    modal_open = True
                else:
                    print(f"[{self.name}] 未找到币种选择按钮")
                    return False
            
            # 在弹窗中选择币种
            if modal_open:
                print(f"[{self.name}] 在弹窗中查找 {pair}...")
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
                                print(f"[{self.name}] 已在弹窗中选择 {pair} (通过行点击)")
                                time.sleep(0.5)
                                return True
                        except:
                            continue
                except Exception as e:
                    print(f"[{self.name}] 通过行选择失败: {e}")
                
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
                                print(f"[{self.name}] 已在弹窗中选择 {pair} (通过元素点击)")
                                time.sleep(0.5)
                                return True
                        except:
                            continue
                except Exception as e:
                    print(f"[{self.name}] 通过元素选择失败: {e}")
                
                print(f"[{self.name}] 在弹窗中未找到 {pair}，可能已选择或需要手动选择")
                return False
            
            return False
        except Exception as e:
            print(f"[{self.name}] 选择币种失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
        """填写开仓数量"""
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
                print(f"[{self.name}] 已填写开仓数量: {quantity}")
                time.sleep(0.3)
                return True
            else:
                print(f"[{self.name}] 未找到数量输入框")
                return False
        except Exception as e:
            print(f"[{self.name}] 填写数量失败: {e}")
            return False
    
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
        """下单"""
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="submit-button"]')
            if btn and btn.is_displayed():
                btn.click()
                print(f"[{self.name}] 已点击下单按钮")
                return True
        except Exception as e:
            print(f"[{self.name}] 下单失败: {e}")
        return False
    
    def close_position(self):
        """主动平仓"""
        try:
            print(f"[{self.name}] 开始平仓流程...")
            row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
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
                # 滚动到按钮可见
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                time.sleep(0.3)
                
                # 点击关闭按钮
                try:
                    close_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", close_btn)
                
                print(f"[{self.name}] 已点击关闭按钮，等待平仓弹窗...")
                time.sleep(1.5)  # 等待弹窗出现
                
                # 查找平仓确认按钮（使用 data-testid="close-position-button"）
                try:
                    confirm_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="close-position-button"]')
                    if confirm_btn and confirm_btn.is_displayed():
                        print(f"[{self.name}] 找到平仓确认按钮: {confirm_btn.text}")
                        # 滚动到按钮可见
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_btn)
                        time.sleep(0.3)
                        
                        # 点击确认按钮
                        try:
                            confirm_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", confirm_btn)
                        
                        print(f"[{self.name}] ✅ 已点击平仓确认按钮")
                        time.sleep(2)  # 等待平仓完成
                        
                        # 检查弹窗是否关闭
                        try:
                            # 如果弹窗还在，尝试关闭
                            close_modal_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="close-button"]')
                            if close_modal_btn and close_modal_btn.is_displayed():
                                close_modal_btn.click()
                                time.sleep(0.5)
                        except:
                            pass
                        
                        return True
                    else:
                        print(f"[{self.name}] ⚠️  平仓确认按钮不可见")
                except Exception as e:
                    # 可能已经平仓了，检查是否还有持仓
                    print(f"[{self.name}] ⚠️  未找到平仓确认按钮: {e}")
                    try:
                        # 检查是否还有持仓行
                        row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
                        # 如果还能找到持仓行，说明还没平仓，尝试备用方法
                        print(f"[{self.name}] 持仓行仍存在，尝试备用方法...")
                        all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                        for btn in all_buttons:
                            if btn.is_displayed():
                                btn_text = btn.text
                                if '平仓' in btn_text or 'Close' in btn_text:
                                    print(f"[{self.name}] 找到备用平仓按钮: {btn_text}")
                                    try:
                                        btn.click()
                                        time.sleep(2)
                                        return True
                                    except:
                                        pass
                    except:
                        # 找不到持仓行，说明可能已经平仓了
                        print(f"[{self.name}] ✅ 持仓行已消失，可能已经平仓")
                        return True  # 返回True表示平仓成功（因为已经没有持仓了）
            else:
                print(f"[{self.name}] ⚠️  未找到关闭按钮")
        except Exception as e:
            print(f"[{self.name}] ❌ 平仓失败: {e}")
        return False
    
    def check_and_fix_tp_sl(self):
        """检查并补设TP/SL"""
        try:
            row = self.driver.find_element(By.CSS_SELECTOR, 'div[data-testid="positions-table-row"]')
            row_text = row.text
            
            # 如果已经有 (2) 订单，说明已设置
            if '(2)' in row_text:
                return False
            
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
                print(f"[{self.name}] 找到创建 TP/SL 按钮，准备点击...")
                # 滚动到按钮可见
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_btn)
                time.sleep(0.3)
                
                # 尝试多种点击方式
                try:
                    add_btn.click()
                except:
                    # 如果普通点击失败，使用JavaScript点击
                    self.driver.execute_script("arguments[0].click();", add_btn)
                
                print(f"[{self.name}] 已点击创建 TP/SL 按钮")
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
                
                print(f"[{self.name}] 找到 {len(modal_inputs)} 个弹窗输入框，开始填写...")
                for i, inp in enumerate(modal_inputs[:2]):  # 最多填两个（止盈和止损）
                    try:
                        self.driver.execute_script("arguments[0].focus();", inp)
                        self.driver.execute_script(f"arguments[0].value = '{self.tp_value}';", inp)
                        self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", inp)
                        self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", inp)
                        print(f"[{self.name}] 已填写输入框 {i+1}: {self.tp_value}%")
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"[{self.name}] 填写输入框 {i+1} 失败: {e}")
                
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
                    
                    print(f"[{self.name}] 点击确认按钮...")
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
                    
                    print(f"[{self.name}] ✅ TP/SL 设置完成")
                    return True
                else:
                    print(f"[{self.name}] ⚠️  未找到确认按钮")
            else:
                print(f"[{self.name}] ⚠️  未找到创建 TP/SL 按钮")
        except Exception as e:
            print(f"[{self.name}] 补设TP/SL失败: {e}")
        return False


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


class DualBrowserHedgeBot:
    def __init__(self, url, start_time=None, morelogin_port1=None, morelogin_port2=None, 
                 morelogin_path1=None, morelogin_path2=None, morelogin_env1=None, morelogin_env2=None,
                 morelogin_api_url="http://127.0.0.1:40000", morelogin_api_id=None, morelogin_api_key=None):
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
        
    def init_drivers(self):
        """初始化两个浏览器"""
        chrome_options1 = Options()
        chrome_options2 = Options()
        driver1 = None
        driver2 = None
        
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
            if self.morelogin_path1:
                print(f"使用 MoreLogin 浏览器1路径: {self.morelogin_path1}")
                chrome_options1.binary_location = self.morelogin_path1
                if USE_AUTO_DRIVER:
                    driver1 = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options1)
                else:
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
                if USE_AUTO_DRIVER:
                    driver2 = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options2)
                else:
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
        thread1 = threading.Thread(target=self.bot1.place_order)
        thread2 = threading.Thread(target=self.bot2.place_order)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
    
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
                
                def set_tp_sl_bot1():
                    if not self.bot1.has_position:
                        print("[浏览器1] 准备设置TP/SL...")
                        self.bot1.check_and_fix_tp_sl()
                
                def set_tp_sl_bot2():
                    if not self.bot2.has_position:
                        print("[浏览器2] 准备设置TP/SL...")
                        self.bot2.check_and_fix_tp_sl()
                
                # 创建线程
                thread1 = threading.Thread(target=set_tp_sl_bot1)
                thread2 = threading.Thread(target=set_tp_sl_bot2)
                
                # 同时启动
                thread1.start()
                thread2.start()
                
                # 等待完成
                thread1.join()
                thread2.join()
                
                print("✅ 两个浏览器的TP/SL设置完成")
        
        # 3. 检测持仓状态变化：从有持仓变成没持仓
        if self.bot1.has_position and not pos1:
            print("[浏览器1] ✅ 持仓已平仓（止损/止盈触发）！")
            # 如果浏览器2还有持仓，立即平掉它（不等待）
            if pos2:
                print("[浏览器2] ⚡ 检测到浏览器1已平仓，立即平掉浏览器2的持仓...")
                # 只等待很短时间确保状态稳定，然后立即平仓
                time.sleep(1)  # 短暂等待确保状态稳定
                if self.bot2.has_position_now():
                    print("[浏览器2] 正在主动平仓...")
                    success = self.bot2.close_position()
                    if success:
                        print("[浏览器2] ✅ 平仓成功")
                    else:
                        print("[浏览器2] ⚠️  平仓失败，将在下次循环重试")
                    time.sleep(1)
                else:
                    print("[浏览器2] 持仓已自动平仓")
            # 记录平仓时间，用于冷却
            self.bot1.last_position_check = datetime.now()
        
        if self.bot2.has_position and not pos2:
            print("[浏览器2] ✅ 持仓已平仓（止损/止盈触发）！")
            # 如果浏览器1还有持仓，立即平掉它（不等待）
            if pos1:
                print("[浏览器1] ⚡ 检测到浏览器2已平仓，立即平掉浏览器1的持仓...")
                # 只等待很短时间确保状态稳定，然后立即平仓
                time.sleep(1)  # 短暂等待确保状态稳定
                if self.bot1.has_position_now():
                    print("[浏览器1] 正在主动平仓...")
                    success = self.bot1.close_position()
                    if success:
                        print("[浏览器1] ✅ 平仓成功")
                    else:
                        print("[浏览器1] ⚠️  平仓失败，将在下次循环重试")
                    time.sleep(1)
                else:
                    print("[浏览器1] 持仓已自动平仓")
            # 记录平仓时间，用于冷却
            self.bot2.last_position_check = datetime.now()
        
        # 4. 更新状态
        self.bot1.has_position = pos1
        self.bot2.has_position = pos2
        
        # 5. 如果两个都没有持仓，准备开新单
        if not pos1 and not pos2:
            # 检查是否刚平仓（需要等待冷却）
            cooldown_time = self.cooldown_after_close
            need_cooldown = False
            if self.bot1.last_position_check:
                elapsed = (datetime.now() - self.bot1.last_position_check).total_seconds()
                if elapsed < cooldown_time:
                    need_cooldown = True
                    wait_time = cooldown_time - elapsed
                    print(f"等待 {int(wait_time)} 秒冷却后再开新单...")
                    time.sleep(wait_time)
            
            if self.bot2.last_position_check and not need_cooldown:
                elapsed = (datetime.now() - self.bot2.last_position_check).total_seconds()
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
            self.bot1.fill_quantity(order_quantity)
            self.bot2.fill_quantity(order_quantity)
            time.sleep(0.5)
            
            # 5. 填写TP/SL
            print("填写止盈止损...")
            self.bot1.fill_tp_sl()
            self.bot2.fill_tp_sl()
            time.sleep(1)
            
            # 6. 同步下单
            self.sync_place_orders()
            
            # 等待持仓出现
            print("等待持仓确认...")
            for _ in range(20):  # 最多等10秒
                if self.bot1.has_position_now() and self.bot2.has_position_now():
                    print("✅ 两个浏览器都已开仓成功！")
                    # 重置平仓时间标记
                    self.bot1.last_position_check = None
                    self.bot2.last_position_check = None
                    break
                time.sleep(0.5)
    
    def run(self):
        """主循环"""
        self.init_drivers()
        self.wait_for_start_time()
        
        self.running = True
        print("开始监控循环...")
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(2)  # 每2秒检查一次
        except KeyboardInterrupt:
            print("\n收到停止信号，正在关闭...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
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
            COOLDOWN_AFTER_CLOSE, WAIT_BEFORE_FORCE_CLOSE
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
        morelogin_api_key=MORELOGIN_API_KEY
    )
    bot.run()

