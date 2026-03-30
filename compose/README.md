# Docker Compose: Mosquitto + Home Assistant

This folder holds config for the **two** services in `docker-compose.yml` at the repo root: the **MQTT broker** and **Home Assistant**. The LovensePy bridge (`HAMqttBridge`) is **not** containerized here—run it **on the host** with `pip install 'lovensepy[mqtt,ble]'` (BLE) or `'lovensepy[mqtt]'` (LAN). Containers cannot use the host Bluetooth stack reliably.

| Service | Role |
|---------|------|
| `mqtt` | Eclipse Mosquitto (`compose/mosquitto.conf`; host publishes `MQTT_PUBLISH_PORT`, default 1883) |
| `homeassistant` | Home Assistant (`compose/ha-config` → `/config`; UI on `HOME_ASSISTANT_PORT`, default 8123) |

## Quick start

```bash
cp .env.example .env
docker compose up -d
```

Open `http://localhost:8123` (or the port from `.env`) and finish onboarding.

Add the **MQTT** integration: **Settings → Devices & services → Add integration → MQTT**:

- **Broker:** `mqtt` (Compose service name — **not** `127.0.0.1` from inside HA)
- **Port:** `1883`
- No TLS, no credentials (matches `compose/mosquitto.conf`)

On the **host**, point the bridge at the published broker:

```bash
pip install 'lovensepy[mqtt,ble]'
export LOVENSE_TRANSPORT=ble
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883
python -m lovensepy.services.mqtt_bridge
# or: lovensepy-mqtt
```

For **LAN** (Game Mode on another host), run the same bridge on the host with `LOVENSE_TRANSPORT=lan` and `LOVENSE_LAN_IP` set—see [Home Assistant MQTT tutorial](../docs/tutorials/home-assistant-mqtt.en.md).

## Troubleshooting MQTT

**Home Assistant (in Docker) must use broker hostname `mqtt`, not `127.0.0.1`.** Use **`127.0.0.1` only on the host** for the Python bridge and MQTT clients.

```bash
docker compose ps mqtt
nc -zv 127.0.0.1 1883
docker compose logs mqtt --tail 30
```

After changing `compose/mosquitto.conf`: `docker compose up -d mqtt --force-recreate`.

## Migrating from the old `docker/` layout

If you used `./docker/ha-config` for Home Assistant data, stop the stack, copy your full `/config` tree (including `.storage`) into `compose/ha-config`, then start again with the updated `docker-compose.yml` paths.

## Logs

```bash
docker compose logs -f homeassistant
docker compose logs -f mqtt
```
