"""
Модуль работы с базой данных
"""
import datetime
from hashlib import md5
import logging
import traceback
import sqlalchemy as db_sql
from sqlalchemy.orm import Session
from config import get_data_path

# Место расположения Базы данных
db_path = get_data_path()
file_path = f"{db_path}/data.db"
engine = db_sql.create_engine(f"sqlite:///{file_path}")
meta = db_sql.MetaData()
session = Session(engine)

# Список школ
schools = db_sql.Table(
    "schools", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("name", db_sql.String, nullable = False),         # Название
    db_sql.Column("deleted", db_sql.DateTime)                       # дата удаления
)

# Список корпусов школы
departments = db_sql.Table(
    "departments", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("school_id", db_sql.Integer, db_sql.ForeignKey("schools.id"), nullable = False),
                                                                    # Ссылка на школу
    db_sql.Column("name", db_sql.String, nullable = False),         # Название
    db_sql.Column("sequence", db_sql.Integer, nullable = False),    # Порядковый номер
    db_sql.Column("deleted", db_sql.DateTime)                       # дата удаления
)

# Расписания школы
schedules = db_sql.Table(
    "schedules", meta,
    db_sql.Column("hash", db_sql.String, primary_key = True),       # Ключ
    db_sql.Column("school_id", db_sql.Integer, db_sql.ForeignKey("schools.id"), nullable = False),
                                                                    # Ссылка на школу
    db_sql.Column("name", db_sql.String),                           # Название
    db_sql.Column("deleted", db_sql.DateTime)                       # дата удаления
)

# Список классов
classes = db_sql.Table(
    "classes", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("department_id", db_sql.Integer, db_sql.ForeignKey("departments.id"), nullable = False),
                                                                    # Ссылка на корпус школы
    db_sql.Column("name", db_sql.String, nullable = False),         # Название
    db_sql.Column("number", db_sql.Integer),                        # Номер класса
    db_sql.Column("link", db_sql.String),                           # url с расписанием класса на неделю
    db_sql.Column("sequence", db_sql.Integer, nullable = False),    # Порядковый номер
    db_sql.Column("deleted", db_sql.DateTime)                       # дата удаления
)

# Расписания по неделям класса
week_schedules = db_sql.Table(
    "week_schedules", meta,
    db_sql.Column("hash", db_sql.String, primary_key = True),       # Ключ
    db_sql.Column("schedule_hash", db_sql.String, db_sql.ForeignKey("schedules.hash"), nullable = False),
                                                                    # Ссылка на рабочее расписание класса
    db_sql.Column("class_id", db_sql.Integer, db_sql.ForeignKey("classes.id"), nullable = False),
                                                                    # Ссылка на класс
    db_sql.Column("created", db_sql.String),						# дата создания
	db_sql.Column("parse_result", db_sql.Boolean, nullable = False),# Результат разбора
	db_sql.Column("parse_error", db_sql.String)						# Описание ошибки разбора
)

# Идентификатор урока
lessons_ident = db_sql.Table(
    "lessons_ident", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("week", db_sql.Integer, nullable = False),        # чередование по неделям
    db_sql.Column("hour_start", db_sql.String),					    # начало урока
    db_sql.Column("day_of_week", db_sql.String),				    # день недели
    db_sql.Column("day_number", db_sql.Integer)				        # номер дня недели
)

connection = engine.connect()
lesson_data = connection.execute(db_sql.text("select * from lessons where id=-1"))
if "is_group" not in lesson_data.keys():
    connection.execute(db_sql.text("alter table lessons add is_group BOOLEAN"))

