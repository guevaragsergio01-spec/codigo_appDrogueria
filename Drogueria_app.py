"""
Sistema de inventario - Droguería Arandia
Conexión a MySQL y gestión por consola.

Requisitos:
    pip install mysql-connector-python

Antes de ejecutar:
    1. Haber corrido ddl.sql y dml.sql en MySQL.
    2. Ajustar la configuración (abajo) o definir las variables de entorno
       DB_HOST, DB_PORT, DB_USER, DB_PASSWORD y DB_NAME.
"""

import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation

import mysql.connector
from mysql.connector import Error

# ----------------------------------------------------------------------
# Configuración de la conexión
# ----------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Seal2006.U"),  
    "database": os.getenv("DB_NAME", "Drogueria_Arandia"),
}


def conectar():
    """Abre la conexión con MySQL (sin autocommit: se confirma manualmente)."""
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn


# ----------------------------------------------------------------------
# Utilidades de consola
# ----------------------------------------------------------------------
def imprimir_tabla(columnas, filas):
    """Imprime los resultados de una consulta como tabla alineada."""
    if not filas:
        print("\n  (sin resultados)\n")
        return
    textos = [[("" if v is None else str(v)) for v in fila] for fila in filas]
    anchos = [
        max(len(str(col)), *(len(f[i]) for f in textos))
        for i, col in enumerate(columnas)
    ]
    linea = "+-" + "-+-".join("-" * a for a in anchos) + "-+"
    print(linea)
    print("| " + " | ".join(str(c).ljust(a) for c, a in zip(columnas, anchos)) + " |")
    print(linea)
    for fila in textos:
        print("| " + " | ".join(v.ljust(a) for v, a in zip(fila, anchos)) + " |")
    print(linea)
    print(f"{len(filas)} registro(s)\n")


def consultar(conn, sql, params=None):
    """Ejecuta un SELECT y devuelve (columnas, filas)."""
    cur = conn.cursor()
    cur.execute(sql, params or ())
    columnas = [d[0] for d in cur.description]
    filas = cur.fetchall()
    cur.close()
    return columnas, filas


def leer_texto(mensaje, obligatorio=True, defecto=None):
    while True:
        sufijo = f" [{defecto}]" if defecto is not None else ""
        valor = input(f"{mensaje}{sufijo}: ").strip()
        if not valor and defecto is not None:
            return defecto
        if valor or not obligatorio:
            return valor
        print("  Este campo es obligatorio.")


def leer_entero(mensaje, minimo=None, defecto=None):
    while True:
        sufijo = f" [{defecto}]" if defecto is not None else ""
        valor = input(f"{mensaje}{sufijo}: ").strip()
        if not valor and defecto is not None:
            return defecto
        try:
            numero = int(valor)
            if minimo is not None and numero < minimo:
                print(f"  Debe ser un número mayor o igual a {minimo}.")
                continue
            return numero
        except ValueError:
            print("  Ingresa un número entero válido.")


def leer_decimal(mensaje, defecto=None):
    while True:
        sufijo = f" [{defecto}]" if defecto is not None else ""
        valor = input(f"{mensaje}{sufijo}: ").strip()
        if not valor and defecto is not None:
            return defecto
        try:
            numero = Decimal(valor)
            if numero < 0:
                print("  El valor no puede ser negativo.")
                continue
            return numero
        except InvalidOperation:
            print("  Ingresa un número válido (ej. 4500 o 4500.50).")


def leer_si_no(mensaje):
    while True:
        r = input(f"{mensaje} (s/n): ").strip().lower()
        if r in ("s", "si", "sí"):
            return True
        if r in ("n", "no"):
            return False
        print("  Responde s o n.")


def leer_fecha_opcional(mensaje):
    """Pide una fecha AAAA-MM-DD; Enter la deja vacía (NULL)."""
    while True:
        valor = input(f"{mensaje} (AAAA-MM-DD, Enter si no vence): ").strip()
        if not valor:
            return None
        try:
            return datetime.strptime(valor, "%Y-%m-%d").date()
        except ValueError:
            print("  Formato inválido. Ejemplo: 2027-12-31")


def existe(conn, tabla, campo_id, valor):
    _, filas = consultar(conn, f"SELECT 1 FROM {tabla} WHERE {campo_id} = %s", (valor,))
    return bool(filas)


