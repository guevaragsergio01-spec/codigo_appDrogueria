import mysql.connector

conn = mysql.connector.connect(
    host="localhost", port=3306, user="root",
    password="Seal2006.U", database="Drogueria_Arandia"
)
print("Conexión exitosa:", conn.is_connected())
conn.close()