# Список уроков
lessons = db_sql.Table(
    "lessons", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("ident_id", db_sql.Integer, db_sql.ForeignKey("lessons_ident.id"), nullable = False),
                                                                    # Идентификатор урока
    db_sql.Column("week_schedule_hash", db_sql.String, db_sql.ForeignKey("week_schedules.hash"), nullable = False),
                                                                    # Ссылка на расписание
    db_sql.Column("hour_end", db_sql.String),					    # окончание урока
    db_sql.Column("name", db_sql.String, nullable = False),         # Название урока
    db_sql.Column("office", db_sql.String),                         # кабинет
    db_sql.Column("group_name", db_sql.String),                     # группа
    db_sql.Column("teacher", db_sql.String),                        # преподаватель
    db_sql.Column("row_data", db_sql.String),                       # сырые данных
    db_sql.Column("is_group", db_sql.Boolean)                       # Признак группы
)

user_data = connection.execute(db_sql.text("select * from users where id=-1"))
if "name" not in user_data.keys():
    connection.execute(db_sql.text("alter table users add name VARCHAR"))
if "updated" not in user_data.keys():
    connection.execute(db_sql.text("alter table users add updated DATETIME"))

# Список пользователей
users = db_sql.Table(
    "users", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("class_id", db_sql.Integer, db_sql.ForeignKey("classes.id"), nullable = False),
                                                                    # Класс к которому последний раз делался запрос пользователем
    db_sql.Column("name", db_sql.String),                           # Имя пользователя
    db_sql.Column("updated", db_sql.DateTime)                       # дата обновления
)

error_data = connection.execute(db_sql.text("select * from errors where created=0"))
if "trace_hash" not in error_data.keys():
    connection.execute(db_sql.text("alter table errors add trace_hash VARCHAR"))
if "error_count" not in error_data.keys():
    connection.execute(db_sql.text("alter table errors add error_count INTEGER"))
# ошибки бота
errors = db_sql.Table(
    "errors", meta,
    db_sql.Column("created", db_sql.DateTime, primary_key = True),  # дата создания
    db_sql.Column("user_id", db_sql.Integer),                       # пользователь
    db_sql.Column("traceback", db_sql.String),                      # стек
    db_sql.Column("update_data", db_sql.String),                    # данные в update
    db_sql.Column("context_chat", db_sql.String),                   # данные в context.chat
    db_sql.Column("context_user", db_sql.String),                   # данные в context.user
    db_sql.Column("trace_hash", db_sql.String),                     # Хеш стека
    db_sql.Column("error_count", db_sql.Integer)                    # Количество повторений
)

meta.create_all(engine)

def delete_old_schedule(school_hash: str) -> None:
    """"
    Удаление старых расписаний и уроков
    """
    # Удалим лишнее в lessons_ident/lessons/week_schedules
    schedule_data = session.query(schedules) \
        .filter(schedules.c.hash != school_hash) \
        .filter(schedules.c.deleted != None)
    for schedule in schedule_data:
        schedule_hash = schedule.hash
        try:
            # удалить lessons - уроки
            sql = "from lessons where week_schedule_hash in " + \
                "(select hash from week_schedules where schedule_hash = '" + schedule_hash + "')"
            lessons_data = connection.execute(db_sql.text("select * " + sql))
            if lessons_data and len(lessons_data.all()) > 0:
                connection.execute(db_sql.text("delete " + sql))
                session.commit()
            # удалить week_schedules - расписания на неделю
            sql = "from week_schedules where schedule_hash = '" + schedule_hash + "'"
            schedule_data = connection.execute(db_sql.text("select * " + sql))
            if schedule_data and len(week_schedules.all()) > 0:
                connection.execute(db_sql.text("delete " + sql))
                session.commit()
        except:
            tb_list = traceback.format_exception()
            tb_string = "".join(tb_list)
            logging.error(f"Error info:{tb_string}")
            save_error(0, tb_string, "", "", "")

