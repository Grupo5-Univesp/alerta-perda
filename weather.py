"""Cliente da integração meteorológica usada pelo painel operacional."""

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HEAT_THRESHOLD_C = 32
HEAT_DAYS_THRESHOLD = 3

WEATHER_CODES = {
    0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Neblina", 48: "Neblina com geada", 51: "Garoa fraca",
    53: "Garoa moderada", 55: "Garoa intensa", 61: "Chuva fraca",
    63: "Chuva moderada", 65: "Chuva intensa", 80: "Pancadas de chuva fracas",
    81: "Pancadas de chuva moderadas", 82: "Pancadas de chuva intensas", 95: "Trovoada",
}


def get_weather_config():
    """Retorna a localização pública usada pela integração meteorológica."""
    return {
        "latitude": os.getenv("WEATHER_LATITUDE", "-21.0094"),
        "longitude": os.getenv("WEATHER_LONGITUDE", "-48.2217"),
        "location": os.getenv("WEATHER_LOCATION", "Pitangueiras, SP"),
    }


def get_weather(categories=None):
    """Obtém as condições atuais e a previsão de hoje para o local configurado."""
    config = get_weather_config()
    params = {
        "latitude": config["latitude"], "longitude": config["longitude"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 10, "timezone": "America/Sao_Paulo",
    }

    try:
        with urlopen(f"{OPEN_METEO_URL}?{urlencode(params)}", timeout=5) as response:
            payload = json.load(response)
    except (OSError, ValueError, KeyError):
        return None

    current = payload.get("current", {})
    daily = payload.get("daily", {})
    weather_code = current.get("weather_code")
    recommendation = get_climate_recommendation(daily, categories)
    return {
        "localidade": config["location"],
        "temperatura": current.get("temperature_2m"),
        "sensacao_termica": current.get("apparent_temperature"),
        "umidade": current.get("relative_humidity_2m"),
        "precipitacao": current.get("precipitation"),
        "condicao": WEATHER_CODES.get(weather_code, "Condição não informada"),
        "maxima": _first(daily, "temperature_2m_max"),
        "minima": _first(daily, "temperature_2m_min"),
        "probabilidade_chuva": _first(daily, "precipitation_probability_max"),
        "atualizado_em": current.get("time"),
        "recomendacao": recommendation,
    }


def _first(data, key):
    values = data.get(key, [])
    return values[0] if values else None


def get_climate_recommendation(daily, categories=None):
    """Cria uma recomendação operacional fictícia a partir dos próximos 10 dias."""
    dates = daily.get("time", [])
    max_temperatures = daily.get("temperature_2m_max", [])
    hot_days = [
        {"data": day, "maxima": maximum}
        for day, maximum in zip(dates, max_temperatures)
        if maximum is not None and maximum >= HEAT_THRESHOLD_C
    ]

    categories = set(categories or [])
    if len(hot_days) >= HEAT_DAYS_THRESHOLD:
        actions = [
            "Priorizar produtos próximos do vencimento em ações comerciais preventivas.",
        ]
        if "Hortifrúti (FLV)" in categories:
            actions.insert(0, "Hortifruti: reforçar o giro e a inspeção dos itens mais sensíveis.")
        if "Carnes e Aves" in categories:
            actions.insert(0, "Carnes e aves: conferir balcões e câmaras com maior frequência.")
        if "Laticínios e Frios" in categories:
            actions.insert(0, "Laticínios e frios: confirmar a cadeia de refrigeração e reduzir exposição.")
        return {
            "nivel": "warning",
            "titulo": "Atenção: período de calor previsto",
            "mensagem": (
                f"Há {len(hot_days)} dias com máxima prevista de {HEAT_THRESHOLD_C} °C "
                "ou mais nos próximos 10 dias."
            ),
            "acoes": actions,
            "dias_quentes": hot_days,
        }

    return {
        "nivel": "success",
        "titulo": "Condições climáticas dentro do limite definido",
        "mensagem": (
            f"Não há ao menos {HEAT_DAYS_THRESHOLD} dias com máxima de "
            f"{HEAT_THRESHOLD_C} °C ou mais nos próximos 10 dias."
        ),
        "acoes": ["Manter a rotina normal de inspeções e acompanhamento de validade."],
        "dias_quentes": hot_days,
    }