def elegir_id(conn, tabla, campo_id, etiqueta, defecto=None):
    """Muestra el catálogo y pide un id existente."""
    columnas, filas = consultar(conn, f"SELECT {campo_id}, nombre FROM {tabla} ORDER BY {campo_id}")
    imprimir_tabla(columnas, filas)
    while True:
        valor = leer_entero(f"ID de {etiqueta}", minimo=1, defecto=defecto)
        if existe(conn, tabla, campo_id, valor):
            return valor
        print(f"  No existe {etiqueta} con ese ID.")


def elegir_producto(conn):
    """Pide un id_producto existente y devuelve (id, nombre)."""
    while True:
        id_producto = leer_entero("ID del producto", minimo=1)
        _, filas = consultar(
            conn, "SELECT nombre FROM productos WHERE id_producto = %s", (id_producto,)
        )
        if filas:
            return id_producto, filas[0][0]
        print("  No existe un producto con ese ID.")


# ----------------------------------------------------------------------
# 1. Registrar producto
# ----------------------------------------------------------------------
def registrar_producto(conn):
    print("\n--- Registrar producto ---")
    nombre = leer_texto("Nombre del producto")
    id_categoria = elegir_id(conn, "categorias", "id_categoria", "categoría")
    id_proveedor = elegir_id(conn, "proveedores", "id_proveedor", "proveedor")
    precio = leer_decimal("Precio de venta (COP)")
    stock_minimo = leer_entero("Stock mínimo", minimo=0)
    requiere_formula = 1 if leer_si_no("¿Requiere fórmula médica?") else 0

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO productos
           (nombre, id_categoria, id_proveedor, precio, stock_actual, stock_minimo, requiere_formula)
           VALUES (%s, %s, %s, %s, 0, %s, %s)""",
        (nombre, id_categoria, id_proveedor, precio, stock_minimo, requiere_formula),
    )
    conn.commit()
    print(f"\nProducto registrado con ID {cur.lastrowid}. "
          "Registra una entrada de mercancía para cargarle existencias.\n")
    cur.close()


# ----------------------------------------------------------------------
# 2. Actualizar producto
# ----------------------------------------------------------------------
def actualizar_producto(conn):
    print("\n--- Actualizar producto ---")
    id_producto, _ = elegir_producto(conn)
    _, filas = consultar(
        conn,
        """SELECT nombre, id_categoria, id_proveedor, precio, stock_minimo, requiere_formula
           FROM productos WHERE id_producto = %s""",
        (id_producto,),
    )
    nombre, id_cat, id_prov, precio, stock_min, formula = filas[0]
    print("Presiona Enter para conservar el valor actual.\n")

    nombre = leer_texto("Nombre", defecto=nombre)
    if leer_si_no("¿Cambiar categoría?"):
        id_cat = elegir_id(conn, "categorias", "id_categoria", "categoría", defecto=id_cat)
    if leer_si_no("¿Cambiar proveedor?"):
        id_prov = elegir_id(conn, "proveedores", "id_proveedor", "proveedor", defecto=id_prov)
    precio = leer_decimal("Precio", defecto=precio)
    stock_min = leer_entero("Stock mínimo", minimo=0, defecto=stock_min)
    formula = 1 if leer_si_no("¿Requiere fórmula médica?") else 0

    cur = conn.cursor()
    cur.execute(
        """UPDATE productos
           SET nombre=%s, id_categoria=%s, id_proveedor=%s, precio=%s,
               stock_minimo=%s, requiere_formula=%s
           WHERE id_producto=%s""",
        (nombre, id_cat, id_prov, precio, stock_min, formula, id_producto),
    )
    conn.commit()
    cur.close()
    print("\nProducto actualizado.\n")


# ----------------------------------------------------------------------
# 3. Consultar existencias
# ----------------------------------------------------------------------
def consultar_existencias(conn):
    print("\n--- Consultar existencias ---")
    texto = leer_texto("Buscar por nombre (Enter para ver todos)", obligatorio=False)
    columnas, filas = consultar(
        conn,
        """SELECT p.id_producto AS id, p.nombre AS producto, c.nombre AS categoria,
                  pr.nombre AS proveedor, p.precio, p.stock_actual AS stock,
                  p.stock_minimo AS minimo,
                  IF(p.requiere_formula = 1, 'Sí', 'No') AS formula
           FROM productos p
           JOIN categorias c  ON c.id_categoria = p.id_categoria
           JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
           WHERE p.nombre LIKE %s
           ORDER BY p.nombre""",
        (f"%{texto}%",),
    )
    imprimir_tabla(columnas, filas)

    if filas and leer_si_no("¿Ver los lotes de algún producto?"):
        id_producto, nombre = elegir_producto(conn)
        columnas, filas = consultar(
            conn,
            """SELECT numero_lote AS lote, fecha_vencimiento AS vence, cantidad
               FROM lotes WHERE id_producto = %s
               ORDER BY fecha_vencimiento IS NULL, fecha_vencimiento""",
            (id_producto,),
        )
        print(f"\nLotes de: {nombre}")
        imprimir_tabla(columnas, filas)


# ----------------------------------------------------------------------
# 4. Registrar entrada de mercancía (incluye lote y vencimiento)
# ----------------------------------------------------------------------
def registrar_entrada(conn):
    print("\n--- Registrar entrada de mercancía ---")
    id_producto, nombre = elegir_producto(conn)
    print(f"Producto: {nombre}")
    cantidad = leer_entero("Cantidad que ingresa", minimo=1)
    numero_lote = leer_texto("Número de lote")
    fecha_venc = leer_fecha_opcional("Fecha de vencimiento")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id_lote FROM lotes WHERE id_producto=%s AND numero_lote=%s",
            (id_producto, numero_lote),
        )
        lote = cur.fetchone()
        if lote:  # el lote ya existe: se suma la cantidad
            cur.execute(
                "UPDATE lotes SET cantidad = cantidad + %s WHERE id_lote=%s",
                (cantidad, lote[0]),
            )
        else:
            cur.execute(
                """INSERT INTO lotes (id_producto, numero_lote, fecha_vencimiento, cantidad)
                   VALUES (%s, %s, %s, %s)""",
                (id_producto, numero_lote, fecha_venc, cantidad),
            )
        cur.execute(
            "UPDATE productos SET stock_actual = stock_actual + %s WHERE id_producto=%s",
            (cantidad, id_producto),
        )
        cur.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (%s, 'entrada', %s, NOW())",
            (id_producto, cantidad),
        )
        conn.commit()
        print("\nEntrada registrada correctamente.\n")
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


# ----------------------------------------------------------------------
# 5. Registrar salida de producto (descuenta primero lo que vence antes)
# ----------------------------------------------------------------------
def registrar_salida(conn):
    print("\n--- Registrar salida de producto ---")
    id_producto, nombre = elegir_producto(conn)
    _, filas = consultar(
        conn,
        "SELECT requiere_formula, stock_actual FROM productos WHERE id_producto=%s",
        (id_producto,),
    )
    requiere_formula, stock = filas[0]
    print(f"Producto: {nombre} (stock actual: {stock})")

    if requiere_formula and not leer_si_no("Este producto requiere fórmula médica. ¿Se presentó la fórmula?"):
        print("\nSalida cancelada: falta la fórmula médica.\n")
        return

    cantidad = leer_entero("Cantidad a retirar", minimo=1)

    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id_lote, cantidad FROM lotes
               WHERE id_producto=%s AND cantidad > 0
               ORDER BY fecha_vencimiento IS NULL, fecha_vencimiento
               FOR UPDATE""",
            (id_producto,),
        )
        lotes = cur.fetchall()
        disponible = sum(c for _, c in lotes)
        if cantidad > disponible:
            conn.rollback()
            print(f"\nStock insuficiente: solo hay {disponible} unidad(es) disponibles.\n")
            return

        pendiente = cantidad
        for id_lote, cant_lote in lotes:  # FEFO: primero en vencer, primero en salir
            if pendiente == 0:
                break
            tomar = min(pendiente, cant_lote)
            cur.execute(
                "UPDATE lotes SET cantidad = cantidad - %s WHERE id_lote=%s",
                (tomar, id_lote),
            )
            pendiente -= tomar

        cur.execute(
            "UPDATE productos SET stock_actual = stock_actual - %s WHERE id_producto=%s",
            (cantidad, id_producto),
        )
        cur.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (%s, 'salida', %s, NOW())",
            (id_producto, cantidad),
        )
        conn.commit()
        print("\nSalida registrada correctamente.\n")
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()