def save_to_db(school) -> None:
    """
    Процедура сохранения объекта школа в базе данных
    """
    # Добавление/изменение школы
    if session.query(schools).filter_by(id = school.id).first() is not None:
        stmt = schools.update().where(schools.c.id == school.id).where(schools.c.name != school.name).values(name = school.name)
    else:
        stmt = schools.insert().values(
            id = school.id,
            name = school.name
        )
    session.execute(stmt)

    department_list = []
    # Добавление/изменение подразделений школы
    for i, department in enumerate(school.departments):
        department_list.append(department.id)
        if session.query(departments).filter_by(id = department.id).first() is not None:
            stmt = departments.update() \
                .where(departments.c.id == department.id) \
                .values(
                    name = department.name,
                    school_id = school.id,
                    sequence = i,
                    deleted = None
                )
        else:
            stmt = departments.insert().values(
                id = department.id,
                name = department.name,
                sequence = i,
                school_id = school.id
            )
        session.execute(stmt)
        # Добавление/изменение классов подразделений школы
        for j, class_ in enumerate(department.class_list):
            if session.query(classes).filter_by(id = class_.id).first() is not None:
                stmt = classes.update() \
                    .where(classes.c.id == class_.id).values(
                        name = class_.name,
                        department_id = department.id,
                        number = class_.number,
                        link = class_.link,
                        sequence = j,
                        deleted = None
                    )
            else:
                stmt = classes.insert().values(
                    id = class_.id,
                    name = class_.name,
                    department_id = department.id,
                    number = class_.number,
                    sequence = j,
                    link = class_.link
                )
            session.execute(stmt)

    # Удалим лишние подразделения
    stmt = departments.update() \
        .where(departments.c.school_id != school.id)  \
        .where(departments.c.id.in_(department_list)) \
        .where(departments.c.deleted == None) \
        .values(
            deleted = datetime.datetime.now()
    )
    session.execute(stmt)

    # Добавление/изменение расписания школы
    if session.query(schedules).filter_by(hash = school.hash).first() is not None:
        stmt = schedules.update() \
            .where(schedules.c.hash == school.hash) \
            .values(
                name = school.schedule_name,
                school_id = school.id

            )
    else:
        stmt = schedules.insert().values(
            hash = school.hash,
            name = school.schedule_name,
            school_id = school.id
        )
    session.execute(stmt)

    # Удалим лишние расписания
    stmt = schedules.update() \
        .where(schedules.c.hash != school.hash)  \
        .where(schedules.c.school_id == school.id) \
        .where(schedules.c.deleted == None) \
        .values(
            deleted = datetime.datetime.now()
    )
    session.execute(stmt)
    session.commit()

    # Удалим лишнее в lessons_ident/lessons/week_schedules
    delete_old_schedule(school.hash)

def load_from_db(school, new_hash: str) -> bool:
    """
    Процедура загрузки расписания из базы
    """
    from schedule_parser import Department, SchoolClass
    schedule_data_for_hash = None
    if school.hash is not None and school.hash != '':
        schedule_data_for_hash = session.query(schedules) \
            .filter(schedules.c.hash == school.hash) \
            .filter(schedules.c.deleted is not None) \
            .first()
        if schedule_data_for_hash is None:
            # Данные еше не загружались
            return False
    # Проверяем по new_hash
    logging.info(f"find in schedules hash = {new_hash}")
    schedule_data = session.query(schedules) \
        .filter(schedules.c.hash == new_hash) \
        .filter(schedules.c.deleted is not None) \
        .first()
    if schedule_data is None:
        return False
    if schedule_data_for_hash is not None:
        # Данные уже загружались
        return True

    school.schedule_name = schedule_data.name

    school_data = session.query(schools) \
        .filter(schools.c.id == schedule_data.school_id) \
        .filter(schools.c.deleted is not None) \
        .first()
    school.id = school_data.id
    school.name = school_data.name

    # Загрузка подразделений
    department_list = session.query(departments) \
        .filter(departments.c.school_id == school.id) \
        .filter(departments.c.deleted is not None) \
        .order_by(departments.c.sequence)
    for department_data in department_list:
        department: Department = Department(department_data.name, school)
        # Загрузка классов
        school_list = session.query(classes) \
            .filter(classes.c.department_id == department.id) \
            .filter(classes.c.deleted is not None) \
            .order_by(classes.c.sequence)
        for school_data in school_list:
            school_class: SchoolClass = SchoolClass(school_data.name, school_data.link, department)
            department.add_class(school_class)
        school.add_department(department)

    school.hash = new_hash
    return True

