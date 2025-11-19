from flask import Flask, render_template, request, redirect, url_for, session
import logging
import sqlite3
import hashlib
from datetime import datetime
import re

from pyexpat.errors import messages

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
app = Flask(__name__)
app.secret_key = 'schedule'
# создание таблиц
with sqlite3.connect("BD/YourBD.db") as YourBD:
    cursor = YourBD.cursor()
    logging.debug("Начало инициализации базы данных")
    # Таблица 1: группа
    cursor.execute("""CREATE TABLE IF NOT EXISTS groups
    (
        id
        INTEGER
        PRIMARY
        KEY
        AUTOINCREMENT,
        faculty
        TEXT
        NOT
        NULL,
        course
        INTEGER
        NOT
        NULL
        CHECK
                      (
        course
        BETWEEN
        1
        AND
        4
                      ),
        name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
    logging.debug("Таблица groups создана")
    # Таблица 2: предмет, тип
    cursor.execute("""CREATE TABLE IF NOT EXISTS subjects
                      (
                          id
                          INTEGER
                          PRIMARY
                          KEY
                          AUTOINCREMENT,
                          name
                          TEXT
                          NOT
                          NULL
                      )""")
    logging.debug("Таблица subjects создана")
    # Таблица 3: имя, фамилия преподователей
    cursor.execute("""CREATE TABLE IF NOT EXISTS teachers
                      (
                          id
                          INTEGER
                          PRIMARY
                          KEY
                          AUTOINCREMENT,
                          first_name
                          TEXT
                          NOT
                          NULL,
                          last_name
                          TEXT
                          NOT
                          NULL
                      )""")
    logging.debug("Таблица teachers создана")
    # Таблица 4: расписание
    cursor.execute("""CREATE TABLE IF NOT EXISTS schedule
    (
        id
        INTEGER
        PRIMARY
        KEY
        AUTOINCREMENT,
        group_id
        INTEGER
        NOT
        NULL,
        subject_id
        INTEGER
        NOT
        NULL,
        teacher_id
        INTEGER
        NOT
        NULL,
        day_of_week
        TEXT
        NOT
        NULL
        CHECK (
        day_of_week
        IN
                      (
        'понедельник',
        'вторник',
        'среда',
        'четверг',
        'пятница',
        'суббота'
                      )),
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        room TEXT NOT NULL,
        lesson_type TEXT NOT NULL CHECK
                      (
                          lesson_type
                          IN
                      (
                          'лекция',
                          'практика',
                          'лабораторная'
                      )),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY
                      (
                          group_id
                      ) REFERENCES groups
                      (
                          id
                      ) ON DELETE CASCADE,
        FOREIGN KEY
                      (
                          subject_id
                      ) REFERENCES subjects
                      (
                          id
                      )
                        ON DELETE CASCADE,
        FOREIGN KEY
                      (
                          teacher_id
                      ) REFERENCES teachers
                      (
                          id
                      )
                        ON DELETE CASCADE
        )""")
    logging.debug("Таблица schedule создана")

    YourBD.commit()
    logging.info("База данных инициализирована успешно")


def validate_group(faculty, course, name):
    """Проверка данных для таблицы groups."""

    if not faculty or not isinstance(faculty, str) or not faculty.strip():
        return False, "Факультет должен быть непустой строкой"

    # курс
    try:
        course = int(course)
        if course < 1 or course > 4:
            return False, "Курс должен быть числом от 1 до 4"
    except (ValueError, TypeError):
        return False, "Курс должен быть числом"

    if not name or not isinstance(name, str) or not name.strip():
        return False, "Название группы должно быть непустой строкой"

    return True, None


# =========================
#   ВАЛИДАЦИЯ ПРЕДМЕТА
# =========================
def validate_subject(name):
    """Проверка данных для таблицы subjects."""

    if not name or not isinstance(name, str) or not name.strip():
        return False, "Название предмета должно быть непустой строкой"

    return True, None


# =========================
#   ВАЛИДАЦИЯ ПРЕПОДАВАТЕЛЯ
# =========================
def validate_teacher(first_name, last_name):
    """Проверка данных для таблицы teachers."""

    if not first_name or not isinstance(first_name, str) or not first_name.strip():
        return False, "Имя преподавателя должно быть непустой строкой"

    if not last_name or not isinstance(last_name, str) or not last_name.strip():
        return False, "Фамилия преподавателя должна быть непустой строкой"

    return True, None


# =========================
#   ВАЛИДАЦИЯ РАСПИСАНИЯ
# =========================
def validate_schedule_entry(group_id, subject_id, teacher_id,
                            day_of_week, start_time, end_time,
                            room, lesson_type):
    """Проверка данных для таблицы schedule."""

    # Проверяем ID
    for field_name, value in {
        "ID группы": group_id,
        "ID предмета": subject_id,
        "ID преподавателя": teacher_id
    }.items():
        try:
            val = int(value)
            if val <= 0:
                return False, f"{field_name} должен быть положительным числом"
        except (ValueError, TypeError):
            return False, f"{field_name} должен быть числом"

    # День недели
    valid_days = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота")
    if day_of_week not in valid_days:
        return False, "Неверный день недели"

    # Формат времени
    time_pattern = r"^\d{2}:\d{2}$"
    if not re.match(time_pattern, start_time):
        return False, "Время начала должно быть в формате ЧЧ:ММ"
    if not re.match(time_pattern, end_time):
        return False, "Время окончания должно быть в формате ЧЧ:ММ"

    # Конец позже начала
    try:
        t1 = datetime.strptime(start_time, "%H:%M")
        t2 = datetime.strptime(end_time, "%H:%M")
        if t1 >= t2:
            return False, "Время окончания должно быть позже времени начала"
    except ValueError:
        return False, "Некорректный формат времени"

    # Аудитория
    if not room or not isinstance(room, str) or not room.strip():
        return False, "Аудитория должна быть непустой строкой"

    # Тип занятия
    valid_types = ("лекция", "практика", "лабораторная")
    if lesson_type not in valid_types:
        return False, "Неверный тип занятия"

    return True, None


# Добавление группы
@app.route('/add_group', methods=['POST'])
def add_group():
    logging.debug("Обработка запроса: /add_group")

    faculty = request.form['faculty']
    course = request.form['course']
    name = request.form['name']

    is_valid, message = validate_group(faculty, course, name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO groups (faculty, course, name) VALUES (?, ?, ?)",
            (faculty, course, name)
        )
        conn.commit()

    return redirect(url_for('groups'))


# Обновление группы
@app.route('/update_group', methods=['POST'])
def update_group():
    logging.debug("Обработка запроса: /update_group")

    group_id = request.form['id']
    faculty = request.form['faculty']
    course = request.form['course']
    name = request.form['name']

    is_valid, message = validate_group(faculty, course, name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE groups SET faculty = ?, course = ?, name = ? WHERE id = ?",
            (faculty, course, name, group_id)
        )
        conn.commit()

    return redirect(url_for('groups'))


# Удаление группы
@app.route('/delete_group', methods=['POST'])
def delete_group():
    logging.debug("Обработка запроса: /delete_group")
    group_id = request.form['id']

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        conn.commit()

    return redirect(url_for('groups'))


# Добавление предмета
@app.route('/add_subject', methods=['POST'])
def add_subject():
    logging.debug("Обработка запроса: /add_subject")

    name = request.form['name']
    is_valid, message = validate_subject(name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        conn.commit()

    return redirect(url_for('subjects'))


# Обновление предмета
@app.route('/update_subject', methods=['POST'])
def update_subject():
    logging.debug("Обработка запроса: /update_subject")

    subject_id = request.form['id']
    name = request.form['name']

    is_valid, message = validate_subject(name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE subjects SET name = ? WHERE id = ?",
            (name, subject_id)
        )
        conn.commit()

    return redirect(url_for('subjects'))


# Удаление предмета
@app.route('/delete_subject', methods=['POST'])
def delete_subject():
    logging.debug("Обработка запроса: /delete_subject")

    subject_id = request.form['id']

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()

    return redirect(url_for('subjects'))


# Добавление преподавателя
@app.route('/add_teacher', methods=['POST'])
def add_teacher():
    logging.debug("Обработка запроса: /add_teacher")

    first_name = request.form['first_name']
    last_name = request.form['last_name']

    is_valid, message = validate_teacher(first_name, last_name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO teachers (first_name, last_name) VALUES (?, ?)",
            (first_name, last_name)
        )
        conn.commit()

    return redirect(url_for('teachers'))


# Обновление преподавателя
@app.route('/update_teacher', methods=['POST'])
def update_teacher():
    logging.debug("Обработка запроса: /update_teacher")

    teacher_id = request.form['id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']

    is_valid, message = validate_teacher(first_name, last_name)
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE teachers SET first_name = ?, last_name = ? WHERE id = ?",
            (first_name, last_name, teacher_id)
        )
        conn.commit()

    return redirect(url_for('teachers'))


# Удаление преподавателя
@app.route('/delete_teacher', methods=['POST'])
def delete_teacher():
    logging.debug("Обработка запроса: /delete_teacher")

    teacher_id = request.form['id']

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
        conn.commit()

    return redirect(url_for('teachers'))


# Добавление записи расписания
@app.route('/add_schedule', methods=['POST'])
def add_schedule():
    logging.debug("Обработка запроса: /add_schedule")

    group_id = request.form['group_id']
    subject_id = request.form['subject_id']
    teacher_id = request.form['teacher_id']
    day_of_week = request.form['day_of_week']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    room = request.form['room']
    lesson_type = request.form['lesson_type']

    is_valid, message = validate_schedule_entry(
        group_id, subject_id, teacher_id,
        day_of_week, start_time, end_time,
        room, lesson_type
    )
    if not is_valid:
        return message, 400

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO schedule
               (group_id, subject_id, teacher_id, day_of_week, start_time, end_time, room, lesson_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, subject_id, teacher_id, day_of_week, start_time, end_time, room, lesson_type)
        )
        conn.commit()

    return redirect(url_for('schedule'))


# Удаление записи расписания
@app.route('/delete_schedule', methods=['POST'])
def delete_schedule():
    logging.debug("Обработка запроса: /delete_schedule")

    schedule_id = request.form['id']

    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule WHERE id = ?", (schedule_id,))
        conn.commit()

    return redirect(url_for('schedule'))


@app.route('/groups')
def groups():
    logging.debug("Обработка запроса: /groups")
    with sqlite3.connect("BD/YourBD.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, faculty, course, name FROM groups")
        groups_list = cursor.fetchall()
    return render_template('groups.html', groups=groups_list)


if __name__ == '__main__':
    logging.debug("Запуск Flask приложения")
    app.run(port=6060, debug=True)
