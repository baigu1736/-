import tkinter as tk
from tkinter import scrolledtext, messagebox, Frame, Label, Entry, Spinbox, IntVar, DoubleVar, Listbox, Button, filedialog
import pyautogui
import cv2
import numpy as np
from pynput import keyboard
import threading
import time
import json
import os
import sys
from PIL import Image, ImageGrab
import pyperclip
import colorsys

class MouseKeyboardAutomation:
    def __init__(self, root):
        self.root = root
        self.root.title("键鼠自动化工具 v1.8-deepseek制作")  # 更新版本号
        self.root.geometry("1600x1200")
        
        # 设置全局字体
        self.font = ("微软雅黑", 10)
        self.bold_font = ("微软雅黑", 10, "bold")
        
        # 创建主框架
        main_frame = Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建可调节左右区域的分隔条
        self.paned_window = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # 创建左右两个框架
        left_frame = Frame(self.paned_window)
        self.paned_window.add(left_frame, stretch="always")
        
        # 右侧容器
        right_container = Frame(self.paned_window)
        self.paned_window.add(right_container, stretch="always")
        
        # 设置初始分割比例
        self.initial_sash_position_set = False

        # 创建右侧滚动条
        scrollbar = tk.Scrollbar(right_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建带滚动条的Canvas
        canvas = tk.Canvas(right_container, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 在Canvas上创建框架
        right_frame = Frame(canvas)
        self.right_frame_id = canvas.create_window((0, 0), window=right_frame, anchor=tk.NW)
        
        # 配置Canvas滚动
        right_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.right_frame_id, width=e.width))
        
        # 鼠标滚轮支持
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # 绑定右侧容器的 <Configure> 事件，限制宽度
        right_container.bind("<Configure>", self.limit_right_frame_width)

        # 创建左侧组件
        self.create_left_widgets(left_frame)

        # 创建右侧面板
        self.create_right_panel(right_frame)

        # 启动键盘监听
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.daemon = True
        self.listener.start()

        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("就绪 | 按 = 键获取鼠标坐标 | Ctrl+C复制 | Ctrl+V粘贴")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, 
                             anchor=tk.W, font=self.font, bg="#f0f0f0")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 设置初始坐标
        self.update_coord()
        
        # 停止标志
        self.stop_execution = False
        
        # 图片识别精度
        self.image_confidence = 0.8
        # 保存最近识别的图片位置
        self.last_image_position = None
        
        # 在窗口显示后设置初始分割位置
        self.root.after(100, self.set_initial_sash_position)

        # 存储原始命令（用于缩进显示）
        self.raw_commands = []
        # 缩进级别
        self.indent_levels = []
        
        # 命令剪贴板
        self.command_clipboard = []
        # 保存滚动位置
        self.scroll_position = (0.0, 0.0)
        # 窗口最小化状态
        self.window_minimized = False
        
        # 绑定快捷键
        self.root.bind("<Control-c>", self.copy_commands)
        self.root.bind("<Control-v>", self.paste_commands)

    def limit_right_frame_width(self, event):
        """限制右侧框架的最大宽度为 550px"""
        max_width = 550
        if event.width > max_width:
            self.paned_window.sash_place(0, self.paned_window.winfo_width() - max_width, 0)

    def set_initial_sash_position(self):
        """设置初始分割位置"""
        if not self.initial_sash_position_set:
            # 获取主框架宽度
            main_width = self.paned_window.winfo_width()
            if main_width > 100:
                # 设置左侧宽度为主框架宽度的65%
                self.paned_window.sash_place(0, int(main_width * 0.85), 0)
                self.initial_sash_position_set = True

    def create_left_widgets(self, parent):
        """创建左侧命令编辑区域"""
        # 命令列表框架
        list_frame = Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # 命令列表标签
        tk.Label(list_frame, text="命令列表 (双击编辑，拖动改变顺序):", 
                font=self.bold_font).pack(anchor=tk.W, pady=(0, 5))

        # 创建命令列表和滚动条
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 添加行号框架 - 修复行号偏移问题
        line_frame = Frame(list_frame)
        line_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # 使用固定高度的Listbox显示行号
        self.line_number_box = Listbox(
            line_frame, 
            width=4, 
            height=25,  # 增加高度以显示更多行
            font=self.font,
            bd=0,
            selectmode=tk.NONE,  # 不可选择
            activestyle="none",
            bg="#f0f0f0",
            highlightthickness=0
        )
        self.line_number_box.pack(side=tk.LEFT, fill=tk.Y)

        # 增加命令列表高度为25行（增加约50px）
        # 修改为支持多选
        self.command_list = Listbox(
            list_frame,
            width=70,
            height=25,  # 增加高度以显示更多行
            yscrollcommand=lambda *args: self.on_scroll(*args, scrollbar),
            selectmode=tk.EXTENDED,  # 支持多选
            activestyle="none",
            font=self.font,
            bd=1,
            relief=tk.SOLID
        )
        self.command_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.command_list.yview)

        # 绑定事件
        self.command_list.bind("<Double-Button-1>", self.edit_command)
        self.command_list.bind("<ButtonPress-1>", self.on_list_press)
        self.command_list.bind("<B1-Motion>", self.on_list_motion)
        self.command_list.bind("<ButtonRelease-1>", self.on_list_release)
        self.command_list.bind("<<ListboxSelect>>", self.update_line_numbers)
        self.command_list.bind("<Configure>", self.update_line_numbers)

        # 命令输入框架
        input_frame = Frame(parent)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(input_frame, text="添加命令:", font=self.font).pack(side=tk.LEFT, padx=(0, 5))

        self.command_entry = Entry(input_frame, width=40, font=self.font, bd=1, relief=tk.SOLID)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.command_entry.bind("<Return>", lambda e: self.add_command())

        self.add_btn = Button(input_frame, text="添加", command=self.add_command, 
                             width=8, font=self.font, bg="#4CAF50", fg="white")
        self.add_btn.pack(side=tk.LEFT, padx=5)

        # 按钮框架
        btn_frame = Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        # 运行按钮
        run_btn = tk.Button(btn_frame, text="执行命令", command=self.execute_commands, 
                          width=10, font=self.font, bg="#2196F3", fg="white")
        run_btn.pack(side=tk.LEFT, padx=5)
        
        # 停止按钮
        stop_btn = tk.Button(btn_frame, text="停止执行", command=self.stop_execution_command, 
                           width=10, font=self.font, bg="#FF5722", fg="white")
        stop_btn.pack(side=tk.LEFT, padx=5)

        # 插入坐标按钮
        insert_coord_btn = tk.Button(btn_frame, text="插入坐标", command=self.insert_current_coord, 
                                  width=10, font=self.font, bg="#9C27B0", fg="white")
        insert_coord_btn.pack(side=tk.LEFT, padx=5)

        # 重复执行设置
        repeat_frame = Frame(btn_frame)
        repeat_frame.pack(side=tk.LEFT, padx=10)

        tk.Label(repeat_frame, text="重复次数:", font=self.font).pack(side=tk.LEFT)
        self.repeat_count = IntVar(value=1)
        repeat_spin = Spinbox(repeat_frame, from_=1, to=100, width=5, 
                             textvariable=self.repeat_count, font=self.font)
        repeat_spin.pack(side=tk.LEFT, padx=5)

        tk.Label(repeat_frame, text="延迟(秒):", font=self.font).pack(side=tk.LEFT)
        self.repeat_delay = DoubleVar(value=0.5)
        delay_spin = Spinbox(repeat_frame, from_=0.1, to=10, increment=0.1, width=5,
                             textvariable=self.repeat_delay, format="%.1f", font=self.font)
        delay_spin.pack(side=tk.LEFT, padx=5)

    def create_right_panel(self, parent):
        """创建右侧面板"""
        # 坐标编辑区域
        coord_frame = tk.LabelFrame(parent, text="坐标设置", padx=10, pady=10, 
                                  font=self.bold_font)
        coord_frame.pack(fill=tk.X, padx=5, pady=10)

        tk.Label(coord_frame, text="X坐标:", font=self.font).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.x_var = IntVar(value=0)
        x_entry = Entry(coord_frame, textvariable=self.x_var, width=10, font=self.font, bd=1, relief=tk.SOLID)
        x_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(coord_frame, text="Y坐标:", font=self.font).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.y_var = IntVar(value=0)
        y_entry = Entry(coord_frame, textvariable=self.y_var, width=10, font=self.font, bd=1, relief=tk.SOLID)
        y_entry.grid(row=1, column=1, padx=5, pady=5)

        # 移动速度设置
        tk.Label(coord_frame, text="移动速度:", font=self.font).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.move_speed = DoubleVar(value=0.1)
        move_speed_spin = Spinbox(coord_frame, from_=0.01, to=1.0, increment=0.05, width=5,
                                  textvariable=self.move_speed, format="%.2f", font=self.font)
        move_speed_spin.grid(row=2, column=1, padx=5, pady=5)

        # 拖动速度设置
        tk.Label(coord_frame, text="拖动速度:", font=self.font).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.drag_speed = DoubleVar(value=0.3)
        drag_speed_spin = Spinbox(coord_frame, from_=0.01, to=1.0, increment=0.05, width=5,
                                  textvariable=self.drag_speed, format="%.2f", font=self.font)
        drag_speed_spin.grid(row=3, column=1, padx=5, pady=5)

        # 更新坐标按钮
        update_btn = tk.Button(coord_frame, text="更新坐标", command=self.update_coord, 
                             width=10, font=self.font, bg="#3F51B5", fg="white")
        update_btn.grid(row=4, column=0, columnspan=2, pady=10)
        
        # 图片识别设置框架
        image_frame = tk.LabelFrame(parent, text="图片识别设置", padx=10, pady=10, 
                                  font=self.bold_font)
        image_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # 图片识别精度设置
        tk.Label(image_frame, text="识别精度(0.1-1.0):", font=self.font).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.image_confidence_var = DoubleVar(value=0.8)
        confidence_spin = Spinbox(image_frame, from_=0.1, to=1.0, increment=0.05, width=5,
                                 textvariable=self.image_confidence_var, format="%.2f", font=self.font)
        confidence_spin.grid(row=0, column=1, padx=5, pady=5)
        
        # 识别超时设置
        tk.Label(image_frame, text="识别超时(秒):", font=self.font).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.image_timeout_var = DoubleVar(value=1.0)
        timeout_spin = Spinbox(image_frame, from_=0.1, to=60.0, increment=0.5, width=5,
                              textvariable=self.image_timeout_var, format="%.1f", font=self.font)
        timeout_spin.grid(row=1, column=1, padx=5, pady=5)
        
        # 图片识别按钮
        img_btn_frame = Frame(image_frame)
        img_btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        # 选择图片按钮
        select_img_btn = tk.Button(img_btn_frame, text="选择图片", command=self.select_image, 
                                 width=10, font=self.font, bg="#2196F3", fg="white")
        select_img_btn.pack(side=tk.LEFT, padx=5)
        
        # 测试识别按钮
        test_img_btn = tk.Button(img_btn_frame, text="测试识别", command=self.test_image_recognition, 
                               width=10, font=self.font, bg="#4CAF50", fg="white")
        test_img_btn.pack(side=tk.LEFT, padx=5)
        
        # 当前选择的图片
        self.selected_image_path = ""
        self.image_path_var = tk.StringVar()
        self.image_path_var.set("未选择图片")
        img_label = tk.Label(image_frame, textvariable=self.image_path_var, font=self.font, 
                           fg="#666666", wraplength=280, justify=tk.LEFT)
        img_label.grid(row=3, column=0, columnspan=2, padx=5, pady=(0, 5))

        # 命令管理框架
        manage_frame = tk.LabelFrame(parent, text="命令管理", padx=10, pady=10, font=self.bold_font)
        manage_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # 管理按钮
        clear_btn = tk.Button(manage_frame, text="清除命令", command=self.clear_commands, 
                           width=12, font=self.font, bg="#FF5722", fg="white")
        clear_btn.grid(row=0, column=0, padx=5, pady=5)
        
        delete_btn = tk.Button(manage_frame, text="删除选中", command=self.delete_selected_command, 
                             width=12, font=self.font, bg="#F44336", fg="white")
        delete_btn.grid(row=0, column=1, padx=5, pady=5)
        
        save_btn = tk.Button(manage_frame, text="保存命令", command=self.save_commands, 
                           width=12, font=self.font, bg="#607D8B", fg="white")
        save_btn.grid(row=1, column=0, padx=5, pady=5)
        
        load_btn = tk.Button(manage_frame, text="加载命令", command=self.load_commands, 
                           width=12, font=self.font, bg="#607D8B", fg="white")
        load_btn.grid(row=1, column=1, padx=5, pady=5)

        # 快捷命令面板
        tk.Label(parent, text="快捷命令", font=("Arial", 10, "bold")).pack(pady=(10, 5))

        # 创建命令按钮（添加注释快捷命令）
        shortcuts = [
            ("移动鼠标", "move $x $y", "#2196F3"),
            
            ("左键点击", "click left", "#4CAF50"),
            ("右键点击", "click right", "#4CAF50"),
            ("双击", "doubleclick", "#4CAF50"),
            ("拖动", "drag $x $y", "#FF9800"),
            
            ("按键", "key ", "#9C27B0"),
            ("Ctrl+C", "key ctrl c", "#673AB7"),
            ("Ctrl+V", "key ctrl v", "#673AB7"),
            ("Alt+F4", "key alt f4", "#F44336"),
            ("回车", "key enter", "#673AB7"),
            ("滚轮向上", "scroll 10", "#00BCD4"),
            ("滚轮向下", "scroll -10", "#00BCD4"),
            ("等待1秒", "sleep 1", "#795548"),
            ("等待0.5秒", "sleep 0.5", "#795548"),
            # 新增图片识别相关快捷命令
            ("图片点击", "imageclick ", "#FF5722"),
            ("等待图片", "imagewait ", "#FF9800"),
            ("如果图片存在", "ifimage ", "#9C27B0"),
            ("如果图片不存在", "ifnotimage ", "#9C27B0"),
            # 新增停止执行命令
            ("停止执行", "stop", "#F44336"),
            ("输入文本", "type ", "#9C27B0"),
            # 新增条件语句块命令
            ("开始条件块", "begin", "#795548"),
            ("结束条件块", "end", "#795548"),
            # 新增完成本次循环命令
            ("完成本次循环", "breakloop", "#795548"),
            # 新增注释命令
            ("添加注释", "# 注释内容", "#607D8B"),
        ]

        # 使用网格布局排列按钮
        grid_frame = Frame(parent)
        grid_frame.pack(fill=tk.X, padx=5)

        row, col = 0, 0
        for text, command, color in shortcuts:
            btn = tk.Button(
                grid_frame,
                text=text,
                width=14,
                font=self.font,
                command=lambda cmd=command: self.add_command_from_shortcut(cmd),
                bg=color,
                fg="white",
                padx=2,
                pady=2
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            col += 1
            if col > 1:
                col = 0
                row += 1

        # 添加更多按钮
        more_btn = tk.Button(
            parent,
            text="更多命令...",
            width=20,
            font=self.font,
            command=self.show_command_reference,
            bg="#607D8B",
            fg="white"
        )
        more_btn.pack(pady=10)

    def on_scroll(self, first, last, scrollbar):
        """处理滚动事件"""
        scrollbar.set(first, last)
        # 同步行号框的滚动位置
        self.line_number_box.yview_moveto(first)
        self.update_line_numbers()

    def show_command_reference(self):
        """显示命令参考（添加注释说明）"""
        reference = """
命令参考:
- move x y          : 移动鼠标到指定位置
- fastmove x y      : 快速移动鼠标到指定位置
- click [left/right]: 点击鼠标（默认左键）
- doubleclick       : 双击鼠标
- drag x y          : 拖动鼠标到指定位置
- type text         : 输入文本（使用复制粘贴方式）
- key keyname       : 按键（支持组合键如key ctrl c）
- scroll amount     : 滚轮滚动（正数向上，负数向下）
- sleep seconds     : 等待指定秒数
- imageclick path [confidence] : 识别图片并点击中心位置
- imagewait path [timeout] [confidence] : 等待图片出现
- ifimage path [confidence] : 如果图片存在则执行代码块
- ifnotimage path [confidence] : 如果图片不存在则执行代码块
- begin             : 开始条件代码块
- end               : 结束条件代码块
- breakloop         : 完成本次循环（跳过当前循环剩余命令）
- stop              : 停止命令执行（配合if语句使用）

注释功能:
- # 这是一行注释
- // 这也是一行注释
- 注释行不会被执行
- 可以在命令后添加注释: move 100 100 // 移动到指定位置
- 输入文本命令中的 # 和 // 不会被当作注释

条件语句结构:
ifimage "logo.png"
begin
    move 100 100
    click
end
else
begin
    move 200 200
    click
end

循环控制:
- breakloop: 跳过当前循环剩余命令，直接进入下一次循环
- stop: 完全停止命令执行

特殊变量:
- $x : 当前X坐标
- $y : 当前Y坐标
- $lastimg : 最近识别的图片位置 (x,y)

提示:
- 使用begin和end定义条件代码块
- 支持嵌套条件语句
- else分支必须紧跟在条件代码块后
- 在右侧设置移动速度（秒），值越小移动越快
- 拖动操作使用单独的拖动速度
- 使用"快速移动"命令忽略速度设置，直接跳转
- 图片识别需要提供图片路径，可以使用相对路径或绝对路径
- 图片识别精度范围0.1-1.0，值越高匹配越严格
- 使用$lastimg变量可以获取最近识别的图片位置

全部代码由deepseek生成
"""
        messagebox.showinfo("命令参考", reference)

    def add_command_from_shortcut(self, command):
        """从快捷命令添加命令"""
        # 替换特殊变量
        cmd = command.replace("$x", str(self.x_var.get()))
        cmd = cmd.replace("$y", str(self.y_var.get()))
        
        # 替换图片路径
        if command.strip().startswith("image") and self.selected_image_path:
            cmd = cmd.replace(" ", f" \"{self.selected_image_path}\" ", 1)
        elif command.strip().startswith("ifimage") and self.selected_image_path:
            cmd = cmd.replace(" ", f" \"{self.selected_image_path}\" ", 1)
        elif command.strip().startswith("ifnotimage") and self.selected_image_path:
            cmd = cmd.replace(" ", f" \"{self.selected_image_path}\" ", 1)

        self.command_entry.delete(0, tk.END)
        self.command_entry.insert(0, cmd)
        self.add_command()

    def add_command(self):
        """添加新命令到列表"""
        cmd = self.command_entry.get().strip()
        if cmd:
            # 保存当前滚动位置
            self.save_scroll_position()
            
            # 获取插入位置
            insert_pos = self.get_insert_position()
            
            # 添加到原始命令列表
            if insert_pos >= len(self.raw_commands):
                self.raw_commands.append(cmd)
            else:
                self.raw_commands.insert(insert_pos, cmd)
            
            # 重新计算缩进并刷新显示
            self.calculate_indent_levels()
            self.refresh_command_list_display()
            
            # 滚动到新命令位置
            self.command_list.see(insert_pos)
            
            self.command_entry.delete(0, tk.END)
            self.status_var.set(f"已添加命令: {cmd}")

    def get_insert_position(self):
        """根据设置确定插入位置"""
        selection = self.command_list.curselection()
        if selection:
            # 获取最大的选中索引
            max_index = max(selection)
            return max_index + 1
        else:
            return len(self.raw_commands)  # 默认到末尾

    def save_scroll_position(self):
        """保存当前滚动位置"""
        self.scroll_position = self.command_list.yview()

    def restore_scroll_position(self):
        """恢复保存的滚动位置"""
        self.command_list.yview_moveto(self.scroll_position[0])
        self.line_number_box.yview_moveto(self.scroll_position[0])

    def copy_commands(self, event=None):
        """复制选中的命令"""
        selection = self.command_list.curselection()
        if selection:
            self.command_clipboard = [self.raw_commands[i] for i in selection]
            self.status_var.set(f"已复制 {len(selection)} 条命令")
        else:
            self.status_var.set("请先选择要复制的命令")
        return "break"  # 阻止默认事件处理

    def paste_commands(self, event=None):
        """粘贴命令到列表"""
        if not self.command_clipboard:
            self.status_var.set("剪贴板中没有命令")
            return
            
        # 保存当前滚动位置
        self.save_scroll_position()
        
        # 获取插入位置
        insert_pos = self.get_insert_position()
        
        # 插入命令
        for i, cmd in enumerate(self.command_clipboard):
            self.raw_commands.insert(insert_pos + i, cmd)
        
        # 重新计算缩进并刷新显示
        self.calculate_indent_levels()
        self.refresh_command_list_display()
        
        # 滚动到粘贴位置
        self.command_list.see(insert_pos)
        
        self.status_var.set(f"已粘贴 {len(self.command_clipboard)} 条命令")
        return "break"  # 阻止默认事件处理

    def edit_command(self, event):
        """编辑选中的命令"""
        selection = self.command_list.curselection()
        if selection:
            index = selection[0]
            # 获取原始命令（不带缩进）
            current_cmd = self.raw_commands[index]

            # 创建编辑对话框
            edit_dialog = tk.Toplevel(self.root)
            edit_dialog.title("编辑命令")
            edit_dialog.transient(self.root)
            edit_dialog.grab_set()

            # 设置对话框位置和大小
            dialog_width = 400
            dialog_height = 150
            x = self.root.winfo_x() + (self.root.winfo_width() - dialog_width) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - dialog_height) // 2
            edit_dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

            # 创建编辑框
            tk.Label(edit_dialog, text="编辑命令:", font=self.font).pack(pady=(10, 0))
            edit_entry = tk.Entry(edit_dialog, width=50, font=self.font)
            edit_entry.pack(padx=10, pady=10)
            edit_entry.insert(0, current_cmd)
            edit_entry.focus_set()

            # 按钮框架
            btn_frame = Frame(edit_dialog)
            btn_frame.pack(pady=(0, 10))

            # 保存按钮
            def save_edit():
                new_cmd = edit_entry.get().strip()
                if new_cmd:
                    # 更新原始命令列表
                    self.raw_commands[index] = new_cmd
                    # 重新计算缩进并刷新显示
                    self.calculate_indent_levels()
                    self.refresh_command_list_display()
                    self.status_var.set(f"命令已更新: {new_cmd}")
                    edit_dialog.destroy()

            save_btn = tk.Button(btn_frame, text="确定", command=save_edit, width=8, 
                         font=self.font, bg="#4CAF50", fg="white")
            save_btn.pack(side=tk.LEFT, padx=10)
            
            # 取消按钮
            cancel_btn = tk.Button(btn_frame, text="取消", command=edit_dialog.destroy, width=8, 
                         font=self.font, bg="#F44336", fg="white")
            cancel_btn.pack(side=tk.LEFT, padx=10)

    def on_list_press(self, event):
        """处理列表按下事件"""
        self.drag_start_index = self.command_list.nearest(event.y)
        self.drag_data = {"y": event.y, "item": None}

    def on_list_motion(self, event):
        """处理列表拖动事件"""
        if self.drag_start_index is not None:
            # 计算移动距离
            dy = event.y - self.drag_data["y"]
            if abs(dy) > 5:  # 拖动阈值
                self.drag_data["y"] = event.y
                # 显示拖动效果
                if self.drag_data["item"] is None:
                    self.drag_data["item"] = self.raw_commands[self.drag_start_index]

    def on_list_release(self, event):
        """处理列表释放事件"""
        if self.drag_start_index is not None and self.drag_data["item"] is not None:
            end_index = self.command_list.nearest(event.y)

            if end_index != self.drag_start_index:
                # 移动原始命令列表中的项目
                item = self.raw_commands[self.drag_start_index]
                del self.raw_commands[self.drag_start_index]
                self.raw_commands.insert(end_index, item)
                
                # 重新计算缩进并刷新显示
                self.calculate_indent_levels()
                self.refresh_command_list_display()
                
                self.command_list.selection_set(end_index)
                self.status_var.set(f"命令已移动到位置 {end_index + 1}")

        # 重置拖动状态
        self.drag_start_index = None
        self.drag_data = {"y": 0, "item": None}

    def insert_current_coord(self):
        """插入当前鼠标坐标到输入框"""
        x, y = pyautogui.position()
        pos_str = f"{x} {y}"
        self.command_entry.insert(tk.INSERT, pos_str)
        self.command_entry.focus_set()
        self.status_var.set(f"已插入坐标: {x}, {y}")
        
    def update_coord(self):
        """更新当前坐标值"""
        x, y = pyautogui.position()
        self.x_var.set(x)
        self.y_var.set(y)
        self.status_var.set(f"坐标已更新: X={x}, Y={y}")

    def on_key_press(self, key):
        """处理键盘按键事件"""
        try:
            if key == keyboard.KeyCode.from_char('='):
                self.update_coord()
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
            
    def select_image(self):
        """选择用于识别的图片"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")],
            title="选择识别图片"
        )
        if file_path:
            self.selected_image_path = file_path
            self.image_path_var.set(os.path.basename(file_path))
            self.status_var.set(f"已选择图片: {file_path}")
            
    def test_image_recognition(self):
        """测试图片识别功能"""
        if not self.selected_image_path or not os.path.exists(self.selected_image_path):
            messagebox.showwarning("警告", "请先选择有效的图片文件！")
            return
            
        confidence = self.image_confidence_var.get()
        
        # 在新线程中执行识别
        threading.Thread(target=self._test_image_recognition_thread, args=(confidence,), daemon=True).start()
        
    def _test_image_recognition_thread(self, confidence):
        """测试图片识别的线程函数"""
        try:
            self.status_var.set(f"正在识别图片: {os.path.basename(self.selected_image_path)}...")
            
            # 查找图片
            location = pyautogui.locateOnScreen(self.selected_image_path, confidence=confidence)
            
            if location:
                # 计算中心点
                center_x = location.left + location.width // 2
                center_y = location.top + location.height // 2
                
                # 移动鼠标到识别位置
                pyautogui.moveTo(center_x, center_y, duration=0.5)
                
                # 高亮显示识别区域
                self.highlight_area(location)
                
                self.status_var.set(f"识别成功! 位置: ({center_x}, {center_y})")
                messagebox.showinfo("测试成功", f"图片识别成功!\n位置: ({center_x}, {center_y})\n大小: {location.width}x{location.height}")
                self.last_image_position = (center_x, center_y)
            else:
                self.status_var.set("图片未找到")
                messagebox.showinfo("测试结果", "未找到匹配的图片")
                
        except Exception as e:
            self.status_var.set(f"识别错误: {str(e)}")
            messagebox.showerror("错误", f"图片识别失败:\n{str(e)}")
            
    def highlight_area(self, location):
        """高亮显示识别区域"""
        # 创建半透明覆盖层
        overlay = tk.Toplevel(self.root)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-topmost", True)
        overlay.configure(bg='yellow')
        
        # 创建透明窗口用于显示高亮框
        highlight = tk.Toplevel(overlay)
        highlight.attributes("-transparentcolor", "white")
        highlight.attributes("-topmost", True)
        highlight.geometry(f"{location.width}x{location.height}+{location.left}+{location.top}")
        highlight.overrideredirect(True)
        
        # 绘制红色边框
        canvas = tk.Canvas(highlight, bg='white', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_rectangle(0, 0, location.width-1, location.height-1, outline='red', width=3)
        
        # 3秒后自动关闭
        highlight.after(3000, highlight.destroy)
        overlay.after(3000, overlay.destroy)
        
    def find_image_on_screen(self, image_path, confidence=0.8, timeout=0):
        """在屏幕上查找图片位置"""
        start_time = time.time()
        location = None
        
        # 修改：当timeout为0时表示无限等待
        while not location and (timeout == 0 or (time.time() - start_time < timeout)):
            try:
                location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            except pyautogui.ImageNotFoundException:
                pass
            
            # 如果设置了超时且未找到，等待一小段时间再试
            if not location:
                time.sleep(0.5)
                # 检查停止标志
                if self.stop_execution:
                    return None
                
        return location

    def execute_commands(self):
        """执行所有命令"""
        if len(self.raw_commands) == 0:
            messagebox.showwarning("警告", "命令列表为空！")
            return
            
        # 重置停止标志
        self.stop_execution = False
        
        # 最小化窗口
        self.root.iconify()
        self.window_minimized = True

        # 在新线程中执行命令
        threading.Thread(target=self._run_commands, daemon=True).start()

    def _run_commands(self):
        """实际执行命令的内部方法（添加注释处理）"""
        try:
            repeat_count = self.repeat_count.get()
            repeat_delay = self.repeat_delay.get()
            move_speed = self.move_speed.get()
            drag_speed = self.drag_speed.get()
            default_confidence = self.image_confidence_var.get()
            default_timeout = self.image_timeout_var.get()

            commands = list(self.raw_commands)  # 使用原始命令列表
            index = 0
            skip_next = False  # 用于条件判断时跳过下一行命令
            skip_block = False  # 是否跳过当前代码块
            in_else_block = False  # 是否在else分支中
            block_depth = 0  # 代码块嵌套深度
            condition_stack = []  # 条件状态栈（用于嵌套条件）
            
            for i in range(repeat_count):
                # 检查停止标志
                if self.stop_execution:
                    self.status_var.set("执行已停止")
                    messagebox.showinfo("停止", "命令执行已停止")
                    return
                    
                self.status_var.set(f"开始执行第 {i + 1}/{repeat_count} 次")
                index = 0  # 每次重复时重置索引
                skip_next = False
                skip_block = False
                in_else_block = False
                block_depth = 0
                condition_stack = []
                
                while index < len(commands):
                    # 检查停止标志
                    if self.stop_execution:
                        self.status_var.set("执行已停止")
                        messagebox.showinfo("停止", "命令执行已停止")
                        return
                    
                    cmd = commands[index].strip()
                    index += 1
                    
                    # ==== 新增：处理注释行 ====
                    # 跳过整行注释（以#或//开头），但忽略type命令中的注释符号
                    if cmd.startswith("#") or cmd.startswith("//"):
                        self.status_var.set(f"跳过注释: {cmd}")
                        continue
                    # ========================
                    
                    # 跳过空行
                    if not cmd:
                        continue
                        
                    # 处理条件跳转
                    if skip_next:
                        skip_next = False
                        self.status_var.set(f"跳过命令: {cmd}")
                        continue
                        
                    # 处理代码块跳过
                    if skip_block:
                        # 如果遇到begin，增加嵌套深度
                        if cmd == "begin":
                            block_depth += 1
                        # 如果遇到end，减少嵌套深度
                        elif cmd == "end":
                            if block_depth > 0:  # 确保深度不会变为负数
                                block_depth -= 1
                            if block_depth == 0:
                                skip_block = False
                                in_else_block = False
                        continue
                        
                    # 处理停止命令
                    if cmd == "stop":
                        self.status_var.set("执行已停止")
                        messagebox.showinfo("停止", "执行了停止命令")
                        return

                    # 处理完成本次循环命令
                    if cmd == "breakloop":
                        self.status_var.set("完成本次循环，跳过剩余命令")
                        # 跳出当前循环的剩余命令，进入下一次循环
                        break

                    # 处理begin命令（开始代码块）
                    if cmd == "begin":
                        # 如果有条件状态，推入栈
                        if condition_stack:
                            # 检查是否需要跳过此块
                            if condition_stack[-1] == "skip":
                                skip_block = True
                                block_depth = 1
                            condition_stack.pop()
                        continue
                        
                    # 处理end命令（结束代码块）
                    if cmd == "end":
                        # 结束当前代码块
                        if condition_stack:
                            condition_stack.pop()
                        continue
                        
                    # 处理else命令（否则分支）
                    if cmd == "else":
                        # 切换分支状态
                        in_else_block = True
                        # 如果条件为真，跳过else分支
                        if condition_stack and condition_stack[-1] == "execute":
                            skip_block = True
                            block_depth = 1
                        # 清除条件栈顶部状态
                        if condition_stack:
                            condition_stack.pop()
                        continue

                    self.status_var.set(f"执行: {cmd}")
                    parts = cmd.split()
                    action = parts[0].lower()

                    # 处理特殊变量
                    processed_parts = []
                    for part in parts:
                        if part == "$x":
                            processed_parts.append(str(self.x_var.get()))
                        elif part == "$y":
                            processed_parts.append(str(self.y_var.get()))
                        elif part == "$lastimg" and self.last_image_position:
                            processed_parts.append(f"{self.last_image_position[0]} {self.last_image_position[1]}")
                        else:
                            processed_parts.append(part)

                    # 处理图片识别命令
                    if action == "imageclick":
                        # 解析参数：imageclick "path" [confidence]
                        if len(processed_parts) < 2:
                            self.status_var.set("错误: imageclick需要图片路径")
                            continue
                            
                        # 获取图片路径（可能包含空格）
                        path_part = processed_parts[1]
                        if path_part.startswith('"') and path_part.endswith('"'):
                            image_path = path_part[1:-1]
                        else:
                            image_path = path_part
                            
                        confidence = default_confidence
                        if len(processed_parts) > 2:
                            try:
                                confidence = float(processed_parts[2])
                            except ValueError:
                                pass

                        # 查找图片
                        location = self.find_image_on_screen(image_path, confidence, 0)
                        if location:
                            center_x = location.left + location.width // 2
                            center_y = location.top + location.height // 2
                            pyautogui.moveTo(center_x, center_y, duration=move_speed)
                            pyautogui.click()
                            self.last_image_position = (center_x, center_y)
                            self.status_var.set(f"图片点击成功: ({center_x}, {center_y})")
                        else:
                            self.status_var.set(f"图片未找到: {os.path.basename(image_path)}")
                            continue

                    elif action == "imagewait":
                        # 解析参数：imagewait "path" [timeout] [confidence]
                        if len(processed_parts) < 2:
                            self.status_var.set("错误: imagewait需要图片路径")
                            continue
                            
                        # 获取图片路径
                        path_part = processed_parts[1]
                        if path_part.startswith('"') and path_part.endswith('"'):
                            image_path = path_part[1:-1]
                        else:
                            image_path = path_part
                            
                        # 修改：对于imagewait命令，默认timeout=0表示无限等待
                        timeout = 0  # 设置为0表示无限等待
                        confidence = default_confidence
                        
                        # 解析可选参数
                        if len(processed_parts) > 2:
                            try:
                                timeout = float(processed_parts[2])
                            except ValueError:
                                pass
                                
                        if len(processed_parts) > 3:
                            try:
                                confidence = float(processed_parts[3])
                            except ValueError:
                                pass

                        self.status_var.set(f"等待图片: {os.path.basename(image_path)} " + 
                                    (f"(超时: {timeout}秒)" if timeout > 0 else "(无限等待)"))
                        
                        # 等待图片出现
                        location = self.find_image_on_screen(image_path, confidence, timeout)
                        if location:
                            center_x = location.left + location.width // 2
                            center_y = location.top + location.height // 2
                            self.last_image_position = (center_x, center_y)
                            self.status_var.set(f"图片出现: ({center_x}, {center_y})")
                        else:
                            if timeout > 0:
                                self.status_var.set(f"等待超时: {os.path.basename(image_path)}")
                            continue

                    elif action == "ifimage" or action == "ifnotimage":
                        # 解析参数：ifimage "path" [confidence] [timeout]
                        if len(processed_parts) < 2:
                            self.status_var.set(f"错误: {action}需要图片路径")
                            continue
                            
                        # 获取图片路径
                        path_part = processed_parts[1]
                        if path_part.startswith('"') and path_part.endswith('"'):
                            image_path = path_part[1:-1]
                        else:
                            image_path = path_part
                            
                        confidence = default_confidence
                        timeout = default_timeout  # 默认使用全局超时设置
                        
                        # 解析可选参数
                        if len(processed_parts) > 2:
                            try:
                                confidence = float(processed_parts[2])
                            except ValueError:
                                pass
                                
                        if len(processed_parts) > 3:
                            try:
                                timeout = float(processed_parts[3])
                            except ValueError:
                                pass

                        # 查找图片（带超时）
                        self.status_var.set(f"条件判断: {action} {os.path.basename(image_path)} (超时: {timeout}秒)")
                        location = self.find_image_on_screen(image_path, confidence, timeout)
                        found = location is not None
                        
                        # 根据命令类型设置条件状态
                        if (action == "ifimage" and found) or (action == "ifnotimage" and not found):
                            # 条件为真，执行代码块
                            condition_stack.append("execute")
                            if found:
                                center_x = location.left + location.width // 2
                                center_y = location.top + location.height // 2
                                self.last_image_position = (center_x, center_y)
                                self.status_var.set(f"条件为真: 找到图片 ({center_x}, {center_y})")
                            else:
                                self.status_var.set(f"条件为真: 未找到图片 {image_path} (超时)")
                        else:
                            # 条件为假，跳过代码块
                            condition_stack.append("skip")
                            # 设置跳过下一个代码块
                            skip_block = True
                            block_depth = 0
                            
                            if found:
                                center_x = location.left + location.width // 2
                                center_y = location.top + location.height // 2
                                self.last_image_position = (center_x, center_y)
                                self.status_var.set(f"条件为假: 找到图片 ({center_x}, {center_y})")
                            else:
                                self.status_var.set(f"条件为假: 未找到图片 {image_path} (超时)")

                    # 原有命令处理
                    elif action == "move":
                        x, y = int(processed_parts[1]), int(processed_parts[2])
                        pyautogui.moveTo(x, y, duration=move_speed)

                    elif action == "fastmove":
                        x, y = int(processed_parts[1]), int(processed_parts[2])
                        pyautogui.moveTo(x, y, duration=0.01)

                    elif action == "click":
                        button = processed_parts[1].lower() if len(processed_parts) > 1 else "left"
                        pyautogui.click(button=button)

                    elif action == "doubleclick":
                        pyautogui.doubleClick()

                    elif action == "drag":
                        x, y = int(processed_parts[1]), int(processed_parts[2])
                        pyautogui.dragTo(x, y, duration=drag_speed, button='left')

                    elif action == "type":
                        # 使用复制粘贴方式输入文本
                        # 获取完整的文本（包括可能的注释符号）
                        text = " ".join(processed_parts[1:])
                        try:
                            # 保存当前剪贴板内容
                            old_clipboard = pyperclip.paste()
                            # 复制文本到剪贴板
                            pyperclip.copy(text)
                            # 粘贴文本
                            if sys.platform == 'darwin':  # macOS
                                pyautogui.hotkey('command', 'v')
                            else:
                                pyautogui.hotkey('ctrl', 'v')
                            # 短暂等待确保粘贴完成
                            time.sleep(0.1)
                            # 恢复剪贴板内容
                            pyperclip.copy(old_clipboard)
                        except Exception as e:
                            # 如果pyperclip不可用，使用原始方式
                            try:
                                pyautogui.write(text)
                            except Exception as e2:
                                self.status_var.set(f"输入错误: {str(e2)}")
                        self.status_var.set(f"已输入文本: {text}")

                    elif action == "key":
                        keys = processed_parts[1:]
                        pyautogui.hotkey(*keys)

                    elif action == "scroll":
                        amount = int(processed_parts[1])
                        pyautogui.scroll(amount)

                    elif action == "sleep":
                        sec = float(processed_parts[1])
                        time.sleep(sec)

                    # 短暂暂停确保命令执行
                    time.sleep(0.01)

                # 如果不是最后一次执行，则等待延迟时间
                if i < repeat_count - 1:
                    # 检查停止标志
                    if self.stop_execution:
                        self.status_var.set("执行已停止")
                        messagebox.showinfo("停止", "命令执行已停止")
                        return
                    time.sleep(repeat_delay)

            self.status_var.set(f"所有命令执行完成! 共执行了 {repeat_count} 次")
            
            # 恢复窗口
            if self.window_minimized:
                self.root.deiconify()
                self.window_minimized = False
                
            messagebox.showinfo("完成", f"所有命令执行完成! 共执行了 {repeat_count} 次")

        except Exception as e:
            self.status_var.set(f"执行错误: {str(e)}")
            
            # 出错时也恢复窗口
            if self.window_minimized:
                self.root.deiconify()
                self.window_minimized = False
                
            messagebox.showerror("错误", f"执行命令时出错:\n{str(e)}")
            
    def stop_execution_command(self):
        """停止命令执行"""
        self.stop_execution = True
        self.status_var.set("正在停止执行...")
        
        # 如果窗口最小化，恢复窗口
        if self.window_minimized:
            self.root.deiconify()
            self.window_minimized = False

    def clear_commands(self):
        """清除命令列表"""
        if messagebox.askyesno("确认", "确定要清除所有命令吗？"):
            self.raw_commands = []
            self.refresh_command_list_display()
            self.status_var.set("命令已清除")

    def save_commands(self):
        """保存命令到文件"""
        if not self.raw_commands:
            messagebox.showwarning("警告", "没有可保存的命令！")
            return
            
        # 使用文件对话框选择保存位置
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="保存命令",
            initialfile="automation_commands.json"
        )
        
        if not file_path:
            return  # 用户取消保存
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.raw_commands, f, indent=2, ensure_ascii=False)
                
            # 只显示文件名，不显示完整路径
            file_name = os.path.basename(file_path)
            self.status_var.set(f"命令已保存到 {file_name}")
            messagebox.showinfo("保存成功", f"命令已成功保存到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("保存错误", f"无法保存命令:\n{str(e)}")

    def load_commands(self):
        """从文件加载命令"""
        # 使用文件对话框选择文件
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="加载命令"
        )
        
        if not file_path:
            return  # 用户取消加载
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                commands = json.load(f)

            if not commands:
                messagebox.showinfo("加载", "文件为空，没有命令可加载")
                return
                
            if not messagebox.askyesno("加载", f"将加载 {len(commands)} 条命令，这会覆盖当前列表。确定继续吗？"):
                return

            self.raw_commands = commands
            self.calculate_indent_levels()
            self.refresh_command_list_display()
                
            # 只显示文件名，不显示完整路径
            file_name = os.path.basename(file_path)
            self.status_var.set(f"已加载 {len(commands)} 条命令 (来自: {file_name})")
        except FileNotFoundError:
            messagebox.showerror("加载错误", f"文件不存在:\n{file_path}")
        except json.JSONDecodeError:
            messagebox.showerror("加载错误", "文件格式错误，无法解析JSON数据")
        except Exception as e:
            messagebox.showerror("加载错误", f"无法加载命令:\n{str(e)}")

    def calculate_indent_levels(self):
        """计算命令的缩进层级（处理注释行）"""
        self.indent_levels = []
        current_indent = 0
        in_condition = False
        
        for cmd in self.raw_commands:
            cmd = cmd.strip()
            
            # ==== 新增：处理注释行 ====
            if cmd.startswith("#") or cmd.startswith("//"):
                # 注释行缩进级别为0
                self.indent_levels.append(0)
                continue
            # ========================
            
            if not cmd:
                self.indent_levels.append(0)
                continue
                
            parts = cmd.split()
            action = parts[0].lower()
            
            # 处理缩进增加的情况
            if action in ["ifimage", "ifnotimage", "else"]:
                self.indent_levels.append(current_indent)
                in_condition = True
            # 处理begin命令（增加缩进）
            elif action == "begin":
                self.indent_levels.append(current_indent)
                if in_condition:
                    current_indent += 1
                    in_condition = False
            # 处理end命令（减少缩进）
            elif action == "end":
                if current_indent > 0:
                    current_indent -= 1
                self.indent_levels.append(current_indent)
            # 其他命令
            else:
                self.indent_levels.append(current_indent)

    def refresh_command_list_display(self):
        """刷新命令列表显示（带缩进和注释样式）"""
        # 清除列表
        self.command_list.delete(0, tk.END)
        
        # 添加带缩进的命令
        for i, cmd in enumerate(self.raw_commands):
            if cmd.strip().startswith("#") or cmd.strip().startswith("//"):
                # 注释行使用灰色显示（不再设置字体）
                self.command_list.insert(tk.END, cmd)
                self.command_list.itemconfig(i, foreground="gray")
                continue
            
            indent = self.indent_levels[i] if i < len(self.indent_levels) else 0
            indent_str = "  " * indent
            display_cmd = f"{indent_str}{cmd}"
            self.command_list.insert(tk.END, display_cmd)
            self.set_command_color(i, cmd)
            
        # 更新行号
        self.update_line_numbers()
        
        # 恢复滚动位置
        self.restore_scroll_position()

    def set_command_color(self, index, cmd):
        """设置命令行的颜色（添加注释行处理）"""
        # ==== 新增：处理注释行 ====
        if cmd.strip().startswith("#") or cmd.strip().startswith("//"):
            # 注释行使用浅灰色背景
            self.command_list.itemconfig(index, bg="#F5F5F5")
            return
        # ========================
        
        action = cmd.split()[0].lower() if cmd else ""
        
        # 12种不同的颜色
        color_map = {
            "move": "#E3F2FD",       # 浅蓝
            "fastmove": "#D1C4E9",    # 浅紫
            "click": "#C8E6C9",       # 浅绿
            "doubleclick": "#FFF9C4", # 浅黄
            "drag": "#FFE0B2",        # 浅橙
            "type": "#F8BBD0",        # 浅粉
            "key": "#BBDEFB",         # 更浅蓝
            "scroll": "#B2EBF2",      # 青蓝
            "sleep": "#E1BEE7",       # 淡紫
            # 图片相关命令
            "imageclick": "#FFCDD2",  # 浅红
            "imagewait": "#FFCCBC",    # 浅橙红
            "ifimage": "#DCEDC8",     # 黄绿
            "ifnotimage": "#F5F5F5",  # 白色
            # 停止命令
            "stop": "#F8BBD0",        # 浅粉
            # 条件语句
            "begin": "#FFF9C4",       # 浅黄
            "end": "#FFF9C4",         # 浅黄
            "else": "#FFF9C4",        # 浅黄
            # 完成本次循环命令
            "breakloop": "#FFECB3"    # 浅橙黄
        }
        
        # 为未定义的动作生成随机但一致的颜色
        if action not in color_map:
            # 使用哈希值生成稳定的颜色
            hue = hash(action) % 360 / 360.0
            r, g, b = [int(255 * c) for c in colorsys.hsv_to_rgb(hue, 0.3, 0.95)]
            color = f"#{r:02x}{g:02x}{b:02x}"
            color_map[action] = color
        
        color = color_map.get(action, "#FFFFFF")
        self.command_list.itemconfig(index, bg=color)

    def update_line_numbers(self, event=None):
        """更新行数显示"""
        # 清除当前所有行号
        self.line_number_box.delete(0, tk.END)
        
        # 获取命令列表行数
        num_lines = len(self.raw_commands)
        
        # 添加行号，确保每行高度一致
        for i in range(1, num_lines + 1):
            self.line_number_box.insert(tk.END, str(i))
            
        # 同步两个列表框的高度和位置
        self.line_number_box.config(height=self.command_list.cget("height"))
        
        # 同步当前滚动位置
        first_line, last_line = self.command_list.yview()
        self.line_number_box.yview_moveto(first_line)

    def delete_selected_command(self):
        """删除选中的命令"""
        selection = self.command_list.curselection()
        if selection:
            # 保存当前滚动位置
            self.save_scroll_position()
            
            # 删除选中的命令（从后往前删除避免索引变化）
            for i in sorted(selection, reverse=True):
                del self.raw_commands[i]
            
            # 重新计算缩进并刷新显示
            self.calculate_indent_levels()
            self.refresh_command_list_display()
            
            # 恢复滚动位置
            self.restore_scroll_position()
            
            self.status_var.set(f"已删除 {len(selection)} 条命令")


if __name__ == "__main__":
    root = tk.Tk()
    app = MouseKeyboardAutomation(root)
    root.mainloop()
