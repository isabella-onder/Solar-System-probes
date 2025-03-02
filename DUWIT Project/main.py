from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from datetime import datetime

app = FastAPI()

class Probe(BaseModel):
    name: str
    distance_in_km: float
    distance_in_AU: float
    timestamp: str

NASA_HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

def get_probe_data(probe_name: str):
    command_value = f"'{probe_name}'" if not probe_name.startswith('-') else probe_name

    params = {
        "format": "json",
        "OBJ_DATA": "NO",
        "COMMAND": command_value,
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "@399",
        "TIME": "NOW",
        "QUANTITIES": "1",
    }

    try:
        response = requests.get(NASA_HORIZONS_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if isinstance(data.get("result"), str) and "ERROR" in data["result"]:
            raise HTTPException(status_code=404, detail=data["result"])

        result_data = data.get("result", {})
        data_table = result_data.get("data", [])

        if not data_table:
            raise HTTPException(status_code=500, detail="No data table found")

        first_table = data_table[0]
        rows = first_table.get("rows", [])
        if not rows:
            raise HTTPException(status_code=500, detail="No rows in data table")

        first_row = rows[0]
        distance_au = float(first_row.get("delta", 0.0))
        timestamp_str = first_row.get("Date__(UT)__HR:MN", "Unknown")

        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%b-%d %H:%M:%S.%f")
        except ValueError:
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%b-%d %H:%M:%S")
            except ValueError:
                timestamp = "Invalid timestamp format"

        distance_km = distance_au * 149597870.7

        return Probe(
            name=probe_name,
            distance_in_km=round(distance_km, 2),
            distance_in_AU=round(distance_au, 4),
            timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S") 
            if isinstance(timestamp, datetime) else timestamp
        )

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"NASA API error: {str(e)}")
    except (KeyError, IndexError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Data parsing error: {str(e)}")

@app.get("/probe/{probe_name}", response_model=Probe)
def get_probe(probe_name: str):
    return get_probe_data(probe_name)

@app.get("/")
def root():
    return {"message": "Hello World"}
