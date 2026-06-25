"""
主窗口界面
- 标签1: 摄像头预览 + 识别结果
- 标签2: 通行记录查询
- 标签3: 系统设置
"""
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer


class MainWindow(QtWidgets.QMainWindow):
    """门禁系统主窗口（YOLOv5版）"""

    WINDOW_WIDTH = 900
    WINDOW_HEIGHT = 700

    def __init__(self, db, hardware):
        super().__init__()
        self.db = db
        self.hardware = hardware
        self._active_thread = None

        self._init_ui()
        self._init_timer()
        self._connect_actions()
        self._apply_initial_state()

    # ==================== UI 初始化 ====================

    def _init_ui(self):
        self.setWindowTitle('智能门禁系统 - YOLOv5')
        self.resize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        try:
            self.setWindowIcon(QtGui.QIcon('ui/app_icon.png'))
        except Exception:
            pass

        # 全局默认字体，确保所有文字清晰可读
        font = QtGui.QFont()
        font.setPointSize(10)
        self.setFont(font)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        # 顶部信息栏
        top_bar = QtWidgets.QHBoxLayout()
        self.user_label = QtWidgets.QLabel('未登录')
        self.user_label.setStyleSheet(
            'color: #cdd6f4; font-size: 14px; font-weight: bold;')
        self.backend_label = QtWidgets.QLabel('')
        self.backend_label.setStyleSheet(
            'color: #a6e3a1; font-size: 13px; font-weight: bold;')
        self.fps_label = QtWidgets.QLabel('')
        self.fps_label.setStyleSheet('color: #f9e2af; font-size: 13px;')
        top_bar.addWidget(self.user_label)
        top_bar.addStretch()
        top_bar.addWidget(self.fps_label)
        top_bar.addWidget(self.backend_label)

        # 标签页
        self.tabs = QtWidgets.QTabWidget()
        self._init_preview_tab()
        self._init_records_tab()
        self._init_settings_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 底部状态栏
        self.statusbar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QtWidgets.QLabel('就绪')
        self.statusbar.addWidget(self.status_label)

        # 菜单栏
        self._init_menubar()

        # 整体布局
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.tabs)

        # 全局样式 — 现代化护眼暗色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QTabWidget::pane {
                border: 1px solid #45475a;
                background: #1e1e2e;
                border-top: none;
            }
            QTabBar::tab {
                background: #313244;
                color: #a6adc8;
                padding: 10px 28px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e;
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #45475a;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
                background: transparent;
            }
            QTableWidget {
                background: #1e1e2e;
                alternate-background-color: #242438;
                color: #cdd6f4;
                gridline-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                selection-background-color: #45475a;
                selection-color: #cdd6f4;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QHeaderView::section {
                background: #313244;
                color: #cdd6f4;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid #45475a;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 5px 8px;
                selection-background-color: #89b4fa;
                selection-color: #1e1e2e;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QDoubleSpinBox:focus, QDateEdit:focus {
                border-color: #89b4fa;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 6px;
            }
            QComboBox QAbstractItemView {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                selection-background-color: #45475a;
            }
            QPushButton {
                background: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 5px;
                padding: 7px 18px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #585b70;
            }
            QPushButton:pressed {
                background: #313244;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1e1e2e;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #585b70;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QMenuBar {
                background: #181825;
                color: #cdd6f4;
                border-bottom: 1px solid #313244;
            }
            QMenuBar::item:selected {
                background: #45475a;
                color: #cdd6f4;
            }
            QMenuBar::item:disabled {
                color: #585b70;
            }
            QMenu {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 32px 6px 20px;
            }
            QMenu::item:selected {
                background: #45475a;
                color: #cdd6f4;
            }
            QMenu::item:disabled {
                color: #585b70;
                background: transparent;
            }
            QStatusBar {
                background: #181825;
                color: #a6adc8;
                border-top: 1px solid #313244;
            }
            QCheckBox {
                color: #cdd6f4;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #45475a;
                border-radius: 3px;
                background: #313244;
            }
            QCheckBox::indicator:checked {
                background: #89b4fa;
                border-color: #89b4fa;
            }
            QSplitter::handle {
                background: #45475a;
                width: 2px;
            }
            QToolTip {
                background: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                padding: 4px;
                border-radius: 3px;
            }
            QMessageBox {
                background: #1e1e2e;
            }
            QMessageBox QLabel {
                color: #cdd6f4;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                min-width: 70px;
                min-height: 28px;
            }
            QDialog {
                background: #1e1e2e;
            }
            QInputDialog {
                background: #1e1e2e;
            }
            QInputDialog QLabel {
                color: #cdd6f4;
                font-size: 13px;
            }
            QInputDialog QLineEdit {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 5px 8px;
            }
        """)

    def _init_menubar(self):
        menubar = self.menuBar()

        # 管理菜单
        manage_menu = menubar.addMenu('管理')
        self.act_login = manage_menu.addAction('登录')
        self.act_register = manage_menu.addAction('注册')
        self.act_signout = manage_menu.addAction('注销')
        manage_menu.addSeparator()
        self.act_auto_run = manage_menu.addAction('自动运行')
        manage_menu.addSeparator()
        manage_menu.addAction('退出程序').triggered.connect(self._on_exit)

        # 设置菜单
        setup_menu = menubar.addMenu('功能')
        self.act_camera = setup_menu.addAction('开启摄像头')
        self.act_face_detect = setup_menu.addAction('启动人脸识别')
        self.act_enroll = setup_menu.addAction('录入人脸数据')
        self.act_train = setup_menu.addAction('训练人脸模型')

    # ---- 三个标签页 ----

    def _init_preview_tab(self):
        """标签1: 摄像头预览 + 识别结果"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # 摄像头画面
        self.video_label = QtWidgets.QLabel('摄像头未启动')
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet(
            'background: #11111b; border: 2px solid #45475a; '
            'border-radius: 6px; color: #7f849c;')
        layout.addWidget(self.video_label, 8)

        # 识别结果（大字红色）
        self.result_label = QtWidgets.QLabel('')
        font = QtGui.QFont()
        font.setPointSize(36)
        self.result_label.setFont(font)
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet(
            'color: #f38ba8; border: none; font-weight: bold;')
        layout.addWidget(self.result_label, 2)

        # 快捷统计
        stats_layout = QtWidgets.QHBoxLayout()
        self.stat_total = QtWidgets.QLabel('总通行: 0')
        self.stat_today = QtWidgets.QLabel('今日: 0')
        self.stat_success = QtWidgets.QLabel('成功: 0')
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_today)
        stats_layout.addWidget(self.stat_success)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        self.tabs.addTab(tab, '摄像头预览')

    def _init_records_tab(self):
        """标签2: 通行记录查询"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(8)

        # ---- 统计卡片 ----
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(10)
        self.card_today = self._make_stat_card('今日通行', '0', '#89b4fa')
        self.card_success = self._make_stat_card('识别成功', '0', '#a6e3a1')
        self.card_fail = self._make_stat_card('识别失败', '0', '#f38ba8')
        self.card_fever = self._make_stat_card('体温异常', '0', '#fab387')
        for c in [self.card_today, self.card_success, self.card_fail, self.card_fever]:
            cards.addWidget(c)
        layout.addLayout(cards)

        # ---- 筛选栏 ----
        filter_bar = QtWidgets.QHBoxLayout()
        filter_bar.setSpacing(8)

        # 快捷日期
        self.btn_today = QtWidgets.QPushButton('今天')
        self.btn_today.clicked.connect(lambda: self._quick_date('today'))
        self.btn_3days = QtWidgets.QPushButton('3天')
        self.btn_3days.clicked.connect(lambda: self._quick_date('3days'))
        self.btn_week = QtWidgets.QPushButton('本周')
        self.btn_week.clicked.connect(lambda: self._quick_date('week'))
        self.btn_all = QtWidgets.QPushButton('全部')
        self.btn_all.clicked.connect(lambda: self._quick_date('all'))
        filter_bar.addWidget(self.btn_today)
        filter_bar.addWidget(self.btn_3days)
        filter_bar.addWidget(self.btn_week)
        filter_bar.addWidget(self.btn_all)

        filter_bar.addWidget(QtWidgets.QLabel('|'))

        # 日期范围
        filter_bar.addWidget(QtWidgets.QLabel('从'))
        self.date_from = QtWidgets.QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QtCore.QDate.currentDate())
        self.date_from.setMaximumWidth(120)
        filter_bar.addWidget(self.date_from)
        filter_bar.addWidget(QtWidgets.QLabel('至'))
        self.date_to = QtWidgets.QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.setMaximumWidth(120)
        filter_bar.addWidget(self.date_to)

        # 结果类型
        filter_bar.addWidget(QtWidgets.QLabel('结果'))
        self.filter_result = QtWidgets.QComboBox()
        self.filter_result.addItems(['全部', '通行成功', '识别失败', '体温异常', '距离异常'])
        self.filter_result.setMaximumWidth(90)
        filter_bar.addWidget(self.filter_result)

        # 关键字
        self.filter_keyword = QtWidgets.QLineEdit()
        self.filter_keyword.setPlaceholderText('搜索姓名/账号...')
        self.filter_keyword.setMaximumWidth(140)
        filter_bar.addWidget(self.filter_keyword)

        self.btn_query = QtWidgets.QPushButton('查询')
        self.btn_query.clicked.connect(self._on_query_records)
        filter_bar.addWidget(self.btn_query)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # ---- 主内容区：表格 + 详情面板 ----
        splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # 左侧：表格
        self.records_table = QtWidgets.QTableWidget()
        self.records_table.setColumnCount(7)
        self.records_table.setHorizontalHeaderLabels(
            ['时间', '姓名', '账号', '结果', '体温', '置信度', '编号'])
        self.records_table.horizontalHeader().setStretchLastSection(True)
        self.records_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.records_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.records_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.setColumnWidth(0, 150)  # 时间
        self.records_table.setColumnWidth(1, 80)   # 姓名
        self.records_table.setColumnWidth(2, 80)   # 账号
        self.records_table.setColumnWidth(3, 80)   # 结果
        self.records_table.setColumnWidth(4, 60)   # 体温
        self.records_table.setColumnWidth(5, 60)   # 置信度
        self.records_table.setColumnHidden(6, True)  # 隐藏编号列
        self.records_table.clicked.connect(self._on_record_selected)
        splitter.addWidget(self.records_table)

        # 右侧：详情面板
        detail_panel = QtWidgets.QWidget()
        detail_panel.setMaximumWidth(280)
        detail_layout = QtWidgets.QVBoxLayout(detail_panel)
        detail_layout.setSpacing(6)

        title = QtWidgets.QLabel('记录详情')
        title.setStyleSheet(
            'font-size: 15px; font-weight: bold; color: #cdd6f4;')
        title.setAlignment(Qt.AlignCenter)
        detail_layout.addWidget(title)

        self.detail_image = QtWidgets.QLabel('点击记录查看抓拍')
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setMinimumHeight(200)
        self.detail_image.setStyleSheet(
            'background: #11111b; border: 1px solid #45475a; '
            'border-radius: 4px; color: #585b70;')
        detail_layout.addWidget(self.detail_image)

        self.detail_info = QtWidgets.QLabel('')
        self.detail_info.setStyleSheet(
            'color: #bac2de; font-size: 12px; line-height: 1.6;')
        self.detail_info.setWordWrap(True)
        detail_layout.addWidget(self.detail_info)

        detail_layout.addStretch()
        splitter.addWidget(detail_panel)
        splitter.setSizes([500, 260])

        layout.addWidget(splitter)

        # ---- 底部信息栏 ----
        bottom_bar = QtWidgets.QHBoxLayout()
        self.record_count_label = QtWidgets.QLabel('共 0 条记录')
        self.record_count_label.setStyleSheet('color: #a6adc8;')
        bottom_bar.addWidget(self.record_count_label)
        bottom_bar.addStretch()
        self.btn_prev_page = QtWidgets.QPushButton('上一页')
        self.btn_prev_page.setMaximumWidth(70)
        self.btn_prev_page.clicked.connect(self._on_prev_page)
        bottom_bar.addWidget(self.btn_prev_page)
        self.page_label = QtWidgets.QLabel('第 1 页')
        self.page_label.setStyleSheet('color: #a6adc8;')
        bottom_bar.addWidget(self.page_label)
        self.btn_next_page = QtWidgets.QPushButton('下一页')
        self.btn_next_page.setMaximumWidth(70)
        self.btn_next_page = QtWidgets.QPushButton('下一页')
        self.btn_next_page.setMaximumWidth(60)
        self.btn_next_page.clicked.connect(self._on_next_page)
        bottom_bar.addWidget(self.btn_next_page)
        layout.addLayout(bottom_bar)

        self._page = 0
        self._page_size = 50

        self.tabs.addTab(tab, '通行记录')

    def _make_stat_card(self, title, value, color):
        """创建统计卡片"""
        card = QtWidgets.QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: #242438; border-left: 3px solid {color}; '
            f'border-radius: 6px; }}')
        card.setMinimumHeight(80)
        card.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        inner = QtWidgets.QVBoxLayout(card)
        inner.setContentsMargins(8, 10, 8, 10)
        inner.setSpacing(6)
        lbl_val = QtWidgets.QLabel(value)
        lbl_val.setStyleSheet(
            f'color: {color}; font-size: 28px; font-weight: bold; border: none;')
        lbl_val.setAlignment(Qt.AlignCenter)
        inner.addWidget(lbl_val)
        lbl_title = QtWidgets.QLabel(title)
        lbl_title.setStyleSheet(
            'color: #bac2de; font-size: 14px; font-weight: bold; border: none;')
        lbl_title.setAlignment(Qt.AlignCenter)
        inner.addWidget(lbl_title)
        card.value_label = lbl_val
        return card

    def _quick_date(self, mode):
        """快捷日期筛选"""
        today = QtCore.QDate.currentDate()
        if mode == 'today':
            self.date_from.setDate(today)
            self.date_to.setDate(today)
        elif mode == '3days':
            self.date_from.setDate(today.addDays(-3))
            self.date_to.setDate(today)
        elif mode == 'week':
            self.date_from.setDate(today.addDays(-(today.dayOfWeek() - 1)))
            self.date_to.setDate(today)
        elif mode == 'all':
            self.date_from.setDate(QtCore.QDate(2020, 1, 1))
            self.date_to.setDate(today)
        self._on_query_records()

    def _init_settings_tab(self):
        """标签3: 系统设置 — 分组卡片式布局"""
        tab = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(tab)
        outer.setSpacing(0)

        # 滚动区域
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { border: none; background: #1e1e2e; }')
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        # ===== 模型状态卡片 =====
        layout.addWidget(self._section_title('模型状态'))
        status_card = QtWidgets.QFrame()
        status_card.setStyleSheet(
            'QFrame { background: #242438; border: 1px solid #45475a; '
            'border-radius: 8px; padding: 10px; }')
        status_inner = QtWidgets.QFormLayout(status_card)
        status_inner.setSpacing(6)
        self.model_status_label = QtWidgets.QLabel('未训练')
        self.model_status_label.setStyleSheet(
            'color: #f38ba8; font-weight: bold; border: none;')
        status_inner.addRow('状态:', self.model_status_label)
        self.model_path_label = QtWidgets.QLabel('./model/model.xml')
        self.model_path_label.setStyleSheet('color: #a6adc8; border: none;')
        status_inner.addRow('路径:', self.model_path_label)
        self.model_people_label = QtWidgets.QLabel('0 人')
        self.model_people_label.setStyleSheet('color: #a6adc8; border: none;')
        status_inner.addRow('已注册:', self.model_people_label)
        layout.addWidget(status_card)

        # ===== 检测引擎设置 =====
        layout.addWidget(self._section_title('检测引擎'))
        det_card = self._make_card()
        det_form = QtWidgets.QFormLayout(det_card)
        det_form.setSpacing(8)

        self.setting_detect_method = QtWidgets.QComboBox()
        self.setting_detect_method.addItems(['yolov5', 'haar'])
        det_form.addRow('检测方法:', self._row_with_hint(
            self.setting_detect_method, 'YOLOv5精度高但需要GPU/ONNX；Haar轻量可在纯CPU上运行'))

        self.setting_model_name = QtWidgets.QComboBox()
        self.setting_model_name.addItems(['yolov5n', 'yolov5s', 'yolov5m', 'yolov5l'])
        det_form.addRow('YOLO模型:', self._row_with_hint(
            self.setting_model_name, 'n=最轻量(快)/s=平衡/m=中等/l=最准(慢)，嵌入式平台推荐n或s'))

        self.setting_conf_threshold = QtWidgets.QDoubleSpinBox()
        self.setting_conf_threshold.setRange(0.1, 1.0)
        self.setting_conf_threshold.setSingleStep(0.05)
        self.setting_conf_threshold.setValue(0.5)
        det_form.addRow('检测阈值:', self._row_with_hint(
            self.setting_conf_threshold, '越高漏检越少但误检增多，推荐0.4~0.6'))

        self.setting_recog_threshold = QtWidgets.QDoubleSpinBox()
        self.setting_recog_threshold.setRange(10, 200)
        self.setting_recog_threshold.setValue(70)
        det_form.addRow('识别阈值:', self._row_with_hint(
            self.setting_recog_threshold, 'LBPH置信度，越低越严格。低于此值判为识别成功，推荐50~80'))
        layout.addWidget(det_card)

        # ===== 门禁控制设置 =====
        layout.addWidget(self._section_title('门禁控制'))
        gate_card = self._make_card()
        gate_form = QtWidgets.QFormLayout(gate_card)
        gate_form.setSpacing(8)

        self.setting_temp_limit = QtWidgets.QDoubleSpinBox()
        self.setting_temp_limit.setRange(35.0, 42.0)
        self.setting_temp_limit.setSingleStep(0.1)
        self.setting_temp_limit.setValue(37.2)
        self.setting_temp_limit.setSuffix(' °C')
        gate_form.addRow('体温上限:', self._row_with_hint(
            self.setting_temp_limit, '超过此温度判定为发热，拒绝通行并语音告警'))

        # 距离范围
        dist_w = QtWidgets.QWidget()
        dist_layout = QtWidgets.QHBoxLayout(dist_w)
        dist_layout.setContentsMargins(0, 0, 0, 0)
        self.setting_dist_min = QtWidgets.QSpinBox()
        self.setting_dist_min.setRange(0, 50)
        self.setting_dist_min.setValue(10)
        dist_layout.addWidget(QtWidgets.QLabel('最小'))
        dist_layout.addWidget(self.setting_dist_min)
        self.setting_dist_max = QtWidgets.QSpinBox()
        self.setting_dist_max.setRange(50, 300)
        self.setting_dist_max.setValue(120)
        dist_layout.addWidget(QtWidgets.QLabel('最大'))
        dist_layout.addWidget(self.setting_dist_max)
        dist_layout.addWidget(QtWidgets.QLabel('cm'))
        dist_layout.addStretch()
        gate_form.addRow('有效距离:', self._row_with_hint(
            dist_w, '人站得太近或太远都不检测，正常范围10~120cm'))

        self.setting_gate_delay = QtWidgets.QDoubleSpinBox()
        self.setting_gate_delay.setRange(1, 30)
        self.setting_gate_delay.setValue(3)
        self.setting_gate_delay.setSuffix(' 秒')
        gate_form.addRow('开门延时:', self._row_with_hint(
            self.setting_gate_delay, '识别成功后道闸保持打开的时间，到时间自动关闭'))

        self.setting_auto_interval = QtWidgets.QSpinBox()
        self.setting_auto_interval.setRange(1, 30)
        self.setting_auto_interval.setValue(4)
        self.setting_auto_interval.setSuffix(' 秒')
        gate_form.addRow('检测间隔:', self._row_with_hint(
            self.setting_auto_interval, '自动运行模式下两次识别之间的等待间隔'))
        layout.addWidget(gate_card)

        # ===== 安全设置 =====
        layout.addWidget(self._section_title('安全策略'))
        sec_card = self._make_card()
        sec_form = QtWidgets.QFormLayout(sec_card)
        sec_form.setSpacing(8)

        self.setting_retry_limit = QtWidgets.QSpinBox()
        self.setting_retry_limit.setRange(1, 10)
        self.setting_retry_limit.setValue(5)
        sec_form.addRow('重试上限:', self._row_with_hint(
            self.setting_retry_limit, '连续识别失败超过此次数后自动锁定系统'))

        self.setting_lockout_duration = QtWidgets.QSpinBox()
        self.setting_lockout_duration.setRange(5, 300)
        self.setting_lockout_duration.setValue(5)
        self.setting_lockout_duration.setSuffix(' 秒')
        sec_form.addRow('锁定时长:', self._row_with_hint(
            self.setting_lockout_duration, '锁定期间拒绝所有识别请求，防止暴力破解'))

        self.setting_stranger_snapshot = QtWidgets.QCheckBox('自动抓拍陌生人与识别失败者')
        self.setting_stranger_snapshot.setChecked(True)
        sec_form.addRow('陌生人抓拍:', self.setting_stranger_snapshot)
        layout.addWidget(sec_card)

        # ===== 硬件状态 =====
        layout.addWidget(self._section_title('硬件状态'))
        hw_card = self._make_card()
        hw_form = QtWidgets.QFormLayout(hw_card)
        hw_form.setSpacing(6)
        self.hw_gate_label = QtWidgets.QLabel('--')
        hw_form.addRow('道闸:', self.hw_gate_label)
        self.hw_temp_label = QtWidgets.QLabel('--')
        hw_form.addRow('测温传感器:', self.hw_temp_label)
        self.hw_dist_label = QtWidgets.QLabel('--')
        hw_form.addRow('超声波测距:', self.hw_dist_label)
        layout.addWidget(hw_card)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # 底部固定按钮栏
        btn_bar = QtWidgets.QHBoxLayout()
        btn_bar.setContentsMargins(16, 8, 16, 8)
        self.btn_save_settings = QtWidgets.QPushButton('保存设置')
        self.btn_save_settings.setMinimumHeight(32)
        self.btn_save_settings.clicked.connect(self._on_save_settings)
        self.btn_reset_settings = QtWidgets.QPushButton('恢复默认')
        self.btn_reset_settings.clicked.connect(self._on_reset_settings)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_reset_settings)
        btn_bar.addWidget(self.btn_save_settings)
        outer.addLayout(btn_bar)

        self.tabs.addTab(tab, '系统设置')

    def _section_title(self, text):
        """分组标题"""
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'color: #89b4fa; font-size: 16px; font-weight: bold; '
            'border: none; margin-top: 8px;')
        return lbl

    def _make_card(self):
        """创建设置卡片容器"""
        card = QtWidgets.QFrame()
        card.setStyleSheet(
            'QFrame { background: #242438; border: 1px solid #45475a; '
            'border-radius: 8px; padding: 12px; }')
        return card

    def _row_with_hint(self, widget, hint):
        """将控件和提示文字放在一起"""
        w = QtWidgets.QWidget()
        w.setStyleSheet('border: none; background: transparent;')
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(widget)
        hint_lbl = QtWidgets.QLabel(hint)
        hint_lbl.setStyleSheet(
            'color: #a6adc8; font-size: 14px; border: none; background: transparent;')
        hint_lbl.setWordWrap(True)
        v.addWidget(hint_lbl)
        return w

    # ---- 定时器 ----

    def _init_timer(self):
        self.timer = QTimer()
        self.timer.start(1000)
        self.timer.timeout.connect(self._on_timer_tick)
        self._tick_count = 0

    def _on_timer_tick(self):
        self.status_label.setText(time.strftime('%Y-%m-%d %H:%M:%S'))
        self._tick_count += 1
        # 每 3 秒自动刷新：通行记录标签页 + 预览页统计数字
        if self._tick_count % 3 == 0:
            if self.tabs.currentIndex() == 1:
                self._on_query_records()
            elif self.tabs.currentIndex() == 0:
                self.update_statistics()

    # ---- 信号连接 ----

    def _connect_actions(self):
        self.act_login.triggered.connect(lambda: self._on_login())
        self.act_register.triggered.connect(lambda: self._on_register())
        self.act_signout.triggered.connect(lambda: self._on_signout())
        self.act_auto_run.triggered.connect(lambda: self._on_auto_run())
        self.act_camera.triggered.connect(lambda: self._on_camera())
        self.act_face_detect.triggered.connect(lambda: self._on_face_detect())
        self.act_enroll.triggered.connect(lambda: self._on_enroll())
        self.act_train.triggered.connect(lambda: self._on_train())

    def _apply_initial_state(self):
        self.act_register.setEnabled(False)
        self.act_signout.setEnabled(False)
        self.act_auto_run.setEnabled(False)

    # ---- 槽函数 ----

    def set_video_pixmap(self, pixmap):
        if pixmap == '' or pixmap is None:
            self.video_label.clear()
            self.video_label.setText('摄像头未启动')
        else:
            self.video_label.setPixmap(pixmap)

    def set_result_text(self, text):
        if text == 'model done':
            self.result_label.setText('')
            self._restore_all_buttons()
        else:
            self.result_label.setText(text if text else '')

    def _restore_all_buttons(self):
        for act in [self.act_camera, self.act_face_detect, self.act_enroll,
                     self.act_train]:
            act.setEnabled(True)
        self.act_register.setEnabled(True)
        self.act_signout.setEnabled(True)

    def _disable_fn_buttons(self):
        for act in [self.act_face_detect, self.act_enroll, self.act_train]:
            act.setEnabled(False)

    def _disable_all(self):
        self._disable_fn_buttons()
        self.act_register.setEnabled(False)
        self.act_signout.setEnabled(False)

    # ---- 管理操作 ----

    def _on_login(self):
        # 由 main.py 中的回调处理
        if hasattr(self, 'login_callback'):
            self.login_callback()

    def _on_register(self):
        if hasattr(self, 'register_callback'):
            self.register_callback()

    def _on_signout(self):
        if hasattr(self, 'signout_callback'):
            self.signout_callback()

    def _on_exit(self):
        reply = QtWidgets.QMessageBox.question(
            self, '退出', '确定退出程序？',
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        if reply == QtWidgets.QMessageBox.Ok:
            QtWidgets.QApplication.instance().quit()

    def _on_auto_run(self):
        if hasattr(self, 'auto_run_callback'):
            self.auto_run_callback()

    def _on_camera(self):
        if hasattr(self, 'camera_callback'):
            self.camera_callback()

    def _on_face_detect(self):
        if hasattr(self, 'face_detect_callback'):
            self.face_detect_callback()

    def _on_enroll(self):
        if hasattr(self, 'enroll_callback'):
            self.enroll_callback()

    def _on_train(self):
        if hasattr(self, 'train_callback'):
            self.train_callback()

    # ---- 通行记录查询 ----

    RESULT_LABELS = {
        'success': '通行成功', 'fail': '识别失败',
        'fever': '体温异常', 'distance': '距离异常'
    }

    def _on_query_records(self):
        """查询通行记录并刷新表格"""
        date_from = self.date_from.date().toString('yyyy-MM-dd') + ' 00:00:00'
        date_to = self.date_to.date().toString('yyyy-MM-dd') + ' 23:59:59'
        keyword = self.filter_keyword.text().strip() or None
        result_filter = self.filter_result.currentText()

        result_map = {'通行成功': 'success', '识别失败': 'fail',
                      '体温异常': 'fever', '距离异常': 'distance'}
        result = result_map.get(result_filter)

        # 查询总量（用于统计和分页）
        all_records = self.db.query_records(
            date_from=date_from, date_to=date_to,
            username=keyword, result=result, limit=5000)

        self._update_stats(all_records)

        # 分页
        total = len(all_records)
        start = self._page * self._page_size
        page_records = all_records[start:start + self._page_size]

        self.records_table.setRowCount(len(page_records))
        for i, r in enumerate(page_records):
            # 时间
            ts = r.get('timestamp', '')
            if len(ts) > 16:
                ts = ts[:16]
            self.records_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(ts))
            # 姓名
            self.records_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(r.get('name', '-')))
            # 账号
            self.records_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(r.get('username', '-')))
            # 结果（中文 + 颜色）
            result_en = r.get('result', '')
            result_cn = self.RESULT_LABELS.get(result_en, result_en)
            item = QtWidgets.QTableWidgetItem(result_cn)
            colors = {'success': '#a6e3a1', 'fail': '#f38ba8',
                      'fever': '#fab387', 'distance': '#fab387'}
            item.setForeground(QtGui.QColor(colors.get(result_en, '#ccc')))
            self.records_table.setItem(i, 3, item)
            # 体温
            temp = r.get('temperature')
            self.records_table.setItem(
                i, 4, QtWidgets.QTableWidgetItem(
                    f'{temp:.1f}°C' if temp else '-'))
            # 置信度
            conf = r.get('confidence', 0)
            item_conf = QtWidgets.QTableWidgetItem(f'{conf:.0f}')
            if conf < 70:
                item_conf.setForeground(QtGui.QColor('#a6e3a1'))
            else:
                item_conf.setForeground(QtGui.QColor('#f38ba8'))
            self.records_table.setItem(i, 5, item_conf)
            # 编号（隐藏）
            self.records_table.setItem(
                i, 6, QtWidgets.QTableWidgetItem(str(r.get('id', ''))))

        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        self.record_count_label.setText(
            f'共 {total} 条记录（第{start + 1}-{min(start + self._page_size, total)}条）')
        self.page_label.setText(f'第 {self._page + 1}/{total_pages} 页')
        self.btn_prev_page.setEnabled(self._page > 0)
        self.btn_next_page.setEnabled((self._page + 1) * self._page_size < total)

        self.status_label.setText(f'查询完成，当前页 {len(page_records)} 条')

    def _update_stats(self, records):
        """更新统计卡片"""
        today = QtCore.QDate.currentDate().toString('yyyy-MM-dd')
        today_cnt = sum(1 for r in records if (r.get('timestamp') or '').startswith(today))
        success_cnt = sum(1 for r in records if r.get('result') == 'success')
        fail_cnt = sum(1 for r in records if r.get('result') == 'fail')
        fever_cnt = sum(1 for r in records if r.get('result') == 'fever')

        self.card_today.value_label.setText(str(today_cnt))
        self.card_success.value_label.setText(str(success_cnt))
        self.card_fail.value_label.setText(str(fail_cnt))
        self.card_fever.value_label.setText(str(fever_cnt))

    def _on_record_selected(self, index):
        """点击记录行：右侧详情面板显示抓拍图像和信息"""
        row = index.row()
        item_id = self.records_table.item(row, 6)  # 隐藏的编号列
        if item_id is None:
            return
        rid = int(item_id.text())

        # 显示详细信息
        name = self.records_table.item(row, 1).text()
        account = self.records_table.item(row, 2).text()
        result = self.records_table.item(row, 3).text()
        temp = self.records_table.item(row, 4).text()
        conf = self.records_table.item(row, 5).text()
        ts = self.records_table.item(row, 0).text()

        info_lines = [
            f'时间: {ts}',
            f'姓名: {name}',
            f'账号: {account}',
            f'结果: {result}',
            f'体温: {temp}',
            f'置信度: {conf}',
            f'记录ID: #{rid}',
        ]
        self.detail_info.setText('\n'.join(info_lines))

        # 显示抓拍图像
        img_data = self.db.get_record_image(rid)
        if img_data is not None:
            import cv2
            img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            if img is not None:
                h, w, c = img.shape
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                qimg = QtGui.QImage(
                    img_rgb.data, w, h, w * 3, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qimg).scaled(
                    260, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_image.setPixmap(pixmap)
            else:
                self.detail_image.setText('(图像损坏)')
        else:
            self.detail_image.setText('(无抓拍图像)')

    def _on_prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._on_query_records()

    def _on_next_page(self):
        self._page += 1
        self._on_query_records()

    # ---- 系统设置 ----

    def _on_tab_changed(self, index):
        if index == 1:
            self._on_query_records()
        elif index == 2:
            self._load_settings()

    def _load_settings(self):
        """从数据库加载设置到界面"""
        s = self.db.get_all_settings()
        idx = self.setting_detect_method.findText(s.get('detect_method', 'yolov5'))
        if idx >= 0:
            self.setting_detect_method.setCurrentIndex(idx)
        idx = self.setting_model_name.findText(s.get('model_name', 'yolov5s'))
        if idx >= 0:
            self.setting_model_name.setCurrentIndex(idx)
        self.setting_conf_threshold.setValue(float(s.get('confidence_threshold', 0.5)))
        self.setting_recog_threshold.setValue(float(s.get('recognition_threshold', 70)))
        self.setting_temp_limit.setValue(float(s.get('temp_limit', 37.2)))
        self.setting_dist_min.setValue(int(s.get('dist_min', 10)))
        self.setting_dist_max.setValue(int(s.get('dist_max', 120)))
        self.setting_gate_delay.setValue(float(s.get('gate_delay', 3)))
        self.setting_auto_interval.setValue(int(s.get('auto_interval', 4)))
        self.setting_retry_limit.setValue(int(s.get('retry_limit', 3)))
        self.setting_lockout_duration.setValue(int(s.get('lockout_duration', 30)))
        self.setting_stranger_snapshot.setChecked(
            s.get('stranger_snapshot', 'true').lower() == 'true')
        self._update_model_status()
        self._update_hardware_status()

    def _update_model_status(self):
        """更新模型状态卡片"""
        import os
        model_path = self.db.get_setting('model_path') or './model/model.xml'
        self.model_path_label.setText(model_path)
        if os.path.exists(model_path):
            self.model_status_label.setText('已训练')
            self.model_status_label.setStyleSheet(
                'color: #a6e3a1; font-weight: bold; border: none;')
        else:
            self.model_status_label.setText('未训练')
            self.model_status_label.setStyleSheet(
                'color: #f38ba8; font-weight: bold; border: none;')
        # 统计已录入人数
        dataset = 'dataset'
        count = 0
        if os.path.isdir(dataset):
            count = len([d for d in os.listdir(dataset)
                         if os.path.isdir(os.path.join(dataset, d))])
        self.model_people_label.setText(f'{count} 人')

    def _update_hardware_status(self):
        """更新硬件状态"""
        if hasattr(self, 'hardware'):
            hw = self.hardware
            if hw.available:
                self.hw_gate_label.setText('已连接')
                self.hw_gate_label.setStyleSheet('color: #a6e3a1; border: none;')
                self.hw_temp_label.setText('已连接 (MLX90614)')
                self.hw_temp_label.setStyleSheet('color: #a6e3a1; border: none;')
                self.hw_dist_label.setText('已连接 (CS100A)')
                self.hw_dist_label.setStyleSheet('color: #a6e3a1; border: none;')
            else:
                self.hw_gate_label.setText('模拟模式')
                self.hw_gate_label.setStyleSheet('color: #fab387; border: none;')
                self.hw_temp_label.setText('模拟模式')
                self.hw_temp_label.setStyleSheet('color: #fab387; border: none;')
                self.hw_dist_label.setText('模拟模式')
                self.hw_dist_label.setStyleSheet('color: #fab387; border: none;')

    def _on_save_settings(self):
        """保存设置到数据库"""
        self.db.set_setting('detect_method', self.setting_detect_method.currentText())
        self.db.set_setting('model_name', self.setting_model_name.currentText())
        self.db.set_setting('confidence_threshold', str(self.setting_conf_threshold.value()))
        self.db.set_setting('recognition_threshold', str(int(self.setting_recog_threshold.value())))
        self.db.set_setting('temp_limit', str(self.setting_temp_limit.value()))
        self.db.set_setting('dist_min', str(self.setting_dist_min.value()))
        self.db.set_setting('dist_max', str(self.setting_dist_max.value()))
        self.db.set_setting('gate_delay', str(self.setting_gate_delay.value()))
        self.db.set_setting('auto_interval', str(self.setting_auto_interval.value()))
        self.db.set_setting('retry_limit', str(self.setting_retry_limit.value()))
        self.db.set_setting('lockout_duration', str(self.setting_lockout_duration.value()))
        self.db.set_setting('stranger_snapshot',
                            'true' if self.setting_stranger_snapshot.isChecked() else 'false')
        QtWidgets.QMessageBox.information(self, '提示',
                                          '设置已保存，部分设置在下次启动自动运行时生效。')

    def _on_reset_settings(self):
        """恢复默认设置"""
        reply = QtWidgets.QMessageBox.question(
            self, '确认', '恢复所有设置为默认值？',
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        if reply != QtWidgets.QMessageBox.Ok:
            return
        defaults = {
            'detect_method': 'yolov5', 'model_name': 'yolov5s',
            'confidence_threshold': '0.5', 'recognition_threshold': '70',
            'temp_limit': '37.2', 'dist_min': '10', 'dist_max': '120',
            'gate_delay': '3', 'auto_interval': '4', 'retry_limit': '5',
            'lockout_duration': '5', 'stranger_snapshot': 'true',
        }
        for k, v in defaults.items():
            self.db.set_setting(k, v)
        self._load_settings()
        QtWidgets.QMessageBox.information(self, '提示', '已恢复默认设置')

    # ---- 更新统计 ----

    def update_statistics(self):
        stats = self.db.get_statistics()
        self.stat_total.setText(f"总通行: {stats['total']}")
        self.stat_today.setText(f"今日: {stats['today']}")
        self.stat_success.setText(f"成功: {stats['success']}")

    def set_user_label(self, text):
        self.user_label.setText(text)

    def set_backend_label(self, text):
        self.backend_label.setText(text)

    def update_fps(self, fps):
        self.fps_label.setText(f'FPS: {fps:.1f}')
