CREATE TABLE researchers (
    id_research SERIAL PRIMARY KEY,
    fio VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    departament VARCHAR(150),
    phone VARCHAR(20),
    zhanie VARCHAR(100)
);

-- 2. Таблица соединений
CREATE TABLE compounds (
    compound_id SERIAL PRIMARY KEY,
    compound_name VARCHAR(200) NOT NULL
);

-- 3. Таблица экспериментов
CREATE TABLE expirements (
    id_expirement SERIAL PRIMARY KEY,
    expirement_name VARCHAR(300) NOT NULL,
    id_research INT NOT NULL,
    FOREIGN KEY (id_research) REFERENCES researchers(id_research)
);

-- 4. Таблица измерений
CREATE TABLE measurements (
    id_measurement SERIAL PRIMARY KEY,
    id_expirement INT NOT NULL,
    compound_id INT NOT NULL,
    measurements_time_hours DECIMAL(10,2),
    od_value DECIMAL(10,4),
    ph_value DECIMAL(4,2),
    temperature_celsius DECIMAL(5,2),
    replicate_number INT,
    FOREIGN KEY (id_expirement) REFERENCES expirements(id_expirement),
    FOREIGN KEY (compound_id) REFERENCES compounds(compound_id)
);

-- Вставляем тестовые данные

-- 1. Исследователи
INSERT INTO researchers (fio, email, departament, phone, zhanie) VALUES
('Андреев Артём Станиславович', 'andreev@lab.ru', 'Микробиология', '+7(999)123-45-67', 'Кандидат биологических наук'),
('Петрова Ирина Владимировна', 'petrova@lab.ru', 'Фармакология', '+7(999)234-56-78', 'Доктор медицинских наук'),
('Сидоров Михаил Петрович', 'sidorov@lab.ru', 'Биохимия', '+7(999)345-67-89', 'Кандидат химических наук'),
('Козлова Ольга Сергеевна', 'kozlova@lab.ru', 'Микробиология', '+7(999)456-78-90', 'Старший научный сотрудник'),
('Николаев Дмитрий Алексеевич', 'nikolaev@lab.ru', 'Фармакология', '+7(999)567-89-01', 'Научный сотрудник');

-- 2. Соединения
INSERT INTO compounds (compound_name) VALUES
('Контроль (без препарата)'),
('Соединение X-123'),
('Стандарт (ципрофлоксацин)'),
('Ампициллин'),
('Соединение Y-456'),
('Гентамицин');

-- 3. Эксперименты
INSERT INTO expirements (expirement_name, id_research) VALUES
('Антибиотическая активность соединения X-123', 1),
('Скрининг противогрибковых средств', 2),
('Влияние pH на активность ампициллина', 3),
('Термостабильность новых соединений', 4),
('Сравнительный анализ антибиотиков', 5),
('Изучение резистентности штаммов', 1);

-- 4. Измерения (тестовые данные для первого эксперимента)
INSERT INTO measurements (id_expirement, compound_id, measurements_time_hours, od_value, ph_value, temperature_celsius, replicate_number) VALUES
-- Контроль (реплики 1 и 2)
(1, 1, 0, 0.05, 7.0, 36.8, 1),
(1, 1, 0, 0.06, 7.0, 36.9, 2),
(1, 1, 2, 0.15, 7.0, 37.1, 1),
(1, 1, 4, 0.45, 7.0, 37.4, 1),
(1, 1, 6, 0.85, 7.0, 37.2, 1),
(1, 1, 8, 1.25, 7.0, 37.0, 1),
(1, 1, 24, 2.80, 7.1, 36.8, 1),
(1, 1, 24, 2.75, 7.1, 37.0, 2),
(1, 1, 24, 1.80, 7.0, 35.0, 3),
(1, 1, 24, 3.20, 7.5, 40.0, 4),

-- Соединение X-123
(1, 2, 0, 0.05, 7.0, 36.8, 1),
(1, 2, 0, 0.06, 7.0, 36.7, 2),
(1, 2, 2, 0.08, 7.0, 37.2, 1),
(1, 2, 4, 0.12, 7.0, 37.5, 1),
(1, 2, 6, 0.15, 7.1, 37.3, 1),
(1, 2, 8, 0.18, 7.1, 37.0, 1),
(1, 2, 24, 0.25, 7.2, 36.9, 1),
(1, 2, 24, 0.26, 7.2, 37.1, 2),
(1, 2, 24, 0.35, 7.3, 39.0, 3),
(1, 2, 24, 0.15, 7.0, 34.0, 4),

-- Стандарт (ципрофлоксацин)
(1, 3, 0, 0.05, 7.0, 36.9, 1),
(1, 3, 2, 0.06, 7.0, 37.0, 1),
(1, 3, 4, 0.07, 7.0, 37.3, 1),
(1, 3, 6, 0.08, 7.0, 37.1, 1),
(1, 3, 8, 0.09, 7.0, 36.9, 1),
(1, 3, 24, 0.12, 7.0, 36.7, 1),
(1, 3, 24, 0.10, 7.0, 37.5, 2),

-- Дополнительные данные для других экспериментов
(2, 4, 0, 0.10, 6.5, 30.0, 1),
(2, 4, 24, 0.85, 6.5, 30.0, 1),
(3, 1, 0, 0.05, 6.0, 37.0, 1),
(3, 1, 24, 2.50, 6.0, 37.0, 1);