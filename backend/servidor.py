import os

import uvicorn


def iniciar():
    direccion = os.getenv("HOST", "127.0.0.1")
    if direccion not in ("127.0.0.1", "192.168.50.10", "0.0.0.0"):
        raise ValueError("HOST no corresponde al montaje local.")
    uvicorn.run(
        "backend.aplicacion:crear_aplicacion",
        factory=True,
        host=direccion,
        port=int(os.getenv("PORT", "3000")),
        workers=1,
        proxy_headers=False,
        server_header=False,
        limit_concurrency=128,
        backlog=128,
        timeout_keep_alive=5,
        access_log=False,
    )


if __name__ == "__main__":
    iniciar()