# ----------------------------------------------------------------------
# 6 y 7. Alertas (usan las vistas de la base de datos)
# ----------------------------------------------------------------------
def alertas_bajo_stock(conn):
    print("\n--- Alertas de bajo stock ---")
    columnas, filas = consultar(conn, "SELECT * FROM vista_bajo_stock")
    imprimir_tabla(columnas, filas)


def proximos_a_vencer(conn):
    print("\n--- Productos próximos a vencer ---")
    columnas, filas = consultar(conn, "SELECT * FROM vista_proximos_vencer")
    imprimir_tabla(columnas, filas)


# ----------------------------------------------------------------------
# 8. Gestionar categorías y proveedores
# ----------------------------------------------------------------------
def gestionar_categorias(conn):
    while True:
        print("\n--- Categorías ---")
        print("1. Listar\n2. Agregar\n3. Editar\n0. Volver")
        op = input("Opción: ").strip()
        if op == "1":
            columnas, filas = consultar(conn, "SELECT id_categoria AS id, nombre FROM categorias ORDER BY id_categoria")
            imprimir_tabla(columnas, filas)
        elif op == "2":
            nombre = leer_texto("Nombre de la nueva categoría")
            cur = conn.cursor()
            cur.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nombre,))
            conn.commit()
            cur.close()
            print("Categoría agregada.")
        elif op == "3":
            id_cat = elegir_id(conn, "categorias", "id_categoria", "categoría")
            nombre = leer_texto("Nuevo nombre")
            cur = conn.cursor()
            cur.execute("UPDATE categorias SET nombre=%s WHERE id_categoria=%s", (nombre, id_cat))
            conn.commit()
            cur.close()
            print("Categoría actualizada.")
        elif op == "0":
            return
        else:
            print("Opción no válida.")


