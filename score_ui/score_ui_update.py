# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'score_ui_update.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1283, 822)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.tile = QtWidgets.QTextEdit(self.centralwidget)
        self.tile.setGeometry(QtCore.QRect(430, 10, 191, 51))
        self.tile.setReadOnly(True)
        self.tile.setObjectName("tile")
        self.next_one = QtWidgets.QPushButton(self.centralwidget)
        self.next_one.setGeometry(QtCore.QRect(1210, 320, 61, 25))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.next_one.setFont(font)
        self.next_one.setObjectName("next_one")
        self.last_one = QtWidgets.QPushButton(self.centralwidget)
        self.last_one.setGeometry(QtCore.QRect(10, 320, 61, 25))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.last_one.setFont(font)
        self.last_one.setObjectName("last_one")
        self.scrollArea = QtWidgets.QScrollArea(self.centralwidget)
        self.scrollArea.setGeometry(QtCore.QRect(620, 160, 581, 591))
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 579, 589))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.pr_text = QtWidgets.QTextBrowser(self.scrollAreaWidgetContents)
        self.pr_text.setGeometry(QtCore.QRect(10, 10, 561, 571))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.pr_text.setFont(font)
        self.pr_text.setObjectName("pr_text")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.scrollArea_2 = QtWidgets.QScrollArea(self.centralwidget)
        self.scrollArea_2.setGeometry(QtCore.QRect(90, 160, 511, 591))
        self.scrollArea_2.setWidgetResizable(True)
        self.scrollArea_2.setObjectName("scrollArea_2")
        self.scrollAreaWidgetContents_2 = QtWidgets.QWidget()
        self.scrollAreaWidgetContents_2.setGeometry(QtCore.QRect(0, 0, 509, 589))
        self.scrollAreaWidgetContents_2.setObjectName("scrollAreaWidgetContents_2")
        self.rule1_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule1_b.setGeometry(QtCore.QRect(10, 120, 16, 51))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule1_b.setFont(font)
        self.rule1_b.setText("")
        self.rule1_b.setObjectName("rule1_b")
        self.rule2_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule2_b.setGeometry(QtCore.QRect(10, 180, 16, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule2_b.setFont(font)
        self.rule2_b.setText("")
        self.rule2_b.setObjectName("rule2_b")
        self.rule3_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule3_b.setGeometry(QtCore.QRect(10, 270, 16, 61))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule3_b.setFont(font)
        self.rule3_b.setText("")
        self.rule3_b.setObjectName("rule3_b")
        self.rule4_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule4_b.setGeometry(QtCore.QRect(10, 350, 16, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule4_b.setFont(font)
        self.rule4_b.setText("")
        self.rule4_b.setObjectName("rule4_b")
        self.rule5_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule5_b.setGeometry(QtCore.QRect(10, 430, 16, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule5_b.setFont(font)
        self.rule5_b.setText("")
        self.rule5_b.setObjectName("rule5_b")
        self.rule6_b = QtWidgets.QRadioButton(self.scrollAreaWidgetContents_2)
        self.rule6_b.setGeometry(QtCore.QRect(10, 490, 16, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule6_b.setFont(font)
        self.rule6_b.setText("")
        self.rule6_b.setObjectName("rule6_b")
        self.save_score = QtWidgets.QPushButton(self.scrollAreaWidgetContents_2)
        self.save_score.setGeometry(QtCore.QRect(410, 560, 89, 25))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.save_score.setFont(font)
        self.save_score.setObjectName("save_score")
        self.groupBox = QtWidgets.QGroupBox(self.scrollAreaWidgetContents_2)
        self.groupBox.setGeometry(QtCore.QRect(10, 10, 491, 81))
        self.groupBox.setObjectName("groupBox")
        self.layoutWidget = QtWidgets.QWidget(self.groupBox)
        self.layoutWidget.setGeometry(QtCore.QRect(0, 30, 491, 41))
        self.layoutWidget.setObjectName("layoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.test_description = QtWidgets.QRadioButton(self.layoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.test_description.setFont(font)
        self.test_description.setObjectName("test_description")
        self.horizontalLayout.addWidget(self.test_description)
        self.test_condition = QtWidgets.QRadioButton(self.layoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.test_condition.setFont(font)
        self.test_condition.setObjectName("test_condition")
        self.horizontalLayout.addWidget(self.test_condition)
        self.test_step = QtWidgets.QRadioButton(self.layoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.test_step.setFont(font)
        self.test_step.setObjectName("test_step")
        self.horizontalLayout.addWidget(self.test_step)
        self.test_result = QtWidgets.QRadioButton(self.layoutWidget)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.test_result.setFont(font)
        self.test_result.setObjectName("test_result")
        self.horizontalLayout.addWidget(self.test_result)
        self.rule1_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule1_l.setGeometry(QtCore.QRect(30, 101, 471, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule1_l.setFont(font)
        self.rule1_l.setText("")
        self.rule1_l.setWordWrap(True)
        self.rule1_l.setObjectName("rule1_l")
        self.rule2_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule2_l.setGeometry(QtCore.QRect(30, 180, 471, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule2_l.setFont(font)
        self.rule2_l.setText("")
        self.rule2_l.setWordWrap(True)
        self.rule2_l.setObjectName("rule2_l")
        self.rule3_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule3_l.setGeometry(QtCore.QRect(30, 260, 471, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule3_l.setFont(font)
        self.rule3_l.setText("")
        self.rule3_l.setWordWrap(True)
        self.rule3_l.setObjectName("rule3_l")
        self.rule4_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule4_l.setGeometry(QtCore.QRect(30, 350, 471, 71))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule4_l.setFont(font)
        self.rule4_l.setText("")
        self.rule4_l.setWordWrap(True)
        self.rule4_l.setObjectName("rule4_l")
        self.rule5_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule5_l.setGeometry(QtCore.QRect(30, 440, 471, 51))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule5_l.setFont(font)
        self.rule5_l.setText("")
        self.rule5_l.setWordWrap(True)
        self.rule5_l.setObjectName("rule5_l")
        self.rule6_l = QtWidgets.QLabel(self.scrollAreaWidgetContents_2)
        self.rule6_l.setGeometry(QtCore.QRect(30, 500, 471, 51))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.rule6_l.setFont(font)
        self.rule6_l.setText("")
        self.rule6_l.setWordWrap(True)
        self.rule6_l.setObjectName("rule6_l")
        self.scrollArea_2.setWidget(self.scrollAreaWidgetContents_2)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(256, 86, 61, 21))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setGeometry(QtCore.QRect(217, 126, 101, 21))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setGeometry(QtCore.QRect(630, 13, 50, 21))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.label_3.setFont(font)
        self.label_3.setObjectName("label_3")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setGeometry(QtCore.QRect(630, 47, 50, 21))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.label_4.setFont(font)
        self.label_4.setObjectName("label_4")
        self.is_scored = QtWidgets.QTextEdit(self.centralwidget)
        self.is_scored.setGeometry(QtCore.QRect(690, 10, 131, 31))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.is_scored.setFont(font)
        self.is_scored.setReadOnly(True)
        self.is_scored.setObjectName("is_scored")
        self.is_not_scored = QtWidgets.QTextEdit(self.centralwidget)
        self.is_not_scored.setGeometry(QtCore.QRect(690, 40, 131, 31))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.is_not_scored.setFont(font)
        self.is_not_scored.setReadOnly(True)
        self.is_not_scored.setObjectName("is_not_scored")
        self.jump_input = QtWidgets.QTextEdit(self.centralwidget)
        self.jump_input.setGeometry(QtCore.QRect(890, 10, 131, 31))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.jump_input.setFont(font)
        self.jump_input.setReadOnly(False)
        self.jump_input.setObjectName("jump_input")
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setGeometry(QtCore.QRect(830, 13, 50, 21))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.jump_button = QtWidgets.QPushButton(self.centralwidget)
        self.jump_button.setGeometry(QtCore.QRect(1030, 12, 61, 25))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.jump_button.setFont(font)
        self.jump_button.setObjectName("jump_button")
        self.total_pr = QtWidgets.QTextEdit(self.centralwidget)
        self.total_pr.setGeometry(QtCore.QRect(890, 40, 131, 31))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.total_pr.setFont(font)
        self.total_pr.setReadOnly(True)
        self.total_pr.setObjectName("total_pr")
        self.label_6 = QtWidgets.QLabel(self.centralwidget)
        self.label_6.setGeometry(QtCore.QRect(830, 43, 50, 21))
        font = QtGui.QFont()
        font.setPointSize(13)
        self.label_6.setFont(font)
        self.label_6.setObjectName("label_6")
        self.pr_url = QtWidgets.QLabel(self.centralwidget)
        self.pr_url.setGeometry(QtCore.QRect(330, 80, 731, 31))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.pr_url.setFont(font)
        self.pr_url.setText("")
        self.pr_url.setOpenExternalLinks(True)
        self.pr_url.setObjectName("pr_url")
        self.pr_files_url = QtWidgets.QLabel(self.centralwidget)
        self.pr_files_url.setGeometry(QtCore.QRect(330, 120, 731, 31))
        font = QtGui.QFont()
        font.setPointSize(14)
        self.pr_files_url.setFont(font)
        self.pr_files_url.setText("")
        self.pr_files_url.setOpenExternalLinks(True)
        self.pr_files_url.setObjectName("pr_files_url")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1283, 28))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.tile.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'Ubuntu\'; font-size:11pt; font-weight:400; font-style:normal;\">\n"
"<p align=\"center\" style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:20pt;\">打分程序</span></p></body></html>"))
        self.next_one.setText(_translate("MainWindow", "下一个"))
        self.last_one.setText(_translate("MainWindow", "上一个"))
        self.save_score.setText(_translate("MainWindow", "保存评分"))
        self.groupBox.setTitle(_translate("MainWindow", "测试方案组成"))
        self.test_description.setText(_translate("MainWindow", "测试描述"))
        self.test_condition.setText(_translate("MainWindow", "前置步骤"))
        self.test_step.setText(_translate("MainWindow", "执行步骤"))
        self.test_result.setText(_translate("MainWindow", "预期结果"))
        self.label.setText(_translate("MainWindow", "pr url："))
        self.label_2.setText(_translate("MainWindow", "pr files url："))
        self.label_3.setText(_translate("MainWindow", "已标："))
        self.label_4.setText(_translate("MainWindow", "剩余："))
        self.label_5.setText(_translate("MainWindow", "当前："))
        self.jump_button.setText(_translate("MainWindow", "跳转"))
        self.label_6.setText(_translate("MainWindow", "共计："))
