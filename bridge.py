import base64
import json
import logging
import os
import ssl
from datetime import datetime, timezone

logger = logging.getLogger("mqtt-mongo-bridge")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"A variável {name} precisa ser definida no arquivo .env")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def build_document(message) -> dict:
    raw_payload = bytes(message.payload)
    try:
        payload_text = raw_payload.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "topic": message.topic,
            "payload_base64": base64.b64encode(raw_payload).decode("ascii"),
            "received_at": datetime.now(timezone.utc),
            "qos": message.qos,
            "retain": message.retain,
        }

    try:
        payload_data = json.loads(payload_text)
    except json.JSONDecodeError:
        payload_data = payload_text

    return {
        "topic": message.topic,
        "payload": payload_text,
        "payload_data": payload_data,
        "received_at": datetime.now(timezone.utc),
        "qos": message.qos,
        "retain": message.retain,
    }


def add_persistence_timestamp(document: dict) -> None:
    document["data"] = datetime.now(timezone.utc)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    import paho.mqtt.client as mqtt
    from pymongo import MongoClient

    broker_host = required_env("MQTT_HOST")
    mongo_uri = required_env("MONGO_URI")
    topic = required_env("MQTT_TOPIC")
    mongo_database = required_env("MONGO_DATABASE")
    mongo_collection = required_env("MONGO_COLLECTION")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    qos = int(os.getenv("MQTT_QOS", "1"))
    if qos not in (0, 1, 2):
        raise ValueError("MQTT_QOS precisa ser 0, 1 ou 2")

    mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    collection = mongo_client[mongo_database][mongo_collection]
    collection.database.command("ping")
    logger.info("Conexão com MongoDB estabelecida")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=os.getenv("MQTT_CLIENT_ID", "mqtt-mongo-bridge"),
        clean_session=False,
        protocol=mqtt.MQTTv311,
    )
    username = os.getenv("MQTT_USERNAME", "").strip()
    password = os.getenv("MQTT_PASSWORD", "")
    if username:
        client.username_pw_set(username, password)
    if env_bool("MQTT_TLS"):
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    client.manual_ack_set(True)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.error("Falha ao conectar ao broker MQTT: %s", reason_code)
            return
        logger.info("Conectado ao broker MQTT; assinando %s (QoS %s)", topic, qos)
        client.subscribe(topic, qos=qos)

    def on_message(client, userdata, message):
        try:
            document = build_document(message)
            payload = document.get("payload", "base64:" + document["payload_base64"])
            logger.info("Mensagem recebida (tópico=%s, payload=%s)", message.topic, payload)
            add_persistence_timestamp(document)
            result = collection.insert_one(document)
            client.ack(message.mid, message.qos)
            logger.info("Mensagem gravada no MongoDB (id=%s, tópico=%s)", result.inserted_id, message.topic)
        except Exception:
            logger.exception("Não foi possível gravar a mensagem; ela não será confirmada ao broker")

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker_host, broker_port, keepalive=60)
        logger.info("Ouvindo mensagens no tópico %s", topic)
        client.loop_forever()
    finally:
        client.disconnect()
        mongo_client.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError) as error:
        logger.error("Configuração inválida: %s", error)
        raise SystemExit(1) from error