def gestionar_proveedores(conn):
    while True:
        print("\n--- Proveedores ---")
        print("1. Listar\n2. Agregar\n3. Editar\n0. Volver")
        op = input("Opción: ").strip()
        if op == "1":
            columnas, filas = consultar(
                conn, "SELECT id_proveedor AS id, nombre, telefono FROM proveedores ORDER BY id_proveedor"
            )
            imprimir_tabla(columnas, filas)
        elif op == "2":
            nombre = leer_texto("Nombre del proveedor")
            telefono = leer_texto("Teléfono", obligatorio=False) or None
            cur = conn.cursor()
            cur.execute("INSERT INTO proveedores (nombre, telefono) VALUES (%s, %s)", (nombre, telefono))
            conn.commit()
            cur.close()
            print("Proveedor agregado.")
        elif op == "3":
            id_prov = elegir_id(conn, "proveedores", "id_proveedor", "proveedor")
            _, filas = consultar(
                conn, "SELECT nombre, telefono FROM proveedores WHERE id_proveedor=%s", (id_prov,)
            )
            nombre_act, tel_act = filas[0]
            nombre = leer_texto("Nombre", defecto=nombre_act)
            telefono = leer_texto("Teléfono", obligatorio=False, defecto=tel_act or "") or None
            cur = conn.cursor()
            cur.execute(
                "UPDATE proveedores SET nombre=%s, telefono=%s WHERE id_proveedor=%s",
                (nombre, telefono, id_prov),
            )
            conn.commit()
            cur.close()
            print("Proveedor actualizado.")
        elif op == "0":
            return
        else:
            print("Opción no válida.")


def menu_catalogos(conn):
    while True:
        print("\n--- Categorías y proveedores ---")
        print("1. Gestionar categorías\n2. Gestionar proveedores\n0. Volver")
        op = input("Opción: ").strip()
        if op == "1":
            gestionar_categorias(conn)
        elif op == "2":
            gestionar_proveedores(conn)
        elif op == "0":
            return
        else:
            print("Opción no válida.")


# ----------------------------------------------------------------------
# Menú principal
# ----------------------------------------------------------------------
ACCIONES = {
    "1": ("Registrar producto", registrar_producto),
    "2": ("Actualizar producto", actualizar_producto),
    "3": ("Consultar existencias", consultar_existencias),
    "4": ("Registrar entrada de mercancía", registrar_entrada),
    "5": ("Registrar salida de producto", registrar_salida),
    "6": ("Alertas de bajo stock", alertas_bajo_stock),
    "7": ("Próximos a vencer", proximos_a_vencer),
    "8": ("Gestionar categorías y proveedores", menu_catalogos),
}


def main():
    try:
        conn = conectar()
    except Error as e:
        print(f"No se pudo conectar a la base de datos: {e}")
        sys.exit(1)

    print("\n=== Sistema de inventario - Droguería Arandia ===")
    try:
        while True:
            print("\nMENÚ PRINCIPAL")
            for clave, (texto, _) in ACCIONES.items():
                print(f"{clave}. {texto}")
            print("0. Salir")
            opcion = input("Opción: ").strip()

            if opcion == "0":
                print("Hasta pronto.")
                break
            if opcion not in ACCIONES:
                print("Opción no válida.")
                continue
            try:
                ACCIONES[opcion][1](conn)
            except Error as e:
                conn.rollback()
                print(f"\nError de base de datos: {e}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nSesión finalizada.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()