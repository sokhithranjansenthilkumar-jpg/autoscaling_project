try:
    import pymysql
except ModuleNotFoundError:
    pymysql = None

if pymysql is not None:
    pymysql.install_as_MySQLdb()
