import rasterio
from services.soil_quality_analysis.quality_index import normalize_bd,normalize_cec,normalize_n,normalize_ph,normalize_soc
from services.load_files import BULK_DENSITY_PATH, CEC_PATH, N_PATH, PH_PATH, SOC_PATH
from pyproj import Transformer
import numpy as np

class SoilQualityService:

    def __init__(self, PH_PATH, N_PATH, BD_PATH, CEC_PATH, SOC_PATH):
        self.ph_path = PH_PATH
        self.n_path = N_PATH
        self.bd_path = BD_PATH
        self.cec_path = CEC_PATH
        self.soc_path = SOC_PATH

    def get_value(self, path, lat, lon):
        with rasterio.open(path) as src:

            # CRS transform (keep your existing logic)
            if src.crs.to_string() != "EPSG:4326":
                from pyproj import Transformer
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                x, y = transformer.transform(lon, lat)
            else:
                x, y = lon, lat

            row, col = src.index(x, y)

            # WINDOW SAMPLING (KEY FIX)
            window = src.read(1)[row-2:row+3, col-2:col+3]

            nodata = src.nodata
            valid = window[
                (window != nodata) &
                (window > 0)
                ]

            if valid.size == 0:
                return None

            return float(np.mean(valid))

    def apply_scaling(self, param, value):
        if value is None:
            return None
        if param == "ph":
            return value / 10
        elif param == "bulk_density":
            return value / 100
        elif param == "soc":
            return value / 100
        elif param == "cec":
            return value / 10
        elif param == "nitrogen":
            return value / 1000
        return value

    def calculate_sqi_partial(self, data):
        weights = {
            "ph": 0.25,
            "nitrogen": 0.20,
            "soc": 0.25,
            "cec": 0.15,
            "bulk_density": 0.15
        }

        score = 0
        total_weight = 0

        for key, value in data.items():
            if value is None:
                continue

            if key == "ph":
                norm = normalize_ph(value)
            elif key == "nitrogen":
                norm = normalize_n(value)
            elif key == "soc":
                norm = normalize_soc(value)
            elif key == "cec":
                norm = normalize_cec(value)
            elif key == "bulk_density":
                norm = normalize_bd(value)

            score += norm * weights[key]
            total_weight += weights[key]

        if total_weight == 0:
            return None, "No Data", 0

        final_score = score / total_weight
        confidence = total_weight/sum(weights.values())

        if final_score > 0.8:
            quality = "Good"
        elif final_score > 0.5:
            quality = "Average"
        else:
            quality = "Poor"

        return final_score, quality,confidence

    def analyze(self, lat, lon):
        ph = self.get_value(self.ph_path, lat, lon)
        n = self.get_value(self.n_path, lat, lon)
        bd = self.get_value(self.bd_path, lat, lon)
        cec = self.get_value(self.cec_path, lat, lon)
        soc = self.get_value(self.soc_path, lat, lon)

        ph = self.apply_scaling("ph", ph)
        n = self.apply_scaling("nitrogen", n)
        bd = self.apply_scaling("bulk_density", bd)
        cec = self.apply_scaling("cec", cec)
        soc = self.apply_scaling("soc", soc)

        data = {
        "ph": ph,
        "nitrogen": n,
        "bulk_density": bd,
        "cec": cec,
        "soc": soc
        }

        missing = [k for k, v in data.items() if v is None]

        score, quality, confidence = self.calculate_sqi_partial(data)

        return {
            **data,
            "soil_quality_index": score,
            "soil_quality": quality,
            "confidence":confidence,
            "missing_parameters":missing
        }
    

soil_service = SoilQualityService(
    PH_PATH,
    N_PATH,
    BULK_DENSITY_PATH,
    CEC_PATH,
    SOC_PATH
)