def save_pdf_to_db(week_schedule) -> bool:
    """
    Процедура сохранения pdf расписания в базе данных
    """

    def save_lesson(lesson, is_group: bool = False):
        """
        Сохранение данных об уроке
        """
        if session.query(lessons_ident).filter_by(id = lesson.ident.id).first() is not None:
            stmt = lessons_ident.update().where(lessons_ident.c.id == lesson.ident.id) \
                .values(
                    week = lesson.ident.week,
                    hour_start = lesson.ident.hour_start,
                    day_of_week = lesson.ident.day_of_week,
                    day_number = lesson.ident.day_of_week_number
                )
        else:
            stmt = lessons_ident.insert().values(
                    id = lesson.ident.id,
                    week = lesson.ident.week,
                    hour_start = lesson.ident.hour_start,
                    day_of_week = lesson.ident.day_of_week,
                    day_number = lesson.ident.day_of_week_number
            )
        session.execute(stmt)

        if session.query(lessons).filter_by(id = lesson.id).first() is not None:
            stmt = lessons.update().where(lessons.c.id == lesson.id) \
                .values(
                    ident_id = lesson.ident.id,
                    week_schedule_hash = week_schedule.hash,
                    hour_end = lesson.hour_end,
                    name = lesson.name,
                    office = lesson.office,
                    group_name = lesson.group,
                    teacher = lesson.teacher,
                    row_data = lesson.row_data,
                    is_group = is_group
                )
        else:
            stmt = lessons.insert().values(
                    id = lesson.id,
                    ident_id = lesson.ident.id,
                    week_schedule_hash = week_schedule.hash,
                    hour_end = lesson.hour_end,
                    name = lesson.name,
                    office = lesson.office,
                    group_name = lesson.group,
                    teacher = lesson.teacher,
                    row_data = lesson.row_data,
                    is_group = is_group
            )
        session.execute(stmt)

        # Сохранение групп
        for lesson in lesson.groups:
            save_lesson(lesson, is_group = True)

    if week_schedule.school_class is None:
        return False
    # Добавление/изменение недельного расписания
    last_parse_result = None
    if week_schedule.last_parse_error:
        last_parse_result = week_schedule.last_parse_result
    if session.query(week_schedules).filter_by(hash = week_schedule.hash).first() is not None:
        stmt = week_schedules.update().where(week_schedules.c.hash == week_schedule.hash).values(
            schedule_hash = week_schedule.school_class.department.school.hash,
            class_id = week_schedule.school_class.id,
            created = week_schedule.created,
            parse_result = last_parse_result,
            parse_error = week_schedule.last_parse_error)
    else:
        stmt = week_schedules.insert().values(
            hash = week_schedule.hash,
            schedule_hash = week_schedule.school_class.department.school.hash,
            class_id = week_schedule.school_class.id,
            created = week_schedule.created,
            parse_result = last_parse_result,
            parse_error = week_schedule.last_parse_error
        )
    session.execute(stmt)

    # Записать данные в таблицу lessons/lessons_ident
    for week in week_schedule.week_list():
        for day_of_week in week_schedule.day_of_week_list(week):
            for lesson in week_schedule.lesson_list(week, day_of_week):
                save_lesson(lesson)

    session.commit()

    # Удалим лишнее в lessons_ident/lessons/week_schedules
    delete_old_schedule(week_schedule.school_class.department.school.hash)


