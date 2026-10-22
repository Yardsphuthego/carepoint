import os


if os.environ.get("DB_ENGINE", "django.db.backends.mysql") == "django.db.backends.mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
