import { DatabaseSync } from "node:sqlite";

function migrarTablasAnteriores(baseDatos) {
  const tablas = [
    [
      "users",
      "usuarios",
      { username: "usuario", password_hash: "hash_clave", active: "activo" },
    ],
    [
      "persons",
      "personas",
      {
        photo: "foto",
        embedding: "vector_facial",
        model: "modelo",
        active: "activo",
        created_at: "fecha_creacion",
        created_by: "creado_por",
      },
    ],
    [
      "events",
      "eventos",
      {
        person_id: "persona_id",
        user_id: "usuario_id",
        score: "similitud",
        threshold: "umbral",
        node: "nodo",
        model: "modelo",
        timestamp: "fecha_hora",
        duration_seconds: "duracion_segundos",
      },
    ],
  ];
  const existeVersionAnterior = baseDatos
    .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'")
    .get();
  if (!existeVersionAnterior) return;
  baseDatos.exec("BEGIN IMMEDIATE");
  try {
    for (const [anterior, actual, columnas] of tablas) {
      baseDatos.exec(`ALTER TABLE ${anterior} RENAME TO ${actual}`);
      for (const [columnaAnterior, columnaActual] of Object.entries(columnas))
        baseDatos.exec(
          `ALTER TABLE ${actual} RENAME COLUMN ${columnaAnterior} TO ${columnaActual}`,
        );
    }
    baseDatos.exec(`
      DROP INDEX IF EXISTS events_time;
      DROP INDEX IF EXISTS events_person;
      DROP TRIGGER IF EXISTS immutable_events_update;
      DROP TRIGGER IF EXISTS immutable_events_delete;
      COMMIT;
    `);
  } catch (error) {
    baseDatos.exec("ROLLBACK");
    throw error;
  }
}

export function abrirBaseDatos(ruta) {
  const baseDatos = new DatabaseSync(ruta);
  baseDatos.exec(
    "PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;",
  );
  if (
    [
      ...baseDatos.prepare("PRAGMA table_info(personas)").all(),
      ...baseDatos.prepare("PRAGMA table_info(persons)").all(),
    ].some((columna) => columna.name === "cui")
  ) {
    baseDatos.close();
    throw new Error(
      "La base existente corresponde a la versión DPI. Consérvela como respaldo y use una base nueva para carnés.",
    );
  }
  migrarTablasAnteriores(baseDatos);
  baseDatos.exec(`
    PRAGMA foreign_keys = ON;
    PRAGMA journal_mode = WAL;
    PRAGMA busy_timeout = 5000;
    CREATE TABLE IF NOT EXISTS usuarios (
      id INTEGER PRIMARY KEY, usuario TEXT NOT NULL UNIQUE CHECK(length(usuario) BETWEEN 3 AND 30),
      hash_clave TEXT NOT NULL, nombres TEXT NOT NULL CHECK(length(nombres) BETWEEN 2 AND 100),
      rol TEXT NOT NULL CHECK(rol IN ('ADMINISTRADOR','OPERADOR')),
      activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1)), version INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS personas (
      id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE CHECK(length(uuid)=36),
      nombres TEXT NOT NULL CHECK(length(nombres) BETWEEN 2 AND 100),
      apellidos TEXT NOT NULL CHECK(length(apellidos) BETWEEN 2 AND 100),
      foto TEXT NOT NULL CHECK(length(foto)<=400000),
      vector_facial TEXT NOT NULL, modelo TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1)),
      fecha_creacion TEXT NOT NULL, creado_por INTEGER NOT NULL REFERENCES usuarios(id)
    );
    CREATE TABLE IF NOT EXISTS eventos (
      id INTEGER PRIMARY KEY, persona_id INTEGER NOT NULL REFERENCES personas(id),
      usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
      uuid TEXT NOT NULL, nombres TEXT NOT NULL, apellidos TEXT NOT NULL,
      tipo TEXT CHECK(tipo IN ('ENTRADA','SALIDA')),
      estado TEXT NOT NULL CHECK(estado IN ('AUTORIZADO','RECHAZADO')),
      similitud REAL NOT NULL CHECK(similitud BETWEEN -1 AND 1), umbral REAL NOT NULL CHECK(umbral BETWEEN -1 AND 1),
      nodo TEXT NOT NULL, modelo TEXT NOT NULL,
      fecha_hora TEXT NOT NULL, duracion_segundos REAL,
      CHECK((estado='RECHAZADO' AND tipo IS NULL) OR (estado='AUTORIZADO' AND tipo IS NOT NULL))
    );
    CREATE TABLE IF NOT EXISTS fotografias_rechazos (
      evento_id INTEGER PRIMARY KEY REFERENCES eventos(id),
      foto BLOB NOT NULL CHECK(typeof(foto)='blob' AND length(foto) BETWEEN 20 AND 16384)
    );
    CREATE INDEX IF NOT EXISTS eventos_fecha ON eventos(fecha_hora);
    CREATE INDEX IF NOT EXISTS eventos_persona ON eventos(persona_id, id DESC);
    CREATE TRIGGER IF NOT EXISTS impedir_actualizacion_eventos BEFORE UPDATE ON eventos
      BEGIN SELECT RAISE(ABORT, 'Bitácora inmutable'); END;
    CREATE TRIGGER IF NOT EXISTS impedir_eliminacion_eventos BEFORE DELETE ON eventos
      BEGIN SELECT RAISE(ABORT, 'Bitácora inmutable'); END;
  `);
  return baseDatos;
}
