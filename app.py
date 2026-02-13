import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu
from tkinter import scrolledtext
import threading
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class LabExperimentAnalyzer:
    def __init__(self):
        self.conn = None
        self.data = None
        self.growth_results = None
        self.current_experiment_id = None
    
    def connect(self, dbname, user, password, host='localhost', port='5432'):
        try:
            self.conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
            self.log("✅ Успешное подключение к БД")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка подключения: {e}", "error")
            return False
    
    def log(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "error":
            print(f"[{timestamp}] ❌ {message}")
        elif level == "warning":
            print(f"[{timestamp}] ⚠️ {message}")
        else:
            print(f"[{timestamp}] ℹ️ {message}")
    
    def load_experiment_data(self, experiment_id):
        try:
            query = """
            SELECT 
                e.expirement_name,
                r.fio as researcher,
                c.compound_name,
                m.measurements_time_hours,
                m.od_value,
                m.ph_value,
                m.temperature_celsius,
                m.replicate_number
            FROM measurements m
            JOIN expirements e ON m.id_expirement = e.id_expirement
            JOIN compounds c ON m.compound_id = c.compound_id
            JOIN researchers r ON e.id_research = r.id_research
            WHERE m.id_expirement = %s
            ORDER BY c.compound_name, m.measurements_time_hours, m.replicate_number
            """
            
            self.data = pd.read_sql_query(query, self.conn, params=(experiment_id,))
            self.current_experiment_id = experiment_id
            
            if self.data.empty:
                self.log(f"⚠️ Нет данных для эксперимента ID={experiment_id}", "warning")
                return self.data
            
            self.log(f"📥 Загружено {len(self.data)} строк из БД")
            self.log(f"🧪 Соединения: {', '.join(self.data['compound_name'].unique())}")
            self.log(f"⏰ Временные точки: {sorted(self.data['measurements_time_hours'].unique())}")
            
            return self.data
            
        except Exception as e:
            self.log(f"❌ Ошибка загрузки данных: {e}", "error")
            return None
    
    def calculate_growth_rate(self, start_time=0, end_time=24):
        if self.data is None or self.data.empty:
            self.log("❌ Данные не загружены", "error")
            return None
        
        try:
            results = []
            
            for compound in self.data['compound_name'].unique():
                compound_data = self.data[self.data['compound_name'] == compound]
                
                for replicate in compound_data['replicate_number'].unique():
                    rep_data = compound_data[compound_data['replicate_number'] == replicate]
                    
                    # Ищем измерения в начальное и конечное время
                    start_measurement = rep_data[rep_data['measurements_time_hours'] == start_time]
                    end_measurement = rep_data[rep_data['measurements_time_hours'] == end_time]
                    
                    if not start_measurement.empty and not end_measurement.empty:
                        initial_od = start_measurement.iloc[0]['od_value']
                        final_od = end_measurement.iloc[0]['od_value']
                        time_diff = end_time - start_time
                        
                        if time_diff > 0 and initial_od > 0 and final_od > 0:
                            growth_rate = (np.log(final_od) - np.log(initial_od)) / time_diff
                            
                            results.append({
                                'compound': compound,
                                'replicate': replicate,
                                'initial_od': initial_od,
                                'final_od': final_od,
                                'growth_rate': growth_rate,
                                'inhibition_percent': None
                            })
            
            if results:
                self.growth_results = pd.DataFrame(results)
                self.log(f"✅ Рассчитано {len(results)} значений скорости роста")
                return self.growth_results
            else:
                self.log("⚠️ Не удалось рассчитать скорость роста", "warning")
                return pd.DataFrame()
                
        except Exception as e:
            self.log(f"❌ Ошибка расчета скорости роста: {e}", "error")
            return None
    
    def calculate_inhibition(self):
        """Расчет процента ингибирования роста"""
        if self.data is None:
            self.log("❌ Данные не загружены", "error")
            return None
        
        try:
            # Сначала рассчитываем скорость роста
            if self.growth_results is None or self.growth_results.empty:
                self.calculate_growth_rate()
            
            if self.growth_results.empty:
                self.log("⚠️ Нет данных для расчета ингибирования", "warning")
                return None
            
            # Находим контрольную группу
            control_mask = self.growth_results['compound'].str.contains('Контроль', case=False, na=False)
            control_data = self.growth_results[control_mask]
            
            if control_data.empty:
                self.log("⚠️ Не найдена контрольная группа", "warning")
                return None
            
            # Средняя скорость роста контроля
            control_mean = control_data['growth_rate'].mean()
            
            if control_mean <= 0:
                self.log("❌ Средняя скорость роста контроля неположительна", "error")
                return None
            
            # Расчет ингибирования
            inhibition_results = self.growth_results.copy()
            
            for idx, row in inhibition_results.iterrows():
                if row['compound'] in control_data['compound'].values:
                    inhibition_percent = 0
                else:
                    if pd.notnull(row['growth_rate']):
                        inhibition_percent = ((control_mean - row['growth_rate']) / control_mean) * 100
                    else:
                        inhibition_percent = None
                
                inhibition_results.at[idx, 'inhibition_percent'] = inhibition_percent
            
            self.growth_results = inhibition_results
            self.log(f"✅ Рассчитано ингибирование для {len(inhibition_results)} образцов")
            return inhibition_results
            
        except Exception as e:
            self.log(f"❌ Ошибка расчета ингибирования: {e}", "error")
            return None
    
    def get_available_experiments(self):
        try:
            query = "SELECT id_expirement, expirement_name FROM expirements ORDER BY id_expirement"
            experiments = pd.read_sql_query(query, self.conn)
            self.log(f"📋 Получено {len(experiments)} экспериментов")
            return experiments
        except Exception as e:
            self.log(f"❌ Ошибка получения списка экспериментов: {e}", "error")
            return pd.DataFrame()
    
    def get_experiment_info(self, experiment_id):
        try:
            query = """
            SELECT e.*, r.fio 
            FROM expirements e
            JOIN researchers r ON e.id_research = r.id_research
            WHERE e.id_expirement = %s
            """
            info = pd.read_sql_query(query, self.conn, params=(experiment_id,))
            if not info.empty:
                self.log(f"📄 Получена информация об эксперименте ID={experiment_id}")
                return info.iloc[0]
            return None
        except Exception as e:
            self.log(f"❌ Ошибка получения информации об эксперименте: {e}", "error")
            return None
    
    def get_statistics(self):
        if self.data is None or self.data.empty:
            return None
        
        try:
            stats = {
                'Общие': {
                    'Всего измерений': len(self.data),
                    'Количество соединений': self.data['compound_name'].nunique(),
                    'Количество реплик': self.data['replicate_number'].nunique(),
                    'Временной диапазон': f"{self.data['measurements_time_hours'].min()} - {self.data['measurements_time_hours'].max()} ч"
                },
                'Оптическая плотность (OD)': self.data['od_value'].describe().to_dict(),
                'pH': self.data['ph_value'].describe().to_dict(),
                'Температура': self.data['temperature_celsius'].describe().to_dict()
            }
            return stats
        except Exception as e:
            self.log(f"❌ Ошибка расчета статистики: {e}", "error")
            return None
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.log("🔌 Соединение с БД закрыто")

class ModernLabAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🧪 Анализатор лабораторных экспериментов v2.0")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Иконка приложения (если есть)
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        
        self.analyzer = LabExperimentAnalyzer()
        self.current_experiment_id = None
        self.graph_windows = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Создаем меню
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню "Файл"
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Экспорт всех данных", command=lambda: self.export_results('xlsx'))
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        
        # Меню "Помощь"
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Помощь", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        
        # Главный контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Панель статуса
        self.status_bar = ttk.Label(self.root, text="Готов к работе", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Создаем вкладки
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладки
        tab1 = ttk.Frame(notebook); notebook.add(tab1, text='📊 Данные'); self.setup_data_tab(tab1)
        tab2 = ttk.Frame(notebook); notebook.add(tab2, text='📈 Анализ'); self.setup_analysis_tab(tab2)
        tab3 = ttk.Frame(notebook); notebook.add(tab3, text='📊 Графики'); self.setup_visualization_tab(tab3)
        tab4 = ttk.Frame(notebook); notebook.add(tab4, text='💾 Экспорт'); self.setup_export_tab(tab4)
        
        # Область вывода
        self.setup_output_area(main_container)
        
    def setup_data_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Панель подключения
        conn_frame = ttk.LabelFrame(frame, text="Подключение к БД", padding="10")
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(conn_frame, text="🔌 Подключиться", command=self.connect_db, 
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        self.conn_status = ttk.Label(conn_frame, text="❌ Не подключено", foreground="red", font=('Arial', 10))
        self.conn_status.pack(side=tk.LEFT, padx=20)
        
        # Выбор эксперимента
        exp_frame = ttk.LabelFrame(frame, text="Выбор эксперимента", padding="10")
        exp_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(exp_frame, text="ID эксперимента:").pack(side=tk.LEFT, padx=5)
        self.exp_id_var = tk.StringVar(value="1")
        exp_entry = ttk.Entry(exp_frame, textvariable=self.exp_id_var, width=10)
        exp_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(exp_frame, text="🔄 Загрузить", command=self.load_experiment_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(exp_frame, text="📋 Список экспериментов", command=self.show_experiments_list).pack(side=tk.LEFT, padx=5)
        
        # Таблица данных
        data_frame = ttk.LabelFrame(frame, text="Просмотр данных", padding="10")
        data_frame.pack(fill=tk.BOTH, expand=True)
        
        # Создаем Treeview с прокруткой
        tree_frame = ttk.Frame(data_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("expirement_name", "researcher", "compound_name", "measurements_time_hours", 
                  "od_value", "ph_value", "temperature_celsius", "replicate_number")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Настраиваем заголовки
        col_names = ["Эксперимент", "Исследователь", "Соединение", "Время (ч)", "OD", "pH", "Температура", "Реплика"]
        col_widths = [200, 180, 150, 100, 100, 80, 120, 80]
        
        for col, name, width in zip(columns, col_names, col_widths):
            self.tree.heading(col, text=name)
            self.tree.column(col, width=width, minwidth=50)
        
        # Добавляем прокрутки
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Размещаем элементы
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
    def setup_analysis_tab(self, parent):
        frame = ttk.Frame(parent, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Кнопки анализа
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 20))
        
        analysis_buttons = [
            ("📊 Статистика по данным", self.show_statistics),
            ("📈 Рассчитать скорость роста", self.calculate_growth),
            ("📉 Рассчитать ингибирование", self.calculate_inhibition),
            ("🧹 Очистить результаты", self.clear_results)
        ]
        
        for i, (text, command) in enumerate(analysis_buttons):
            ttk.Button(button_frame, text=text, command=command).grid(
                row=0, column=i, padx=5, pady=5, sticky="ew"
            )
            button_frame.grid_columnconfigure(i, weight=1)
        
        # Результаты анализа
        results_frame = ttk.LabelFrame(frame, text="Результаты анализа", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.analysis_text = scrolledtext.ScrolledText(results_frame, height=20, font=('Consolas', 10))
        self.analysis_text.pack(fill=tk.BOTH, expand=True)
        
    def setup_visualization_tab(self, parent):
        frame = ttk.Frame(parent, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Настройки графиков
        settings_frame = ttk.LabelFrame(frame, text="Настройки графиков", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(settings_frame, text="Размер графика:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.figsize_var = tk.StringVar(value="10x6")
        figsize_combo = ttk.Combobox(settings_frame, textvariable=self.figsize_var, 
                                    values=["8x6", "10x6", "12x8", "14x10"], width=10)
        figsize_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Кнопки графиков
        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        graph_buttons = [
            ("📈 Кривые роста", self.plot_growth),
            ("📊 Ингибирование", self.plot_inhibition),
            ("🌡️ Температура", self.plot_temp),
            ("🧪 pH", self.plot_ph),
            ("📊 Сравнение реплик", self.plot_replicates),
            ("📉 Все графики", self.plot_all)
        ]
        
        for i, (text, command) in enumerate(graph_buttons):
            row, col = divmod(i, 3)
            btn = ttk.Button(grid_frame, text=text, command=command)
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            grid_frame.grid_columnconfigure(col, weight=1)
            grid_frame.grid_rowconfigure(row, weight=1)
        
    def setup_export_tab(self, parent):
        frame = ttk.Frame(parent, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Экспорт результатов", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Опции экспорта
        options_frame = ttk.LabelFrame(frame, text="Опции", padding="10")
        options_frame.pack(fill=tk.X, pady=10)
        
        self.export_data_var = tk.BooleanVar(value=True)
        self.export_results_var = tk.BooleanVar(value=True)
        self.export_stats_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(options_frame, text="Исходные данные", variable=self.export_data_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Результаты анализа", variable=self.export_results_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Статистику", variable=self.export_stats_var).pack(anchor=tk.W, pady=2)
        
        # Кнопки экспорта
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        export_buttons = [
            ("💾 Excel (.xlsx)", lambda: self.export_results('xlsx')),
            ("📄 CSV (.csv)", lambda: self.export_results('csv')),
            ("📋 Копировать в буфер", self.copy_results),
            ("🖨️ Печать", self.print_results)
        ]
        
        for i, (text, command) in enumerate(export_buttons):
            ttk.Button(button_frame, text=text, command=command).grid(
                row=0, column=i, padx=5, pady=5, sticky="ew"
            )
            button_frame.grid_columnconfigure(i, weight=1)
        
    def setup_output_area(self, parent):
        output_frame = ttk.LabelFrame(parent, text="Журнал выполнения", padding="10")
        output_frame.pack(fill=tk.X, pady=10)
        
        # Панель инструментов журнала
        log_toolbar = ttk.Frame(output_frame)
        log_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(log_toolbar, text="📄 Очистить журнал", command=self.clear_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_toolbar, text="💾 Сохранить журнал", command=self.save_log).pack(side=tk.LEFT, padx=2)
        
        # Текстовое поле журнала
        self.output_text = scrolledtext.ScrolledText(output_frame, height=10, font=('Consolas', 9))
        self.output_text.pack(fill=tk.BOTH)
        
        # Настраиваем теги для цветов
        self.output_text.tag_config("info", foreground="black")
        self.output_text.tag_config("success", foreground="green")
        self.output_text.tag_config("error", foreground="red")
        self.output_text.tag_config("warning", foreground="orange")
        
    def log_output(self, message, message_type="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.output_text.insert(tk.END, formatted_message, message_type)
        self.output_text.see(tk.END)
        
        # Обновляем статус бар (только для коротких сообщений)
        if len(message) < 100:
            self.status_bar.config(text=message)
    
    def connect_db(self):
        try:
            success = self.analyzer.connect(
                dbname="science_research",
                user="postgres",
                password="sql-class"
            )
            if success:
                self.conn_status.config(text="✅ Подключено", foreground="green")
                self.log_output("✓ Успешно подключено к базе данных science_research", "success")
            else:
                self.conn_status.config(text="❌ Ошибка", foreground="red")
                self.log_output("✗ Не удалось подключиться к базе данных", "error")
        except Exception as e:
            self.log_output(f"✗ Ошибка подключения: {e}", "error")
    
    def show_experiments_list(self):
        if self.analyzer.conn is None:
            messagebox.showwarning("Ошибка", "Сначала подключитесь к БД")
            return
        
        try:
            experiments = self.analyzer.get_available_experiments()
            if experiments.empty:
                self.log_output("⚠️ В базе данных нет экспериментов", "warning")
                return
            
            # Создаем окно со списком
            list_window = tk.Toplevel(self.root)
            list_window.title("Список экспериментов")
            list_window.geometry("600x400")
            
            # Таблица экспериментов
            tree = ttk.Treeview(list_window, columns=("id", "name"), show="headings", height=15)
            tree.heading("id", text="ID")
            tree.heading("name", text="Название эксперимента")
            tree.column("id", width=80)
            tree.column("name", width=500)
            
            for _, row in experiments.iterrows():
                tree.insert("", tk.END, values=(row['id_expirement'], row['expirement_name']))
            
            # Прокрутка
            scrollbar = ttk.Scrollbar(list_window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # Кнопка выбора
            def select_experiment():
                selection = tree.selection()
                if selection:
                    item = tree.item(selection[0])
                    self.exp_id_var.set(item['values'][0])
                    list_window.destroy()
                    self.load_experiment_data()
            
            ttk.Button(list_window, text="Выбрать", command=select_experiment).pack(pady=5)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
        except Exception as e:
            self.log_output(f"✗ Ошибка получения списка экспериментов: {e}", "error")
    
    def load_experiment_data(self):
        if self.analyzer.conn is None:
            messagebox.showwarning("Ошибка", "Сначала подключитесь к БД")
            return
        
        try:
            experiment_id = int(self.exp_id_var.get())
            self.current_experiment_id = experiment_id
            
            def load_data():
                self.log_output(f"⏳ Загрузка данных эксперимента ID={experiment_id}...", "info")
                
                data = self.analyzer.load_experiment_data(experiment_id)
                
                if data is None or data.empty:
                    self.log_output(f"⚠️ Нет данных для эксперимента ID={experiment_id}", "warning")
                    return
                
                # Очищаем таблицу
                for row in self.tree.get_children():
                    self.tree.delete(row)
                
                # Заполняем таблицу
                for _, row in data.iterrows():
                    self.tree.insert("", tk.END, values=(
                        row['expirement_name'][:50] + "..." if len(row['expirement_name']) > 50 else row['expirement_name'],
                        row['researcher'],
                        row['compound_name'],
                        f"{row['measurements_time_hours']:.1f}",
                        f"{row['od_value']:.4f}",
                        f"{row['ph_value']:.2f}",
                        f"{row['temperature_celsius']:.2f}",
                        row['replicate_number']
                    ))
                
                # Получаем информацию об эксперименте
                info = self.analyzer.get_experiment_info(experiment_id)
                if info is not None:
                    self.log_output(f"✓ Загружено {len(data)} измерений", "success")
                    self.log_output(f"📄 Эксперимент: {info['expirement_name']}", "info")
                    self.log_output(f"👨‍🔬 Исследователь: {info['fio']}", "info")
                else:
                    self.log_output(f"✓ Загружено {len(data)} измерений", "success")
            
            threading.Thread(target=load_data, daemon=True).start()
            
        except ValueError:
            self.log_output("✗ ID эксперимента должен быть числом", "error")
        except Exception as e:
            self.log_output(f"✗ Ошибка загрузки: {e}", "error")
    
    def show_statistics(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        
        try:
            stats = self.analyzer.get_statistics()
            if stats is None:
                self.log_output("⚠️ Не удалось рассчитать статистику", "warning")
                return
            
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(1.0, "📊 СТАТИСТИКА ПО ДАННЫМ\n")
            self.analysis_text.insert(tk.END, "="*50 + "\n\n")
            
            for section, data in stats.items():
                self.analysis_text.insert(tk.END, f"{section}:\n")
                self.analysis_text.insert(tk.END, "-"*30 + "\n")
                
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, float):
                            self.analysis_text.insert(tk.END, f"  {key}: {value:.4f}\n")
                        else:
                            self.analysis_text.insert(tk.END, f"  {key}: {value}\n")
                self.analysis_text.insert(tk.END, "\n")
            
            self.log_output("✓ Статистика рассчитана", "success")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка: {e}", "error")
    
    def calculate_growth(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        
        try:
            def calc():
                self.log_output("⏳ Расчет скорости роста...", "info")
                growth = self.analyzer.calculate_growth_rate()
                
                if growth is not None and not growth.empty:
                    self.analysis_text.delete(1.0, tk.END)
                    self.analysis_text.insert(1.0, "📈 РЕЗУЛЬТАТЫ РАСЧЕТА СКОРОСТИ РОСТА\n")
                    self.analysis_text.insert(tk.END, "="*60 + "\n\n")
                    self.analysis_text.insert(tk.END, growth.to_string(index=False))
                    
                    # Добавляем сводку
                    self.analysis_text.insert(tk.END, "\n\n📊 СВОДКА:\n")
                    self.analysis_text.insert(tk.END, "-"*30 + "\n")
                    for compound in growth['compound'].unique():
                        compound_data = growth[growth['compound'] == compound]
                        mean_growth = compound_data['growth_rate'].mean()
                        self.analysis_text.insert(tk.END, f"{compound}: µ = {mean_growth:.6f} (n={len(compound_data)})\n")
                    
                    self.log_output("✓ Скорость роста рассчитана", "success")
                else:
                    self.log_output("⚠️ Не удалось рассчитать скорость роста", "warning")
            
            threading.Thread(target=calc, daemon=True).start()
            
        except Exception as e:
            self.log_output(f"✗ Ошибка: {e}", "error")
    
    def calculate_inhibition(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные эксперимента")
            return
        
        try:
            def calc():
                self.log_output("⏳ Расчет ингибирования роста...", "info")
                inhibition = self.analyzer.calculate_inhibition()
                
                if inhibition is not None and not inhibition.empty:
                    self.analysis_text.delete(1.0, tk.END)
                    self.analysis_text.insert(1.0, "📉 РЕЗУЛЬТАТЫ РАСЧЕТА ИНГИБИРОВАНИЯ\n")
                    self.analysis_text.insert(tk.END, "="*60 + "\n\n")
                    
                    # Форматируем вывод
                    formatted = inhibition.copy()
                    if 'inhibition_percent' in formatted.columns:
                        formatted['inhibition_percent'] = formatted['inhibition_percent'].apply(
                            lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A"
                        )
                    
                    # Форматируем скорость роста
                    if 'growth_rate' in formatted.columns:
                        formatted['growth_rate'] = formatted['growth_rate'].apply(
                            lambda x: f"{x:.6f}" if pd.notnull(x) else "N/A"
                        )
                    
                    self.analysis_text.insert(tk.END, formatted.to_string(index=False))
                    
                    # Добавляем сводку по соединениям
                    self.analysis_text.insert(tk.END, "\n\n📊 СВОДКА ПО СОЕДИНЕНИЯМ:\n")
                    self.analysis_text.insert(tk.END, "-"*40 + "\n")
                    
                    for compound in formatted['compound'].unique():
                        if 'Контроль' not in str(compound):
                            compound_data = formatted[formatted['compound'] == compound]
                            inhibition_values = compound_data[compound_data['inhibition_percent'] != 'N/A']['inhibition_percent']
                            if not inhibition_values.empty:
                                # Извлекаем числовые значения
                                values = [float(x.replace('%', '')) for x in inhibition_values if x != 'N/A']
                                if values:
                                    mean_inhibition = np.mean(values)
                                    std_inhibition = np.std(values)
                                    self.analysis_text.insert(tk.END, 
                                        f"{compound}: {mean_inhibition:.1f}% ± {std_inhibition:.1f}% (n={len(values)})\n")
                    
                    self.log_output("✓ Ингибирование рассчитано", "success")
                else:
                    self.log_output("⚠️ Не удалось рассчитать ингибирование", "warning")
            
            threading.Thread(target=calc, daemon=True).start()
            
        except Exception as e:
            self.log_output(f"✗ Ошибка: {e}", "error")
    
    def clear_results(self):
        self.analysis_text.delete(1.0, tk.END)
        self.log_output("🧹 Результаты очищены", "info")
    
    def clear_log(self):
        self.output_text.delete(1.0, tk.END)
        self.log_output("🧹 Журнал очищен", "info")
    
    def save_log(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.get(1.0, tk.END))
                self.log_output(f"✓ Журнал сохранен в {file_path}", "success")
            except Exception as e:
                self.log_output(f"✗ Ошибка сохранения: {e}", "error")
    
    def plot_growth(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        
        threading.Thread(target=self._create_growth_plot, daemon=True).start()
    
    def _create_growth_plot(self):
        try:
            # Получаем размер графика
            width, height = map(int, self.figsize_var.get().split('x'))
            
            fig = Figure(figsize=(width, height))
            ax = fig.add_subplot(111)
            
            data = self.analyzer.data
            compounds = data['compound_name'].unique()
            
            # Используем цветовую палитру
            colors = plt.cm.tab10(np.linspace(0, 1, len(compounds)))
            
            for compound, color in zip(compounds, colors):
                compound_data = data[data['compound_name'] == compound]
                
                # Группируем по времени и рассчитываем среднее и стандартное отклонение
                grouped = compound_data.groupby('measurements_time_hours')['od_value']
                mean_curve = grouped.mean()
                std_curve = grouped.std()
                
                # Рисуем кривую со стандартным отклонением
                ax.plot(mean_curve.index, mean_curve.values, 
                       label=compound, color=color, linewidth=2, marker='o', markersize=6)
                
                # Заливка для стандартного отклонения
                ax.fill_between(mean_curve.index,
                              mean_curve.values - std_curve.values,
                              mean_curve.values + std_curve.values,
                              color=color, alpha=0.2)
            
            ax.set_xlabel('Время, часы', fontsize=12)
            ax.set_ylabel('Оптическая плотность (OD)', fontsize=12)
            ax.set_title('Кинетика роста микроорганизмов', fontsize=14, fontweight='bold')
            ax.legend(loc='best', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            
            fig.tight_layout()
            self._show_plot_window(fig, "Кривые роста")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка построения графика: {e}", "error")
    
    def plot_inhibition(self):
        if self.analyzer.growth_results is None or self.analyzer.growth_results.empty:
            self.calculate_inhibition()
        
        if self.analyzer.growth_results is None or self.analyzer.growth_results.empty:
            self.log_output("⚠️ Нет данных для графика ингибирования", "warning")
            return
        
        threading.Thread(target=self._create_inhibition_plot, daemon=True).start()
    
    def _create_inhibition_plot(self):
        try:
            width, height = map(int, self.figsize_var.get().split('x'))
            
            fig = Figure(figsize=(width, height))
            ax = fig.add_subplot(111)
            
            data = self.analyzer.growth_results
            
            # Фильтруем контроль и удаляем NaN
            control_mask = data['compound'].str.contains('Контроль', case=False, na=False)
            plot_data = data[~control_mask].dropna(subset=['inhibition_percent'])
            
            if plot_data.empty:
                self.log_output("⚠️ Нет данных для графика ингибирования", "warning")
                return
            
            # Группируем по соединениям
            grouped = plot_data.groupby('compound')['inhibition_percent']
            compounds = list(grouped.groups.keys())
            means = grouped.mean().values
            stds = grouped.std().values
            
            # Создаем столбчатую диаграмму с помощью seaborn для лучшего отображения
            fig.clf()
            ax = fig.add_subplot(111)
            
            # Используем seaborn для построения графика
            sns.barplot(data=plot_data, x='compound', y='inhibition_percent', 
                       ax=ax, palette='viridis', ci='sd', capsize=0.1)
            
            # Добавляем значения на столбцы
            for i, (mean, std) in enumerate(zip(means, stds)):
                ax.text(i, mean + 3, f'{mean:.1f}%', ha='center', fontweight='bold', fontsize=10)
            
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            ax.set_ylabel('% Ингибирования роста', fontsize=12)
            ax.set_title('Эффективность соединений', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 105)
            ax.grid(True, alpha=0.3, axis='y')
            
            # Линия 50% ингибирования
            ax.axhline(y=50, color='red', linestyle='--', alpha=0.5, linewidth=1.5)
            ax.text(0.02, 0.98, '50% ингибирование', transform=ax.transAxes, 
                   color='red', fontsize=10, verticalalignment='top')
            
            fig.tight_layout()
            self._show_plot_window(fig, "Ингибирование роста")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка построения графика: {e}", "error")
    
    def plot_temp(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        threading.Thread(target=self._create_temp_plot, daemon=True).start()
    
    def _create_temp_plot(self):
        try:
            width, height = map(int, self.figsize_var.get().split('x'))
            
            fig = Figure(figsize=(width, height))
            ax = fig.add_subplot(111)
            
            data_24h = self.analyzer.data[self.analyzer.data['measurements_time_hours'] == 24]
            if len(data_24h) == 0:
                self.log_output("⚠️ Нет данных для 24 часов", "warning")
                return
            
            compounds = data_24h['compound_name'].unique()
            colors = plt.cm.Set2(np.linspace(0, 1, len(compounds)))
            
            for compound, color in zip(compounds, colors):
                compound_data = data_24h[data_24h['compound_name'] == compound]
                
                # Группируем по температуре
                grouped = compound_data.groupby('temperature_celsius')['od_value']
                mean_od = grouped.mean()
                std_od = grouped.std()
                
                # Сортируем по температуре
                mean_od = mean_od.sort_index()
                std_od = std_od.sort_index()
                
                ax.plot(mean_od.index, mean_od.values, label=compound, 
                       color=color, marker='o', linewidth=2, markersize=8)
                
                # Отображаем стандартное отклонение
                ax.fill_between(mean_od.index,
                              mean_od.values - std_od.values,
                              mean_od.values + std_od.values,
                              color=color, alpha=0.2)
            
            ax.set_xlabel('Температура, °C', fontsize=12)
            ax.set_ylabel('Оптическая плотность (OD)', fontsize=12)
            ax.set_title('Влияние температуры на рост микроорганизмов (24 ч)', 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='best', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            
            fig.tight_layout()
            self._show_plot_window(fig, "Влияние температуры")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка построения графика: {e}", "error")
    
    def plot_ph(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        threading.Thread(target=self._create_ph_plot, daemon=True).start()
    
    def _create_ph_plot(self):
        try:
            width, height = map(int, self.figsize_var.get().split('x'))
            
            fig = Figure(figsize=(width, height))
            ax = fig.add_subplot(111)
            
            data_24h = self.analyzer.data[self.analyzer.data['measurements_time_hours'] == 24]
            if len(data_24h) == 0:
                self.log_output("⚠️ Нет данных для 24 часов", "warning")
                return
            
            compounds = data_24h['compound_name'].unique()
            colors = plt.cm.Set3(np.linspace(0, 1, len(compounds)))
            
            for compound, color in zip(compounds, colors):
                compound_data = data_24h[data_24h['compound_name'] == compound]
                
                # Группируем по pH
                grouped = compound_data.groupby('ph_value')['od_value']
                mean_od = grouped.mean()
                std_od = grouped.std()
                
                # Сортируем по pH
                mean_od = mean_od.sort_index()
                std_od = std_od.sort_index()
                
                ax.plot(mean_od.index, mean_od.values, label=compound, 
                       color=color, marker='s', linewidth=2, markersize=8)
                
                # Отображаем стандартное отклонение
                ax.fill_between(mean_od.index,
                              mean_od.values - std_od.values,
                              mean_od.values + std_od.values,
                              color=color, alpha=0.2)
            
            ax.set_xlabel('pH', fontsize=12)
            ax.set_ylabel('Оптическая плотность (OD)', fontsize=12)
            ax.set_title('Влияние pH на рост микроорганизмов (24 ч)', 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='best', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            
            fig.tight_layout()
            self._show_plot_window(fig, "Влияние pH")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка построения графика: {e}", "error")
    
    def plot_replicates(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        threading.Thread(target=self._create_replicates_plot, daemon=True).start()
    
    def _create_replicates_plot(self):
        try:
            width, height = map(int, self.figsize_var.get().split('x'))
            
            fig = Figure(figsize=(width, height))
            ax = fig.add_subplot(111)
            
            data = self.analyzer.data
            compounds = data['compound_name'].unique()
            
            # Фильтруем данные для 24 часов
            data_24h = data[data['measurements_time_hours'] == 24]
            
            if data_24h.empty:
                self.log_output("⚠️ Нет данных для 24 часов", "warning")
                return
            
            # Подготовка данных для boxplot
            plot_data = []
            labels = []
            
            for compound in compounds:
                compound_data = data_24h[data_24h['compound_name'] == compound]
                if not compound_data.empty:
                    plot_data.append(compound_data['od_value'].values)
                    labels.append(f"{compound}\n(n={len(compound_data)})")
            
            # Создаем boxplot
            bp = ax.boxplot(plot_data, labels=labels, patch_artist=True, showmeans=True)
            
            # Настраиваем цвета
            colors = plt.cm.Paired(np.linspace(0, 1, len(plot_data)))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            ax.set_xlabel('Соединения', fontsize=12)
            ax.set_ylabel('Оптическая плотность (OD, 24 ч)', fontsize=12)
            ax.set_title('Сравнение реплик по соединениям', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_axisbelow(True)
            
            # Поворачиваем подписи если их много
            if len(labels) > 4:
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            
            fig.tight_layout()
            self._show_plot_window(fig, "Сравнение реплик")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка построения графика: {e}", "error")
    
    def plot_all(self):
        self.log_output("⏳ Построение всех графиков...", "info")
        self.plot_growth()
        self.plot_inhibition()
        self.plot_temp()
        self.plot_ph()
        self.plot_replicates()
    
    def _show_plot_window(self, fig, title):
        try:
            window = tk.Toplevel(self.root)
            window.title(title)
            window.geometry("900x700")
            
            # Создаем фрейм для графика
            canvas_frame = ttk.Frame(window)
            canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Холст для графика
            canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Панель инструментов
            toolbar_frame = ttk.Frame(window)
            toolbar_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            
            # Кнопка сохранения
            ttk.Button(toolbar_frame, text="💾 Сохранить график", 
                      command=lambda: self.save_figure(fig)).pack(side=tk.RIGHT, padx=5)
            
            self.graph_windows.append(window)
            self.log_output(f"✓ График '{title}' построен", "success")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка отображения графика: {e}", "error")
    
    def save_figure(self, fig):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("PDF files", "*.pdf"),
                ("SVG files", "*.svg"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            try:
                fig.savefig(file_path, dpi=300, bbox_inches='tight')
                self.log_output(f"✓ График сохранен в {file_path}", "success")
            except Exception as e:
                self.log_output(f"✗ Ошибка сохранения графика: {e}", "error")
    
    def export_results(self, file_type):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        
        try:
            if file_type == 'xlsx':
                file_ext = '.xlsx'
                file_types = [("Excel files", "*.xlsx"), ("All files", "*.*")]
            else:
                file_ext = '.csv'
                file_types = [("CSV files", "*.csv"), ("All files", "*.*")]
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=file_ext,
                filetypes=file_types
            )
            
            if not file_path:
                return
            
            if file_type == 'xlsx':
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # Лист с исходными данными
                    if self.export_data_var.get():
                        self.analyzer.data.to_excel(writer, sheet_name='Исходные_данные', index=False)
                    
                    # Лист с результатами анализа
                    if self.export_results_var.get() and self.analyzer.growth_results is not None:
                        self.analyzer.growth_results.to_excel(writer, sheet_name='Анализ_роста', index=False)
                    
                    # Лист со статистикой
                    if self.export_stats_var.get():
                        stats = self.analyzer.get_statistics()
                        if stats:
                            stats_df = pd.DataFrame([stats['Общие']])
                            stats_df.to_excel(writer, sheet_name='Статистика', index=False)
                    
                    self.log_output(f"✓ Данные экспортированы в Excel: {file_path}", "success")
            else:
                # Для CSV экспортируем только данные (многолистовой CSV невозможен)
                self.analyzer.data.to_csv(file_path, index=False, encoding='utf-8')
                self.log_output(f"✓ Данные экспортированы в CSV: {file_path}", "success")
                
        except Exception as e:
            self.log_output(f"✗ Ошибка экспорта: {e}", "error")
    
    def copy_results(self):
        if self.analyzer.growth_results is not None and not self.analyzer.growth_results.empty:
            try:
                self.root.clipboard_clear()
                # Копируем форматированные результаты
                text_to_copy = self.analysis_text.get(1.0, tk.END)
                if text_to_copy.strip():
                    self.root.clipboard_append(text_to_copy)
                    self.log_output("✓ Результаты скопированы в буфер обмена", "success")
                else:
                    self.log_output("⚠️ Нет результатов для копирования", "warning")
            except Exception as e:
                self.log_output(f"✗ Ошибка копирования: {e}", "error")
        else:
            messagebox.showwarning("Ошибка", "Сначала выполните расчеты")
    
    def print_results(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Ошибка", "Сначала загрузите данные")
            return
        
        try:
            # Создаем PDF для печати (упрощенная версия)
            self.log_output("🖨️ Подготовка к печати...", "info")
            
            # Можно добавить более сложную логику печати здесь
            messagebox.showinfo("Печать", 
                "Функция печати в разработке. Используйте экспорт в Excel для печати результатов.")
            
        except Exception as e:
            self.log_output(f"✗ Ошибка печати: {e}", "error")
    
    def show_about(self):
        about_text = """
        Анализатор лабораторных экспериментов v2.0
        
        Программа для анализа данных микробиологических
        и фармакологических исследований.
        
        Функции:
        - Загрузка данных из PostgreSQL
        - Расчет скорости роста микроорганизмов
        - Расчет процента ингибирования
        - Построение графиков и визуализация
        - Экспорт результатов
        
        Автор: Андреев Артём Станиславович
        Версия: 2.0 (2026)
        """
        
        messagebox.showinfo("О программе", about_text)
    
    def on_closing(self):
        if self.analyzer.conn:
            self.analyzer.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ModernLabAnalyzerGUI(root)
    
    # Обработка закрытия окна
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Центрирование окна
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()