def load_pdf_from_db(week_schedule, new_hash: str) -> bool:
    """
    Процедура загрузки pdf расписания из базы
    """
    from week_pdf_parser import LessonIdent, Lesson
    schedule_data_for_hash = None
    if week_schedule.hash is not None and week_schedule.hash != '':
        schedule_data_for_hash = session.query(week_schedules) \
            .filter(week_schedules.c.hash == week_schedule.hash) \
            .filter(week_schedules.c.parse_result == True) \
            .first()
        if schedule_data_for_hash is None:
            # Данные еще не загружались
            return False
    schedule_data = session.query(week_schedules) \
        .filter(week_schedules.c.hash == new_hash) \
        .filter(week_schedules.c.parse_result == True) \
        .first()
    if schedule_data is None:
        return False
    if schedule_data_for_hash is not None:
        # Данные уже загружались
        return True

    # Загрузка WeekSchedule
    week_schedule.created = schedule_data.created
    week_schedule.hash = schedule_data.hash
    week_schedule.last_parse_result = schedule_data.parse_result
    week_schedule.last_parse_error = schedule_data.parse_error

    # Загрузка lesson
    sql = "select l.*, i.week, i.hour_start, i.day_of_week, i.day_number from lessons l join lessons_ident i on l.ident_id=i.id " + \
        "where l.week_schedule_hash = '" + schedule_data.hash + "' " + \
        "order by i.week, i.day_number, i.hour_start, l.hour_end, l.is_group"
    lessons_data = connection.execute(db_sql.text(sql))
    has_lesson = False
    for lesson_data in lessons_data:
        lesson_ident = LessonIdent(lesson_data.week, lesson_data.hour_start, lesson_data.day_of_week, lesson_data.day_number)
        new_lesson = Lesson(
                ident = lesson_ident,
                name = lesson_data.name,
                office = lesson_data.office,
                group = lesson_data.group_name,
                teacher = lesson_data.teacher,
                class_name = None if week_schedule.school_class is None else week_schedule.school_class.name,
                row_data = lesson_data.row_data)
        if lesson_data.hour_end is not None:
            new_lesson.hour_end = lesson_data.hour_end
        if lesson_data.is_group is None or lesson_data.is_group == False:
            week_schedule.add_lesson(lesson_ident, new_lesson)
        else:
            week_schedule.add_group_lesson(lesson_ident, new_lesson)
        has_lesson = True

    return has_lesson

def save_user_class(user_id: int, class_id: int, user_name: str) -> None:
    """
    Сохранение данных о последнем запрошенном пользователем классе
    """
    users_data = session.query(users).filter(users.c.id == user_id).first()
    if users_data is not None:
        stmt = users.update() \
            .where(users.c.id == user_id) \
            .values(
                class_id = class_id,
                name = user_name,
                updated = datetime.datetime.now()
            )
    else:
        stmt = users.insert().values(
            id = user_id,
            class_id = class_id,
            name = user_name,
            updated = datetime.datetime.now()
        )
    session.execute(stmt)
    session.commit()

def get_user_class(user_id) -> int:
    """"
    Получение информации о последнем запрошенном пользователем классе
    """
    users_data = session.query(users).filter(users.c.id == user_id).first()
    if users_data is None:
        return None
    else:
        return users_data.class_id

def save_error(user_id: int, traceback: str, update: str, context_chat: str, context_user: str) -> None:
    """"
    Сохранение информации об ошибка
    """
    def escape_sql_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("_", "\\_").replace("'", "''")

    traceback = escape_sql_text(traceback)
    data_for_hash = traceback.encode('utf-8', errors='ignore')
    trace_hash = md5(data_for_hash).hexdigest()
    error_data = session.query(errors).filter(errors.c.trace_hash == trace_hash).first()
    if error_data is not None:
        stmt = errors.update() \
            .where(errors.c.trace_hash == trace_hash) \
            .values(
                {
                    errors.c.created: datetime.datetime.now(),
                    errors.c.user_id: user_id,
                    errors.c.update_data: escape_sql_text(update),
                    errors.c.context_chat: escape_sql_text(context_chat),
                    errors.c.context_user: escape_sql_text(context_user),
                    errors.c.error_count: error_data.error_count + 1
                }
            )
    else:
        stmt = errors.insert().values(
            created = datetime.datetime.now(),
            user_id = user_id,
            traceback = traceback,
            update_data = escape_sql_text(update),
            context_chat = escape_sql_text(context_chat),
            context_user = escape_sql_text(context_user),
            trace_hash = trace_hash,
            error_count = 1
        )
    session.execute(stmt)
    session.commit()
