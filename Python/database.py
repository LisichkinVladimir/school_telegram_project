"""
Модуль работы с базой данных
"""
import datetime
import sqlalchemy as db_sql
from sqlalchemy.orm import Session
from config import get_data_path

# Место расположения Базы данных
db_path = get_data_path()
file_path = f"{db_path}/data.db"
engine = db_sql.create_engine(f"sqlite:///{file_path}")
meta = db_sql.MetaData()

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
    db_sql.Column("row_data", db_sql.String)                        # сырые данных
)

# Список пользователей
users = db_sql.Table(
    "users", meta,
    db_sql.Column("id", db_sql.Integer, primary_key = True),        # Ключ
    db_sql.Column("class_id", db_sql.Integer, db_sql.ForeignKey("classes.id"), nullable = False)
                                                                    # Класс к которому последний раз делался запрос пользователем
)

# ошибки бота
errors = db_sql.Table(
    "errors", meta,
    db_sql.Column("created", db_sql.DateTime),                      # дата создания
    db_sql.Column("user_id", db_sql.Integer, primary_key = True),   # пользователь
    db_sql.Column("traceback", db_sql.String),                      # стек
    db_sql.Column("update_data", db_sql.String),                    # данные в update
    db_sql.Column("context_chat", db_sql.String),                   # данные в context.chat
    db_sql.Column("context_user", db_sql.String)                    # данные в context.user
)

meta.create_all(engine)
session = Session(engine)

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

def load_from_db(school, new_hash: str) -> bool:
    """
    Процедура загрузки расписания из базы
    """
    from schedule_parser import Department, SchoolClass
    if new_hash is not None:
        schedule_data = session.query(schedules) \
            .filter(schedules.c.hash == school.hash) \
            .filter(schedules.c.deleted is not None) \
            .first()
        if schedule_data is not None:
            # Данные уже загружались
            return True
    schedule_data = session.query(schedules) \
        .filter(schedules.c.hash == new_hash) \
        .filter(schedules.c.deleted is not None) \
        .first()
    if schedule_data is None:
        return False

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
        department: Department = Department(department_data.name)
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

def save_user_class(user_id: int, class_id: int) -> None:
    """
    Сохранение данных о последнем запрошенном пользователем классе
    """
    users_data = session.query(users).filter(users.c.id == user_id).first()
    if users_data is not None:
        stmt = users.update() \
            .where(users.c.id == user_id) \
            .values(
                class_id = class_id

            )
    else:
        stmt = users.insert().values(
            id = user_id,
            class_id = class_id
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

    stmt = errors.insert().values(
        created = datetime.datetime.now(),
        user_id = user_id,
        traceback = escape_sql_text(traceback),
        update_data = escape_sql_text(update),
        context_chat = escape_sql_text(context_chat),
        context_user = escape_sql_text(context_user)
    )
    session.execute(stmt)
    session.commit()
