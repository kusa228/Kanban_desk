import sqlite3
from flask import Flask, render_template_string, request, jsonify
import datetime

app = Flask(__name__)


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('kanban.db')
    c = conn.cursor()

    # Таблица колонок
    c.execute('''CREATE TABLE IF NOT EXISTS columns
                 (id INTEGER PRIMARY KEY, title TEXT)''')

    # Таблица задач
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY, title TEXT, column_id INTEGER,
                 FOREIGN KEY(column_id) REFERENCES columns(id))''')

    # Таблица истории
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY, task_id INTEGER, action TEXT,
                 column_from INTEGER, column_to INTEGER, timestamp TEXT,
                 FOREIGN KEY(task_id) REFERENCES tasks(id))''')

    # Заполняем колонки, если их нет
    c.execute("SELECT COUNT(*) FROM columns")
    if c.fetchone()[0] == 0:
        columns = [('To Do',), ('In Progress',), ('Done',)]
        c.executemany("INSERT INTO columns (title) VALUES (?)", columns)

    conn.commit()
    conn.close()


def get_kanban_data():
    conn = sqlite3.connect('kanban.db')
    c = conn.cursor()

    # Получаем колонки
    c.execute("SELECT * FROM columns ORDER BY id")
    columns = c.fetchall()

    kanban_data = {'columns': []}
    for col in columns:
        # Получаем задачи для колонки
        c.execute("SELECT * FROM tasks WHERE column_id = ? ORDER BY id", (col[0],))
        tasks = [{'id': t[0], 'title': t[1]} for t in c.fetchall()]
        kanban_data['columns'].append({
            'id': col[0],
            'title': col[1],
            'tasks': tasks
        })

    conn.close()
    return kanban_data


def get_history():
    conn = sqlite3.connect('kanban.db')
    c = conn.cursor()
    c.execute('''SELECT h.task_id, h.action, c1.title as from_title,
                 c2.title as to_title, h.timestamp
                 FROM history h
                 LEFT JOIN columns c1 ON h.column_from = c1.id
                 LEFT JOIN columns c2 ON h.column_to = c2.id
                 ORDER BY h.timestamp DESC LIMIT 50''')
    history = c.fetchall()
    conn.close()
    return history


