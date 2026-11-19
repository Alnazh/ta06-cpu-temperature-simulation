"""Server Flask: halaman utama dan API simulasi."""
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from insights import STATUS_LABEL, build_insights, fan_summary
from simulation import (DEFAULT_SCENARIO, PRESETS, SCENARIOS, SLIDER_SCOPE, SLIDERS, TEMP_HOT, TEMP_WARM, Params,
                        fan_curve, parse_params, simulate)

app = Flask(__name__)

PRESET_LIST = [{"name": name, "scenario": scenario, "params": params, "hint": hint}
               for name, scenario, params, hint in PRESETS]
FAN_SLIDER_NAMES = ("fan", "g", "t_amb")


def page(template: str, **context):
    return render_template(template, defaults=asdict(Params()), warm=int(TEMP_WARM), hot=int(TEMP_HOT),
                           scope=SLIDER_SCOPE, default_scenario=DEFAULT_SCENARIO, **context)


@app.get("/")
def index():
    return page("index.html", scenarios=SCENARIOS.values(), sliders=SLIDERS, presets=PRESET_LIST)


@app.get("/simulator")
def simulator():
    return page("simulator.html", scenarios=SCENARIOS.values(), sliders=SLIDERS, presets=PRESET_LIST)


@app.get("/kipas")
def kipas():
    return page("kipas.html", sliders=[row for row in SLIDERS if row[0] in FAN_SLIDER_NAMES])


@app.get("/model")
def model():
    return page("model.html", scenarios=SCENARIOS.values())


@app.errorhandler(404)
def not_found(_error):
    return page("404.html"), 404


def read_params(payload: dict):
    """Params dari JSON; (None, respons error) bila tidak valid."""
    try:
        return parse_params(payload.get("params", {})), None
    except (TypeError, ValueError) as err:
        return None, (jsonify(error=str(err)), 400)


@app.post("/api/simulate")
def api_simulate():
    payload = request.get_json(silent=True) or {}
    scenario = SCENARIOS.get(payload.get("scenario"))
    if scenario is None:
        return jsonify(error="Skenario tidak dikenal"), 400
    params, error = read_params(payload)
    if error:
        return error
    result = simulate(params, scenario)
    result["insights"] = build_insights(params, scenario, result)
    result["metrics"]["status_label"] = STATUS_LABEL[result["metrics"]["status"]]
    return jsonify(result)


@app.post("/api/fans")
def api_fans():
    params, error = read_params(request.get_json(silent=True) or {})
    if error:
        return error
    return jsonify(fans=fan_curve(params), summary=fan_summary(params))


if __name__ == "__main__":
    app.run(debug=True)
