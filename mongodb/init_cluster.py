import time
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure

CONFIG_RS = ("configReplSet", 27019, "configsvr:27019", True)
SHARDS = [
    ("shard1ReplSet", 27018, "shard1:27018"),
    ("shard2ReplSet", 27020, "shard2:27020"),
]
MONGOS_PORT = 28017


def wait_connectable(port, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            c = MongoClient(f"mongodb://localhost:{port}",
                            directConnection=True, serverSelectionTimeoutMS=1500)
            c.admin.command("ping")
            c.close()
            return
        except (ConnectionFailure, OperationFailure):
            time.sleep(2)
    raise TimeoutError(f"El nodo en localhost:{port} no respondio en {timeout}s")


def initiate_replica_set(rs_name, port, member_host, is_config=False):
    client = MongoClient(f"mongodb://localhost:{port}", directConnection=True,
                         serverSelectionTimeoutMS=3000)
    config = {
        "_id": rs_name,
        "members": [{"_id": 0, "host": member_host}],
    }
    if is_config:
        config["configsvr"] = True

    try:
        client.admin.command("replSetInitiate", config)
        print(f"  [ok] rs.initiate ejecutado en {rs_name} ({member_host})")
    except OperationFailure as e:
        if e.code == 23 or "already initialized" in str(e).lower():
            print(f"  [=] {rs_name} ya estaba iniciado, se omite")
        else:
            raise
    finally:
        client.close()


def wait_for_primary(port, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            c = MongoClient(f"mongodb://localhost:{port}", directConnection=True,
                            serverSelectionTimeoutMS=1500)
            hello = c.admin.command("hello")
            c.close()
            if hello.get("isWritablePrimary"):
                return
        except (ConnectionFailure, OperationFailure):
            pass
        time.sleep(2)
    raise TimeoutError(f"El nodo en localhost:{port} no llego a PRIMARY en {timeout}s")


def add_shards():
    client = MongoClient(f"mongodb://localhost:{MONGOS_PORT}",
                         serverSelectionTimeoutMS=5000)
    for rs_name, _, member_host in SHARDS:
        shard_uri = f"{rs_name}/{member_host}"
        try:
            client.admin.command("addShard", shard_uri)
            print(f"  [ok] shard agregado: {shard_uri}")
        except OperationFailure as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"  [=] shard {shard_uri} ya estaba registrado")
            else:
                raise
    client.close()


def print_status():
    client = MongoClient(f"mongodb://localhost:{MONGOS_PORT}",
                         serverSelectionTimeoutMS=5000)
    shards = list(client.config.shards.find({}))
    print("\n Shards registrados (config.shards)")
    for s in shards:
        print(f"  {s['_id']:16s} -> {s['host']}")
    client.close()


def main():
    print("Esperando a que los nodos acepten conexiones")
    for _, port, *_ in [CONFIG_RS] + SHARDS:
        wait_connectable(port)
    wait_connectable(MONGOS_PORT)

    print("Iniciando replica set del config server")
    rs_name, port, host, is_cfg = CONFIG_RS
    initiate_replica_set(rs_name, port, host, is_config=is_cfg)
    wait_for_primary(port)
    print(f"   {rs_name} PRIMARY listo.")

    print("Iniciando replica sets de los shards")
    for rs_name, port, host in SHARDS:
        initiate_replica_set(rs_name, port, host)
        wait_for_primary(port)
        print(f"   {rs_name} PRIMARY listo.")

    print("Registrando shards en mongos")
    add_shards()

    print_status()
    print("\nCluster inicializado. Siguiente paso: python enable_sharding.py")


if __name__ == "__main__":
    main()
