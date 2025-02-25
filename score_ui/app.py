from functools import partial
import re
import sys
import os
import json
import markdown
import markdown2
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from score_ui_update import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, json_path, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.json_path = json_path
        self.current_pr_index = 0
        self.pr_data = []
        self.scores = {}  # 用于存储每个 PR 的评分，键为 PR 索引，值为评分字典
        self.temp_scores = {}  # 临时存储当前 PR 的评分情况
        self.load_json_with_test_plan()
        self.is_first_use = True
        # 初始化评分规则
        self.rules = {
            'test_description': [
                "8-10分：详细介绍了要测试的内容，并且完整对应于真实代码改动.描述清晰且与项目需求紧密对接，充分覆盖了所有关键特性。",
                "6-8分：介绍了大部分要测试的内容，并与代码改动相关，但可能遗漏了一些细节或关键特性。描述较为清晰，基本符合项目需求。",
                "4-6分：描述了部分要测试的内容，且与代码改动关系较弱，存在一定程度的遗漏。测试范围或目标不够明确，部分内容缺乏足够的细节。",
                "2-4分：测试描述缺乏足够的细节，未能清晰表达要测试的内容。与代码改动关系不明显，很多关键信息未涵盖，导致理解困难。",
                "0-2分：测试描述几乎不存在，或与代码改动无关。没有明确的目标和测试范围，无法推测要测试什么内容。",
                "0分：没有描述测试内容，无法判断测试的目标和范围。"
            ],
            'test_condition': [
                "8-10分：前置条件详尽并且符合实际，列出了所有必需的假设、约束和测试环境。完全满足测试所需，环境搭建和资源准备充分。",
                "6-8分：大多数前置条件明确，涵盖了假设、约束和环境要求，但可能略有遗漏或缺乏一些细节。整体准备较为充分。",
                "4-6分：列出了部分前置条件，但有明显遗漏或假设不明确。测试环境和工具要求可能不完全清晰，测试的可行性受到影响。",
                "2-4分：前置条件描述简略，缺乏必要的假设和约束条件，测试环境不明确，可能影响测试的顺利执行。",
                "0-2分：几乎没有描述前置条件，假设和约束完全缺失，测试环境没有说明，测试无法进行。",
                "0分：没有描述前置条件，无法判断测试的可行性。"
            ],
            'test_step': [
                "8-10分：测试步骤清晰、完整，详细描述了测试用例的执行方法，测试用例涵盖了所有功能点并且与代码改动紧密相关。步骤可执行且易于理解。",
                "6-8分：大多数测试步骤清晰，涵盖了主要功能点，但可能遗漏一些边界情况或细节。整体上，测试步骤易于执行，但有改进空间。",
                "4-6分：测试步骤部分描述，执行方法不完全明确或存在一定的模糊性。测试用例可能遗漏某些功能点，导致无法全面覆盖代码改动。",
                "2-4分：测试步骤不完整或含糊不清。执行方法缺乏细节，测试用例覆盖不全，可能导致测试无法顺利执行。",
                "0-2分：没有明确的测试步骤或描述极其模糊，测试用例几乎无法执行。缺乏足够的指导信息，导致测试完全无法进行。",
                "0分：没有描述测试步骤，无法判断测试的执行方法。"
            ],
            'test_result': [
                "8-10分：测试预期明确且详细，成功和失败的标准完全对齐，准确地定义了每个测试用例的预期结果，包含了所有边界条件和特殊情况。",
                "6-8分：大部分测试预期清晰，成功和失败的标准较为明确，但可能遗漏了一些特殊情况或边界条件。预期结果基本准确，符合大多数测试用例。",
                "4-6分：测试预期部分明确，但对成功和失败的标准描述不足，可能没有覆盖所有的边界条件和特殊情况。预期结果不完全准确，测试可能存在偏差。",
                "2-4分：测试预期描述模糊，成功和失败的标准不清晰，未能覆盖所有关键点。预期结果不明确，可能导致无法判断测试是否成功。",
                "0-2分：测试预期几乎没有描述，成功和失败的标准完全缺失，无法判断测试是否成功。预期结果不清晰，测试无法验证。",
                "0分：没有描述测试预期，无法判断测试的成功标准。"
            ]
        }
        self.display_pr()

        # 连接按钮
        self.next_one.clicked.connect(self.next_pr)
        self.last_one.clicked.connect(self.previous_pr)
        self.save_score.clicked.connect(self.save_current_score)

        # 连接单选按钮
        self.test_description.clicked.connect(partial(self.load_rules, 'test_description'))
        self.test_condition.clicked.connect(partial(self.load_rules, 'test_condition'))
        self.test_step.clicked.connect(partial(self.load_rules, 'test_step'))
        self.test_result.clicked.connect(partial(self.load_rules, 'test_result'))

        # 连接跳转按钮
        self.jump_button.clicked.connect(self.jump_to_pr)

        # 连接lable与radio_button
        for i in range(6):
            label = getattr(self, f'rule{i+1}_l')
            radio_button = getattr(self, f'rule{i+1}_b')
            label.mousePressEvent = self.connect_label_click_to_radioButton(radio_button)

        # 初始化评分状态显示
        self.update_score_status()

        # 初始化 PR 计数显示
        self.update_pr_count_label()

    def connect_label_click_to_radioButton(self, radio_button):
        def handler(event):
            radio_button.setChecked(not radio_button.isChecked())
        return handler

    def load_json_with_test_plan(self):
        if not os.path.exists(self.json_path):
            QMessageBox.critical(self, "错误", f"JSON 文件未找到: {self.json_path}")
            sys.exit(1)
        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        prs = []
        pr_data_idx = 0
        for _, project_info in data.items():
            project_prs = project_info.get('项目prs', [])
            with_test_plan_prs = []
            for pr in project_prs:
                if '测试计划' in pr and pr['测试计划'] != 'None':
                    with_test_plan_prs.append(pr)
            # 合并prs与project_prs
            prs.extend(with_test_plan_prs)
            for pr in with_test_plan_prs:
                self.scores[pr_data_idx] = pr.get('评分结果', {})
                pr_data_idx +=1 

        prs = sorted(prs, key=lambda x: len(x['测试计划']), reverse=True).copy()
        self.pr_data = prs
        if not self.pr_data:
            QMessageBox.critical(self, "错误", "没有找到 PR 数据。")
            sys.exit(1)

    def load_json(self):
        if not os.path.exists(self.json_path):
            QMessageBox.critical(self, "错误", f"JSON 文件未找到: {self.json_path}")
            sys.exit(1)
        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        prs = []
        pr_data_idx = 0
        for _, project_info in data.items():
            project_prs = project_info.get('项目prs', [])
            # 合并prs与project_prs
            prs.extend(project_prs)
            for pr in project_prs:
                self.scores[pr_data_idx] = pr.get('评分结果', {})
                pr_data_idx +=1 

        self.pr_data = prs

        if not self.pr_data:
            QMessageBox.critical(self, "错误", "没有找到 PR 数据。")
            sys.exit(1)

        # 初始化评分字典
        # self.scores = {i: {} for i in range(len(self.pr_data))}

    def display_pr(self):
        if not self.pr_data:
            return
        pr = self.pr_data[self.current_pr_index]
        self.pr_url.setText(f"<a style='color: black; text-decoration: none' href = {pr.get('pr网址', '')}>{pr.get('pr网址', '')}")
        self.pr_files_url.setText(f"<a style='color: black; text-decoration: none' href = {pr.get('pr_files_url', '')}>{pr.get('pr_files_url', '')}")
        
        # 格式化 PR 描述和代码
        description = pr.get('测试计划', '')
        if description is not str:
            description = str(description)
        clean_description = re.sub(r'\r\n', '\n', description)
        
        # 转换 Markdown 为 HTML，启用 GFM 和代码高亮
        html_description = markdown.markdown(
            clean_description,
            extras=[
                "fenced-code-blocks",
                "code-friendly",
                "tables",
                "strike",
                "task_lists"
            ],
            extension_configs={
                'codehilite': {
                    'linenums': False,
                    'guess_lang': False
                }
            }
        )
        
        # 可选：添加高亮 CSS 样式
        css_styles = """
        <style>
            /* Pygments 或 CodeHilite 样式 */
            .codehilite { background: #f8f8f8; padding: 10px; }
            .codehilite .hll { background-color: #ffffcc }
            .codehilite .c { color: #408080; font-style: italic }
            code { 
                background-color: #f0f0f0; 
                padding: 2px 4px; 
                border-radius: 4px; 
                font-family: monospace; 
            }
            /* 代码块样式 */
            pre { 
                background-color: #f8f8f8; 
                padding: 10px; 
                border-radius: 4px; 
                overflow: auto; 
            }
        </style>
        """
        
        # 构建最终 HTML 内容
        html_content = f"""
        <html>
            <head>
                {css_styles}
            </head>
            <body>
                {html_description}
            </body>
        </html>
        """
        self.pr_text.setHtml(html_content)

        # 更新评分规则显示（默认选择第一个维度）
        if not (self.test_description.isChecked() or self.test_condition.isChecked() or 
                self.test_step.isChecked() or self.test_result.isChecked()):
            self.test_description.setChecked(True)
            self.load_rules('test_description')
        # 更新评分状态显示
        # 加载已有评分
        self.load_existing_scores()
        if not self.is_first_use:
            self.test_description.setChecked(True)
            self.load_rules('test_description')
        # 更新 PR 计数显示
        self.update_pr_count_label()

    def jump_to_pr(self):
        input_text = self.jump_input.toPlainText().strip()
        if not input_text.isdigit():
            QMessageBox.warning(self, "输入错误", "请输入有效的 PR 索引（数字）。")
            return
        pr_index = int(input_text) - 1  # 假设用户输入的是从1开始的索引
        if pr_index < 0 or pr_index >= len(self.pr_data):
            QMessageBox.warning(self, "输入错误", f"请输入介于 1 和 {len(self.pr_data)} 之间的数字。")
            return
        self.current_pr_index = pr_index
        self.display_pr()

    def update_pr_count_label(self):
        self.jump_input.setText(f"{self.current_pr_index + 1}")
        self.total_pr.setText(f"{len(self.pr_data)}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A:
            self.previous_pr()
        elif event.key() == Qt.Key_D:
            self.next_pr()
        else:
            super(MainWindow, self).keyPressEvent(event)

    def load_existing_scores(self):
        # 加载当前 PR 的评分情况
        pr_index = self.current_pr_index
        self.temp_scores = {}  # 重置临时评分
        if self.scores.get(pr_index):
            self.temp_scores = self.scores[pr_index].copy()
        else:
            self.temp_scores = {}
        self.update_score_status()

    def next_pr(self):
        self.is_first_use = False
        if self.current_pr_index < len(self.pr_data) - 1:
            self.current_pr_index += 1
            self.display_pr()
        else:
            QMessageBox.information(self, "信息", "已经是最后一个 PR 了。")

    def previous_pr(self):
        self.is_first_use = False
        if self.current_pr_index > 0:
            self.current_pr_index -= 1
            self.display_pr()
        else:
            QMessageBox.information(self, "信息", "已经是第一个 PR 了。")


    def load_rules(self, dimension):
        test_rules = self.rules.get(dimension, [])
        # 设置新的规则
        self.clear_rules()

        for i in range(6):
            rule_text = test_rules[i] if i < len(test_rules) else ""
            rule_widget = getattr(self, f'rule{i+1}_l')
            rule_widget.setText(f"{rule_text}")
            radio_button = getattr(self, f'rule{i+1}_b')
            # radio_button.setText(rule_text)
            
            # 阻断信号以防止触发update_temp_score
            radio_button.blockSignals(True)
            
            # 根据 temp_scores 或 scores 设置选中状态
            if dimension in self.temp_scores and self.temp_scores[dimension] == i:
                radio_button.setChecked(True)
            elif self.current_pr_index in self.scores and dimension in self.scores[self.current_pr_index]:
                if self.scores[self.current_pr_index][dimension] == i:
                    radio_button.setChecked(True)
                else:
                    radio_button.setChecked(False)
            else:
                radio_button.setChecked(False)
            
            # 恢复信号
            radio_button.blockSignals(False)

        # 连接 RadioButtons 的状态改变信号以更新 temp_scores
        for i in range(6):
            radio_button = getattr(self, f'rule{i+1}_b')
            try:
                radio_button.toggled.disconnect()
            except:
                pass
            radio_button.toggled.connect(partial(self.update_temp_score, dimension, i))

    def update_temp_score(self, dimension, index, state):
        if state:
            self.temp_scores[dimension] = index
            # 确保同一维度内只选一个规则（RadioButtons 默认互斥）
        else:
            if dimension in self.temp_scores and self.temp_scores[dimension] == index:
                del self.temp_scores[dimension]
        # 评分状态会在 save_score 中统一更新

    def clear_rules(self):

        # 清除所有 RadioButtons 的状态和文本
        for i in range(6):
            rule_widget = getattr(self, f'rule{i+1}_l')
            rule_widget.clear()
            radio_button = getattr(self, f'rule{i+1}_b')
            # radio_button.setText("")
            # 阻断信号以防止触发update_temp_score
            radio_button.blockSignals(True)
            radio_button.setChecked(False)
            try:
                radio_button.toggled.disconnect()
            except:
                pass
            # 恢复信号
            radio_button.blockSignals(False)
        
        
    def save_current_score(self):
        # 确保所有评分维度都有评分
        required_dimensions = ['test_description', 'test_condition', 'test_step', 'test_result']
        missing_dimensions = [dim for dim in required_dimensions if dim not in self.temp_scores]
        if missing_dimensions:
            QMessageBox.warning(self, "未完成评分", f"请完成所有评分维度的评分：{', '.join(missing_dimensions)}。")
            return

        pr_index = self.current_pr_index
        # 将 temp_scores 保存到 scores
        self.scores[pr_index] = self.temp_scores.copy()

        # 更新评分状态显示
        self.update_score_status()

        QMessageBox.information(self, "保存成功", f"已保存第 {self.current_pr_index + 1} 个 PR 的评分。")

    def update_score_status(self):
        scored = sum(1 for score in self.scores.values() if score!= {})
        remaining = len(self.pr_data) - scored
        self.is_scored.setPlainText(str(scored))
        self.is_not_scored.setPlainText(str(remaining))

    def closeEvent(self, event):
        with open(self.json_path, 'r', encoding='utf-8') as f:
            prs_data = json.load(f)
        pr_score_idx = 0
        for _, project_info in prs_data.items():
            project_prs = project_info.get('项目prs', [])
            for pr in project_prs:
                pr['评分结果'] = self.scores[pr_score_idx]
                pr_score_idx += 1

        # 保存 pr_data 回 JSON 文件
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(prs_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存评分结果到 JSON 文件: {e}")
            event.ignore()
            return

        event.accept()

if __name__ == "__main__":
    

    app = QApplication(sys.argv)
    json_file_path = 'data/llm_restructed_pull_request.json'  # 请将此路径替换为您的 JSON 文件路径
    window = MainWindow(json_file_path)
    window.show()
    sys.exit(app.exec_())