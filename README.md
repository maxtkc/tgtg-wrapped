# TGTG Wrapped

Export your Too Good To Go pickup history as a GeoJSON map.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**First-time login:**
```bash
python main.py --email your@email.com
```
A browser window will open to enter your login PIN. Credentials are saved to `tgtg_credentials.json` for future runs.

**Subsequent runs:**
```bash
python main.py
```

**Include full bag metadata (price, address, quantity, etc.):**
```bash
python main.py --metadata
```

**Custom output file:**
```bash
python main.py --output my_history.geojson
```

## Output

- `tgtg_history.geojson` (default) — view on [geojson.io](https://geojson.io) or import into any GIS tool

## Visualize the data

You can visualize your data [here](https://max.kcfam.us/blog/mapping-tgtg/).
Scroll to the bottom for the upload link.

## Notes

- `tgtg_credentials.json` stores your auth tokens locally — do not share or commit this file
- Based on the unofficial TGTG API from [Der-Henning/tgtg](https://github.com/Der-Henning/tgtg/blob/main/tgtg_scanner/tgtg/tgtg_client.py)
