# OSRM (road distances for the route planner)

Self-hosted routing engine with a Netherlands OpenStreetMap extract. Memory use scales with the extract size; measure it on your server before relying on it.

```
mkdir -p data && cd data
curl -LO https://download.geofabrik.de/europe/netherlands-latest.osm.pbf
docker run --rm -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/netherlands-latest.osm.pbf
docker run --rm -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/netherlands-latest.osrm
docker run --rm -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/netherlands-latest.osrm
cd .. && docker compose up -d
```

Test: `curl "http://127.0.0.1:5000/table/v1/driving/4.9,52.37;4.48,51.92"`

Refresh the map monthly: repeat the three commands and `docker compose restart`. These commands follow the OSRM documentation and have not been run for this project yet.