# HTML-шаблон с историей
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Канбан-доска с историей</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .board { display: flex; gap: 20px; margin-bottom: 30px; }
        .column { flex: 1; border: 1px solid #ccc; padding: 15px; border-radius: 5px; }
        .column-title { text-align: center; font-weight: bold; margin-bottom: 10px; font-size: 18px; }
        .task { background: #f9f9f9; padding: 10px; margin: 5px 0; border-left: 4px solid #007bff; border-radius: 3px; cursor: move; }
        .add-task { margin-top: 10px; display: flex; gap: 5px; }
        input { padding: 8px; flex: 1; }
        button { padding: 8px 12px; }
        .task-controls { display: flex; justify-content: space-between; margin-top: 5px; }
        .history { border: 1px solid #ddd; padding: 15px; border-radius: 5px; max-height: 300px; overflow-y: auto; }
        .history-item { padding: 5px; border-bottom: 1px solid #eee; }
    </style>
</head>
<body>
    <h1>Канбан-доска</h1>
    <div class="board">
        {% for column in columns %}
        <div class="column" data-column-id="{{ column.id }}">
            <div class="column-title">{{ column.title }}</div>
            <div class="tasks-container">
                {% for task in column.tasks %}
                <div class="task" data-task-id="{{ task.id }}">
                    {{ task.title }}
                    <div class="task-controls">
                        {% if column.id > 1 %}
                        <button onclick="moveTask({{ task.id }}, {{ column.id - 1 }})">←</button>
                        {% endif %}
                        {% if column.id < 3 %}
                        <button onclick="moveTask({{ task.id }}, {{ column.id + 1 }})">→</button>
                        {% endif %}
                        <button onclick="deleteTask({{ task.id }})">×</button>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="add-task">
                <input type="text" id="taskInput_{{ column.id }}" placeholder="Новая задача">
                <button onclick="addTask({{ column.id }})">Добавить</button>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="history">
        <h3>История действий (последние 50)</h3>
        {% for item in history %}
        <div class="history-item">
            Задача #{{ item[0] }}: {{ item[1] }}
            {% if item[2] %}из "{{ item[2] }}"{% endif %}
            {% if item[3] %}в "{{ item[3] }}"{% endif %}
            в {{ item[4] }}
        </div>
        {% endfor %}
    </div>

    <script>
        function addTask(columnId) {
            const input = document.getElementById('taskInput_' + columnId);
            const title = input.value.trim();
            if (!title) return;

            fetch('/add_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({title: title, column_id: columnId})
            })
            .then(response => response.json())
            .then(() => {
                input.value = '';
                location.reload();
            });
        }

        function moveTask(taskId, newColumnId) {
            fetch('/move_task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({task_id: taskId, column_id: newColumnId})
            })
            .then(() => location.reload());
        }

        function deleteTask(taskId) {
            if (confirm('Удалить задачу?')) {
                fetch('/delete_task/' + taskId, { method: 'DELETE' })
                .then(() => location.reload());
            }
        }
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    kanban_data = get_kanban_data()
    history = get_history()
    return render_template_string(HTML_TEMPLATE, columns=kanban_data['columns'], history=history)


@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.get_json()
    conn = sqlite3.connect('kanban.db')
    c = conn.cursor()

    # Добавляем задачу
    c.execute("INSERT INTO tasks (title, column_id) VALUES (?, ?)",
              (data['title'], data['column_id']))
    task_id = c.lastrowid

    # Записываем в историю
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO history (task_id, action, column_from, column_to, timestamp) "
              "VALUES (?, ?, ?, ?, ?)",
              (task_id, 'создана', None, data['column_id'], timestamp))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route('/move_task', methods=['POST'])
def move_task():
 data = request.get_json()
 conn = sqlite3.connect('kanban.db')
 c = conn.cursor()

 # Получаем текущую колонку задачи
 c.execute("SELECT column_id FROM tasks WHERE id = ?", (data['task_id'],))
 result = c.fetchone()
 if not result:
  conn.close()
  return jsonify(success=False)

 current_column = result[0]

 # Обновляем колонку задачи
 c.execute("UPDATE tasks SET column_id = ? WHERE id = ?",
           (data['column_id'], data['task_id']))

 # Записываем в историю
 timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 c.execute("INSERT INTO history (task_id, action, column_from, column_to, timestamp) "
           "VALUES (?, ?, ?, ?, ?)",
           (data['task_id'], 'перемещена', current_column, data['column_id'], timestamp))

 conn.commit()
 conn.close()
 return jsonify(success=True)


@app.route('/delete_task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
 conn = sqlite3.connect('kanban.db')
 c = conn.cursor()

 # Получаем информацию о задаче перед удалением
 c.execute("SELECT column_id FROM tasks WHERE id = ?", (task_id,))
 result = c.fetchone()
 if not result:
  conn.close()
  return jsonify(success=False)

 column_id = result[0]

 # Удаляем задачу
 c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

 # Записываем в историю
 timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 c.execute("INSERT INTO history (task_id, action, column_from, column_to, timestamp) "
           "VALUES (?, ?, ?, ?, ?)",
           (task_id, 'удалена', column_id, None, timestamp))

 conn.commit()
 conn.close()
 return jsonify(success=True)


if __name__ == '__main__':
 # Инициализируем базу данных при запуске
 init_db()

 # Добавляем тестовые данные, если их нет
 conn = sqlite3.connect('kanban.db')
 c = conn.cursor()

 # Проверяем, есть ли задачи в колонке "To Do" (id=1)
 c.execute("SELECT COUNT(*) FROM tasks WHERE column_id = 1")
 if c.fetchone()[0] == 0:
  # Добавляем тестовые задачи
  test_tasks = [
   ('Спланировать структуру проекта', 1),
   ('Написать базовый код', 1),
   ('Реализовать добавление задач', 2)
  ]
  c.executemany("INSERT INTO tasks (title, column_id) VALUES (?, ?)", test_tasks)
  conn.commit()

 conn.close()

 print("Канбан-доска запущена!")
 print("Откройте в браузере: http://127.0.0.1:5000")
 app.run(debug=False, host='127.0.0.1', port=5000)
